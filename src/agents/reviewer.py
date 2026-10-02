# src/agents/reviewer.py
from typing import Literal, Tuple

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.core.models import IntelligenceItem, ItemStatus


# =====================================================================
# 1. Reviewer Agent (Day 13): 初審評分與二分流決策
# =====================================================================
class ReviewResult(BaseModel):
    raw_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="情報技術價值評分，範圍 0 到 100。扣分依據缺乏數據或公關空話。"
    )
    decision: Literal["PASS", "DROP"] = Field(
        ...,
        description="二分流判定：達到 60 分且具備技術價值為 'PASS'，低於 60 分為 'DROP'。"
    )
    reason: str = Field(
        ...,
        description="審核判定理由，精確指出扣分項目或給予高分的關鍵技術依據。"
    )
    key_metrics_found: list[str] = Field(
        default_factory=list,
        description="初審中快速抓取到的硬核技術量化指標（如無則為空清單）。"
    )

# src/agents/reviewer.py (續)

REVIEWER_SYSTEM_INSTRUCTION = """
你是一位極度嚴苛、追求技術實質與數據佐證的冷酷情報審核員（Reviewer Agent）。
你的職責是評估傳入情資的「技術實質密度」與「可驗證性」，並決定其生死。

評分規則 (0 - 100 分)：
1. 缺乏具體量化數據、基準測試或實證依據：直接扣 30-40 分。
2. 充斥行銷話術、公關宣傳或空泛預測（如「將顛覆產業」）：扣 25 分。
3. 具備明確架構突破、開源程式碼、可驗證技術細節或硬指標：給予 70 分以上基準。

判定規則：
- raw_score >= 60：判定為 PASS（進入下游專家節點深入分析）。
- raw_score < 60：判定為 DROP（雜訊過濾，立即歸檔中斷）。
輸出必須嚴格符合指定 JSON 結構。
"""

class ReviewerAgent:
    def __init__(self, client: genai.Client, model_name: str = "gemini-2.5-flash", threshold: int = 60):
        self.client = client
        self.model_name = model_name
        self.threshold = threshold

    def evaluate(self, item: IntelligenceItem) -> Tuple[IntelligenceItem, bool]:
        """
        評估單一情報條目。
        回傳: (更新後的 IntelligenceItem, should_continue)
        """
        prompt = f"""
        請審核以下情資條目：
        【標題】：{item.source_title}
        【來源網址】：{item.source_url}
        【領域/軌道】：{item.domain} / {item.track}
        【原始摘要/內文】：
        {item.raw_content}
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=REVIEWER_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ReviewResult,
                temperature=0.1,  # 低隨機性以維持客觀嚴謹
            ),
        )

        result = ReviewResult.model_validate_json(response.text)
        
        # 回填核心領域模型
        item.raw_score = result.raw_score
        item.metadata["reviewer_decision"] = result.decision
        item.metadata["reviewer_reason"] = result.reason
        if result.key_metrics_found and not item.metrics:
            item.metrics = result.key_metrics_found

        # Early-exit 狀態機轉移判定
        if result.raw_score >= self.threshold and result.decision.upper() == "PASS":
            # 通過審核，維持 ANALYZING 狀態，交給下游節點
            return item, True
        else:
            # 雜訊熔斷，標記歸檔，中止後續流水線
            item.status = ItemStatus.ARCHIVED
            item.editorial_summary = f"[雜訊過濾歸檔] {result.reason}"
            return item, False
