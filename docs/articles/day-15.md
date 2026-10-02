### Day 15：綜合研判 Agent：跨領域影響推演與技術碰撞

在經過 Day 13 **Reviewer Agent** 的雜訊門檻過濾，以及 Day 14 **Domain Expert Agent** 榨取出的硬核量化指標（`metrics`）與邊界約束（`limitations`）之後，單一情報條目的本質已被徹底拆解。

然而，真實世界的技術創新很少孤立發生。一項新的 Attention 量化演算法，可能直接衝擊端側邊緣推論硬體；一項晶體結構預測模型，可能顛覆特定功能材料的合成路徑；一場宏觀流動性變化，可能連帶重構算力基礎設施的資本支出節奏。

**Synthesizer Agent（綜合研判代理人）** 的核心使命，就是跳脫單一論文或單一報導的微觀視角，進行**跨領域影響推演（Cross-Domain Impact Analysis）**，並產出系統標準欄位中的 `cross_impact_notes`。

---

## 核心設計：多維碰撞推演契約

依循六角架構契約，Synthesizer 接收已具備專家註解的 `IntelligenceItem`，並將其置於更廣闊的系統與產業全景中進行矩陣式碰撞。我們以 Pydantic V2 定義其結構化輸出 `SynthesizerResult`：

```python
# src/agents/synthesizer.py
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from src.core.models import IntelligenceItem

class ImpactVector(BaseModel):
    target_dimension: str = Field(..., description="受影響的面向 (如：硬體能耗、架構選型、工程落地、成本效益)")
    direction: str = Field(..., description="影響方向: POSITIVE (正面促進), NEGATIVE (阻礙/淘汰), 或 DISRUPTIVE (重構範式)")
    rationale: str = Field(..., description="推演邏輯與實質機制")

class SynthesizerResult(BaseModel):
    impact_vectors: list[ImpactVector] = Field(..., description="多維度技術衝擊向量")
    cross_impact_notes: str = Field(..., description="精煉的跨領域影響綜合筆記 (Markdown 條列或摘要)")
    downstream_actions: list[str] = Field(default_factory=list, description="建議下游工程或研究團隊採取的評估行動")
```

---

## 系統提示詞與 Agent 實作

Synthesizer 必須具備「系統思考（Systems Thinking）」的視角。其 Prompt 著重引導 LLM 將該項技術的優勢與缺陷，映射至整體工程生態中：

```python
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
        limitations_str = "\n".join([f"- {l}" for l in item.limitations]) or "無標註限制"

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

```

---

## 六角架構的協同價值

1. **避免資訊孤島**：傳統的情報爬蟲僅能保留原文摘錄，而 `SynthesizerAgent` 透過輸入前序節點產出的 `metrics` 與 `limitations`，讓條目具備了二階推演價值。
2. **無縫交棒至總編**：經過此步驟後，`cross_impact_notes` 已完整填入，所有深度的專家論據與影響向量皆已準備就緒，後續的最後一棒即可專注於文字風格重塑與讀者導向的排版。

明天 **Day 16**，我們將迎接多代理人管線的終點節點——**Editor Agent（主編總結與格式成型）**，並正式將全流程串聯起來，完成整條自動化情報雷達流水線！