# src/core/models.py
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, HttpUrl, field_validator


class ItemStatus(str, Enum):
    """狀態機生命週期定義"""
    PENDING = "PENDING"          # 收集端剛寫入，等待處理
    ANALYZING = "ANALYZING"      # ADK 正在分析審核中 (鎖定狀態)
    PROCESSED = "PROCESSED"      # 審核通過 (>= 4分)，納入發布週報
    ARCHIVED = "ARCHIVED"        # 常規雜訊 (< 4分)，歸檔留存
    ERROR = "ERROR"              # 處理異常


class DomainType(str, Enum):
    """一級領域分類"""
    SCIENCE = "SCIENCE"
    FINANCE = "FINANCE"
    COMMUNITY = "COMMUNITY"


class IntelligenceItem(BaseModel):
    """
    情報條目核心資料契約 (Data Contract)
    貫穿整個收集端、Google Sheets 資料庫與 ADK 推理層。
    """
    # 1. 系統骨架欄位 (不可變)
    entry_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8],
        description="條目唯一識別碼"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="收集入庫時間"
    )
    status: ItemStatus = Field(
        default=ItemStatus.PENDING,
        description="當前狀態機節點"
    )

    # 2. 路由分類與來源
    domain: DomainType = Field(description="主領域")
    track: str = Field(description="子軌道標籤，例如 AI_Frontier、Macro_Econ")
    source_title: str = Field(min_length=3, description="標題")
    source_url: str = Field(description="原始連結")

    # 3. 收集端提煉內容
    raw_content: str = Field(description="核心摘要或論點")
    metrics: Optional[str] = Field(default=None, description="關鍵數據表現")
    limitations: Optional[str] = Field(default=None, description="潛在風險或侷限")
    raw_score: int = Field(ge=1, le=5, description="收集端給予的初級評分 (1-5)")

    # 4. ADK 多代理人推演後的落實欄位
    verified_score: Optional[int] = Field(
        default=None, ge=1, le=5, description="審核員校準後的最終評分"
    )
    editorial_summary: Optional[str] = Field(
        default=None, description="資深編輯精煉後的決策層摘要"
    )
    cross_impact_notes: Optional[str] = Field(
        default=None, description="跨領域推演關聯筆記"
    )

    # 5. 彈性預留槽 (擴充的關鍵)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="以字典儲存特定信源專屬的擴充屬性 (如 PDF 下載點、作者名冊)"
    )

    class Config:
        use_enum_values = True
        validate_assignment = True