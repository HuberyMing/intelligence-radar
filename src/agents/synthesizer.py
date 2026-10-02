# src/agents/synthesizer.py
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.core.models import IntelligenceItem


# =====================================================================
# 3. Synthesizer Agent (Day 15): 跨維度衝擊與二階技術碰撞
# =====================================================================
class ImpactVector(BaseModel):
    target_dimension: str = Field(
        ...,
        description="受影響的面向（例如：硬體算力架構、端側推論能耗、模型訓練成本、工程部署生態）。"
    )
    direction: Literal["POSITIVE", "NEGATIVE", "DISRUPTIVE"] = Field(
        ...,
        description="影響方向：正面促進 (POSITIVE)、增加阻礙或面臨淘汰 (NEGATIVE)、顛覆舊範式 (DISRUPTIVE)。"
    )
    rationale: str = Field(
        ...,
        description="詳細的推演邏輯，說明該項技術如何透過具體機制引發該維度的二階效應。"
    )

class SynthesizerResult(BaseModel):
    impact_vectors: list[ImpactVector] = Field(
        ...,
        description="結構化的多維度技術衝擊向量清單。"
    )
    cross_impact_notes: str = Field(
        ...,
        description="Markdown 格式的跨領域影響綜合研判筆記，條列分析與整體推演結論。"
    )
    downstream_actions: list[str] = Field(
        default_factory=list,
        description="建議下游架構師或研發團隊進行驗證或技術儲備的具體行動步驟。"
    )

# src/agents/synthesizer.py (續)

SYNTHESIZER_SYSTEM_INSTRUCTION = """
你是一位具備宏觀工程架構與前沿科研視野的綜合研判專家（Synthesizer Agent）。
你的職責不是重複單點技術摘要，而是從更宏觀的視角進行跨領域衝擊推演與技術碰撞。

分析維度指南：
1. 【工程落地與架構相容】：該技術是否需要更換既有算力基礎設施？與主流推論引擎（如 vLLM、TensorRT-LLM）或既有管線是否衝突？
2. 【連鎖效益推演】：結合其 Limitations，思考若在真實生產環境採用，會引發哪些非預期的二階效應（Second-Order Effects）？
3. 【橫向學科碰撞】：該技術對相鄰領域（例如：計算科學、邊緣端運算、定量策略評估）具備何種潛在借鑒價值？

請以客觀、具預見性且邏輯嚴密的工程視角輸出指定 JSON Schema。
"""

class SynthesizerAgent:
    def __init__(self, client: genai.Client, model_name: str = "gemini-2.5-flash"):
        self.client = client
        self.model_name = model_name

    def synthesize(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        對情報條目進行跨領域推演與二階影響分析，回填 cross_impact_notes。
        """
        # 將專家節點萃取的指標與限制結構化餵入
        metrics_str = "\n".join([f"- {m}" for m in item.metrics]) or "無量化指標"

        # 修改為更語意化的 lim：
        limitations_str = "\n".join([f"- {lim}" for lim in item.limitations]) or "無特別限制"

        prompt = f"""
        請推演以下技術情資的跨領域影響與二階技術碰撞：
        【情資主題】：{item.source_title}
        【所屬範疇】：{item.domain} / {item.track}
        【專家校準分數】：{item.verified_score} / 100
        【核心量化指標】：
        {metrics_str}
        【已識別邊界與架構缺陷】：
        {limitations_str}
        【技術本質摘要】：
        {item.metadata.get("expert_takeaway", item.raw_content[:400])}
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYNTHESIZER_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=SynthesizerResult,
                temperature=0.3,
            ),
        )

        result = SynthesizerResult.model_validate_json(response.text)

        # 寫入領域核心模型
        item.cross_impact_notes = result.cross_impact_notes
        item.metadata["synthesizer_vectors"] = [v.model_dump() for v in result.impact_vectors]
        item.metadata["synthesizer_actions"] = result.downstream_actions

        return item
