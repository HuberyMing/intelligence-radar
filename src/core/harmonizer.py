# src/core/harmonizer.py
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.models import IntelligenceItem, ItemStatus


class DataHarmonizer:
    """異構資料對齊轉換器：將各收集端原始字典轉換為標準 IntelligenceItem"""

    @staticmethod
    def _parse_timestamp(ts: Any) -> datetime:
        """容錯時間解析器：處理 Google Sheets 各種非標準時間字串"""
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        
        if isinstance(ts, str) and ts.strip():
            # 常見時間格式清單（包含個位數小時、斜線日期與 ISO 格式）
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %I:%M:%S %p",
                "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y-%m-%d",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(ts.strip(), fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            
            # 若標準 strptime 無法匹配，嘗試以 ISO 格式解析
            try:
                dt = datetime.fromisoformat(ts.strip())
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # 最終 fallback：若無法辨別則給當下 UTC 時間
        return datetime.now(timezone.utc)

    @staticmethod
    def normalize(raw_payload: Dict[str, Any]) -> IntelligenceItem:
        """
        將前端輸入標準化為完整 15 欄合約
        自動處理預設值、欄位映射與型別容錯
        """
        # 1. 提取或生成主鍵與時間 (使用容錯時間解析)
        entry_id = raw_payload.get("entry_id") or str(uuid.uuid4())[:8]
        timestamp = DataHarmonizer._parse_timestamp(raw_payload.get("timestamp"))

        # 2. 提取或打包自訂 metadata
        core_fields = {
            "entry_id", "timestamp", "status", "domain", "track",
            "source_title", "source_url", "raw_content", "metrics",
            "limitations", "raw_score", "verified_score",
            "editorial_summary", "cross_impact_notes", "metadata"
        }
        
        # 既有的 metadata 加上未在核心定義的外掛欄位
        merged_metadata = dict(raw_payload.get("metadata", {}))
        for k, v in raw_payload.items():
            if k not in core_fields:
                merged_metadata[k] = v

        # 3. 建立並嚴格驗證 Pydantic 物件
        item = IntelligenceItem(
            entry_id=str(entry_id),
            timestamp=timestamp,
            status=ItemStatus.PENDING,  # 強制鎖定為待處理
            domain=raw_payload["domain"],
            track=raw_payload["track"],
            source_title=str(raw_payload["source_title"]).strip(),
            source_url=str(raw_payload["source_url"]).strip(),
            raw_content=str(raw_payload["raw_content"]).strip(),
            metrics=raw_payload.get("metrics") or None,
            limitations=raw_payload.get("limitations") or None,
            raw_score=int(raw_payload.get("raw_score", 3)),
            verified_score=None,
            editorial_summary=None,
            cross_impact_notes=None,
            metadata=merged_metadata
        )
        return item


class SheetSerializer:
    """負責將 IntelligenceItem 映射至 Google Sheets A~O 欄位"""

    HEADERS = [
        "entry_id", "timestamp", "status", "domain", "track",
        "source_title", "source_url", "raw_content", "metrics",
        "limitations", "raw_score", "verified_score", "editorial_summary",
        "cross_impact_notes", "metadata"
    ]

    @staticmethod
    def _val(field: Any) -> str:
        """輔助函式：安全提取 Enum 或純字串的值"""
        if hasattr(field, "value"):
            return str(field.value)
        return str(field) if field is not None else ""

    @staticmethod
    def to_row(item: IntelligenceItem) -> List[Any]:
        """按嚴格順序序列化為 Google Sheets 寫入陣列 (15 欄)"""
        return [
            item.entry_id,
            item.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            SheetSerializer._val(item.status),
            SheetSerializer._val(item.domain),
            item.track,
            item.source_title,
            item.source_url,
            item.raw_content,
            item.metrics or "",
            item.limitations or "",
            item.raw_score,
            item.verified_score if item.verified_score is not None else "",
            item.editorial_summary or "",
            item.cross_impact_notes or "",
            json.dumps(item.metadata, ensure_ascii=False) if item.metadata else "{}"
        ]
