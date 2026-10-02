# src/core/harmonizer.py
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.models import IntelligenceItem, ItemStatus


class DataHarmonizer:
    """異構資料對齊轉換器：將各收集端原始字典轉換為標準 IntelligenceItem"""

    @staticmethod
    def normalize(raw_payload: Dict[str, Any]) -> IntelligenceItem:
        """
        將前端輸入標準化為完整 15 欄合約
        自動處理預設值、欄位映射與型別容錯
        """
        # 1. 提取或生成主鍵與時間
        entry_id = raw_payload.get("entry_id") or str(uuid.uuid4())[:8]
        timestamp = raw_payload.get("timestamp") or datetime.now(timezone.utc)

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
            entry_id=entry_id,
            timestamp=timestamp,
            status=ItemStatus.PENDING,  # 強制鎖定為待處理
            domain=raw_payload["domain"],
            track=raw_payload["track"],
            source_title=raw_payload["source_title"].strip(),
            source_url=raw_payload["source_url"].strip(),
            raw_content=raw_payload["raw_content"].strip(),
            metrics=raw_payload.get("metrics"),
            limitations=raw_payload.get("limitations"),
            raw_score=int(raw_payload.get("raw_score", 3)),
            verified_score=None,
            editorial_summary=None,
            cross_impact_notes=None,
            metadata=merged_metadata
        )
        return item

# 在 src/core/harmonizer.py 追加序列化方法
import json


class SheetSerializer:
    """負責將 IntelligenceItem 映射至 Google Sheets A~O 欄位"""

    HEADERS = [
        "entry_id", "timestamp", "status", "domain", "track",
        "source_title", "source_url", "raw_content", "metrics",
        "limitations", "raw_score", "verified_score", "editorial_summary",
        "cross_impact_notes", "metadata"
    ]

    @staticmethod
    def to_row(item: IntelligenceItem) -> List[Any]:
        """按嚴格順序序列化為 Google Sheets 寫入陣列"""
        return [
            item.entry_id,
            item.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            item.status.value,
            item.domain.value if hasattr(item.domain, "value") else str(item.domain),
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

