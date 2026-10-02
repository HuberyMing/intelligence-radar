### Day 14：領域專家 Agent：深度技術指標萃取與限制剖析

在 Day 13 中，我們建構了第一道防線 **Reviewer Agent**，以冷酷且客觀的門檻（`raw_score >= 60`）過濾掉充斥宣傳話術的低價值公關稿。當情報條目獲得放行許可（`should_continue = True`）後，流水線便正式進入第二階段：**Domain Expert Agent（領域專家代理人）**。

與審核員著眼於「是否及格」不同，領域專家 Agent 的任務是**技術下鑽（Deep-Dive Analysis）**——從原文中精準萃取具備複現價值的硬指標（Benchmark、吞吐量、記憶體佔用、超參數），並以批判視角挖掘作者避重就輕的「系統限制與邊界條件」。

---

## 核心設計：結構化萃取契約

依據六角架構與 `IntelligenceItem` 契約，Domain Expert 主要負責填充與校準兩個關鍵欄位：

* `metrics`（`list[str]`）：量化硬指標與實驗對比數據。
* `limitations`（`list[str]`）：架構侷限、邊界限制與失效場景。
* `verified_score`（`int`）：由專家結合技術細節深度後給出的校準分數。

```python
# src/agents/domain_expert.py
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

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
    
```

---

## 提示詞工程與 Agent 實作

技術情報常有「報喜不報憂」的偏差。因此，Domain Expert 的提示詞著重在**逆向工程其潛在約束**（例如：推論延遲是否因注意力機制急遽上升？是否僅限特定顯存與批量大小？）：

```python
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

```

---

## 運作價值與六角實踐

1. **資訊密度倍增**：經過此節點後，`IntelligenceItem` 不再只是粗糙的文字摘要，而是轉化為攜帶「量化指標對照」與「防禦性缺陷評估」的結構化技術資產。
2. **為綜合評估鋪路**：萃取出的 `limitations` 與 `metrics` 將直接作為下游 **Synthesizer Agent（交叉影響綜合代理人）** 的關鍵依據，用以判斷該技術對既有技術堆疊（如推論加速、記憶體優化）的實質衝擊。

明天 **Day 15**，我們將把目光移向跨領域關聯，實作 **Synthesizer Agent**，負責推演多領域技術衝擊與自動產出 Cross-Impact 洞察筆記！
