# src/adapters/notion_adapter.py
from __future__ import annotations

import uuid
import logging
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError

from src.core.models import IntelligenceItem
from src.ports.knowledge_sync import KnowledgeSyncPort

logger = logging.getLogger(__name__)

class NotionSyncAdapter(KnowledgeSyncPort):
    def __init__(self, auth_token: str, database_id: str):
        self.client = Client(auth=auth_token)
        self.database_id = database_id

    def _find_page_by_entry_id(self, entry_id: str) -> str | None:
        """依據 Entry ID 查詢是否已存在該筆情資（確保冪等性）"""
        try:
            # # 舊版寫法
            # response = self.client.databases.query(
            #     database_id=self.database_id,
            #     filter={
            #         "property": "Entry ID",
            #         "rich_text": {
            #             "equals": str(entry_id)
            #         }
            #     }
            # )

            # # 新版寫法：改用 client.request 直接查詢
            # # 使用 client.request 既不會受到 SDK 物件命名改版的影響，又能 100% 維持 Notion 官方 API 查詢語意！
            # response = self.client.request(
            #     path=f"databases/{self.database_id}/query",
            #     method="POST",
            #     body={"filter": {"property": "Entry ID", "rich_text": {"equals": entry_id}}},
            # )

            # 1. 確保 database_id 格式為合法的標準 UUID (例如：3f44e1c2-03bf-8097-815f-ef01e424ddc1)
            raw_id = self.database_id.strip().replace("-", "")
            formatted_db_id = str(uuid.UUID(raw_id))
            
            # 2. 呼叫 query endpoint
            response = self.client.request(
                path=f"databases/{formatted_db_id}/query",
                method="POST",
                body={
                    "filter": {
                        "property": "Entry ID",
                        "rich_text": {
                            "equals": str(entry_id)
                        }
                    }
                }
            )

            results = response.get("results", [])
            return results[0]["id"] if results else None
        
        except APIResponseError as e:
            logger.error(f"查詢 Notion 資料庫失敗: {e}")
            return None


    def _build_properties(self, item: IntelligenceItem) -> dict[str, Any]:
        """將領域模型映射為 Notion Database Properties"""
        date_str = None
        if item.timestamp:
            date_str = item.timestamp.strftime("%Y-%m-%d") if hasattr(item.timestamp, "strftime") else str(item.timestamp)[:10]

        properties: dict[str, Any] = {
            "Title": {
                "title": [{"text": {"content": item.source_title or "Untitled"}}]
            },
            "Entry ID": {
                "rich_text": [{"text": {"content": str(item.entry_id)}}]
            },
            "Domain": {
                "select": {"name": item.domain or "GENERAL"}
            },
            "Score": {
                "number": float(item.verified_score or item.raw_score or 0)
            }
        }

        if item.source_url:
            properties["Source URL"] = {"url": item.source_url}

        if date_str:
            properties["Date"] = {"date": {"start": date_str}}

        return properties

    def _build_children_blocks(self, item: IntelligenceItem) -> list[dict[str, Any]]:
        """建立頁面內的 Rich Text 區塊結構（包含 Callout 與各級標題）"""
        blocks = []

        # 核心提煉 Callout
        summary_text = item.editorial_summary or "暫無編輯精煉摘要"
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": f"核心提煉：\n{summary_text}"}}],
                "icon": {"emoji": "💡"}
            }
        })

        # 量化對比與效能指標
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "📊 量化對比與效能指標"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": item.metrics or "無顯著量化指標揭露。"}}]
            }
        })

        # 技術邊界與缺陷
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "⚠️ 技術邊界與潛在缺陷"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": item.limitations or "作者未於論文中強調顯著邊界。"}}]
            }
        })

        # 二階效應
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "🔮 二階效應與跨領域衝擊"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": item.cross_impact_notes or "暫無二階推演。" }}],
                "icon": {"emoji": "🚀"}
            }
        })

        return blocks

    def sync_item(self, item: IntelligenceItem, overwrite: bool = False) -> bool:
        """同步單筆情報至 Notion，若已存在則檢查 overwrite 決定是否更新"""
        existing_page_id = self._find_page_by_entry_id(str(item.entry_id))
        
        properties = self._build_properties(item)

        try:
            if existing_page_id:
                if not overwrite:
                    logger.info(f"Notion 頁面已存在，略過更新: [{item.entry_id}]")
                    return False
                
                # 覆寫既有頁面屬性
                self.client.pages.update(page_id=existing_page_id, properties=properties)
                logger.info(f"成功更新 Notion 頁面: [{item.entry_id}]")
                return True
            else:
                # 建立新頁面
                children = self._build_children_blocks(item)
                self.client.pages.create(
                    parent={"database_id": self.database_id},
                    properties=properties,
                    children=children
                )
                logger.info(f"成功建立 Notion 新頁面: [{item.entry_id}]")
                return True
        except APIResponseError as err:
            logger.error(f"寫入 Notion API 失敗 [{item.entry_id}]: {err}")
            return False

    def batch_sync(self, items: list[IntelligenceItem], overwrite: bool = False) -> dict[str, int]:
        stats = {"synced": 0, "skipped": 0}
        for item in items:
            if self.sync_item(item, overwrite=overwrite):
                stats["synced"] += 1
            else:
                stats["skipped"] += 1
        return stats