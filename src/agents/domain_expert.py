# src/agents/domain_expert.py
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.core.models import IntelligenceItem


# =====================================================================
# 2. Domain Expert Agent (Day 14): 深度指標萃取與限制挑戰
# =====================================================================
class ExpertAnalysisResult(BaseModel):
    verified_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="技術深度二次校準分數 (0-100)，評估其實用性、原創性與可驗證性。"
    )
    key_metrics: list[str] = Field(
        ...,
        description="量化技術指標清單，必須包含數值、基準（Benchmark）與測試硬體條件。"
    )
    limitations: list[str] = Field(
        ...,
        description="論文或技術文章避重就輕的邊界條件、架構缺陷、未解瓶頸或極限場景。"
    )
    technical_takeaway: str = Field(
        ...,
        description="一句話總結該技術架構的核心本質與最具價值的工程突破點。"
    )

# src/agents/domain_expert.py (續)

DOMAIN_EXPERT_SYSTEM_INSTRUCTION = """
你是一位資深的技術領域專家與架構架構師（Domain Expert Agent）。
你的職責是對已經通過初審的高價值技術情報進行深度剖析，提取可驗證的量化數據並戳破潛在宣傳泡沫。

分析要點：
1. 【量化指標 (Metrics)】：萃取所有具體的測試基準（如 MMLU, Tokens/s, VRAM, FLOPS, 訓練/推論延遲）。嚴禁提取「顯著提升」等模糊詞彙，必須具備數值與對照組。
2. 【邊界與限制 (Limitations)】：發掘論文或文章未明說或輕描淡寫的限制（例如：上下文長度外推失敗、極度依賴高品質標註資料、記憶體頻寬瓶頸、無量化支援等）。
3. 【校準評分 (Verified Score)】：結合技術架構的原創性、實用性與再現可能性重新評分 (0-100)。若發現指標有 cherry-picking 嫌疑，應酌情調低分數。

輸出必須完全符合所指定的 JSON Schema。
"""

class DomainExpertAgent:
    def __init__(self, client: genai.Client, model_name: str = "gemini-2.5-flash"):
        self.client = client
        self.model_name = model_name

    def analyze(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        對情報進行領域深度分析，補全 metrics, limitations 與 verified_score。
        """
        prompt = f"""
        請針對以下通過初審的技術情報進行深度專家剖析：
        【領域分類】：{item.domain} / {item.track}
        【技術標題】：{item.source_title}
        【初審評分】：{item.raw_score}
        【原始內文/摘要】：
        {item.raw_content}
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=DOMAIN_EXPERT_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ExpertAnalysisResult,
                temperature=0.2,
            ),
        )

        analysis = ExpertAnalysisResult.model_validate_json(response.text)

        # 回填領域核心資料模型
        item.verified_score = analysis.verified_score
        item.metrics = analysis.key_metrics
        item.limitations = analysis.limitations
        item.metadata["expert_takeaway"] = analysis.technical_takeaway

        return item
