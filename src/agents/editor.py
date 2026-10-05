# src/agents/editor.py
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.core.models import IntelligenceItem


class EditorialResult(BaseModel):
    headline: str = Field(
        ...,
        description="一句精煉的情報主標題，突出實質突破或核心價值，拒絕標題黨。"
    )
    editorial_summary: str = Field(
        ...,
        description="嚴格遵循三段式結構的 Markdown 技術簡報（背景與突破、關鍵指標對照、架構限制與建議）。"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="技術檢索標籤（如：['FP8', 'vLLM', 'Attention-Free']）。"
    )

# src/agents/editor.py (續)

EDITOR_SYSTEM_INSTRUCTION = """
你是一位資深科技技術總編（Editor Agent）。
你的任務是將各專家代理人萃取的零散事實、量化指標、架構限制與衝擊推演，熔鑄成一份專業、高密度且排版嚴謹的技術情報短報。

撰寫排版規範（Markdown 格式）：
1. 【核心突破 (The Breakthrough)】：1-2 句話說明解決了什麼工程瓶頸及其本質。
2. 【硬核指標 (Verified Benchmarks)】：條列展示專家節點提煉的量化對比數據。
3. 【邊界挑戰與落地推演 (Limits & Action)】：精煉限制與 Synthesizer 的二階影響，給出具體工程評估建議。

語氣要求：極客、嚴謹、杜絕公關空話。輸出必須嚴格遵循指定 JSON Schema。
"""

class EditorAgent:
    def __init__(self, client: genai.Client, model_name: str = "gemini-3.8-flash"):
        self.client = client
        self.model_name = model_name

    def edit(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        將已標註的多維情資編排為高品質的 Markdown 編輯摘要。
        """
        metrics_block = "\n".join([f"- {m}" for m in item.metrics]) or "無量化數據"

        # 原本寫法 (容易被 linter 認為 l 像 1)：
        # limitations_block = "\n".join([f"- {l}" for l in item.limitations]) or "無特別限制"
        # 修改為更語意化的 lim：
        limitations_block = "\n".join([f"- {lim}" for lim in item.limitations]) or "無特別限制"


        prompt = f"""
        請將以下技術情報加工編纂為最終技術短報：
        【情報標題】：{item.source_title}
        【領域分類】：{item.domain} / {item.track}
        【審核評分】：初審 {item.raw_score} / 複審 {item.verified_score}
        【專家提煉指標】：
        {metrics_block}
        【已確認限制】：
        {limitations_block}
        【跨領域綜合影響 (Synthesizer)】：
        {item.cross_impact_notes}
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=EDITOR_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=EditorialResult,
                temperature=0.2,
            ),
        )

        result = EditorialResult.model_validate_json(response.text)

        # 回填領域核心資料模型
        item.editorial_summary = f"### {result.headline}\n\n{result.editorial_summary}"
        item.metadata["editorial_tags"] = result.tags

        return item

