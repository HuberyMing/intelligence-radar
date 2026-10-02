
### Day 13：冷酷審核員 Agent：打造抗雜訊評分與二分流機制

在 Day 12 中，我們勾勒出多代理人協同的核心藍圖。在資訊洪流的情報雷達系統中，最忌諱讓高成本的下游專家模型（Domain Expert / Synthesizer）去分析低質量的公關稿或空洞雜訊。因此，整個 ADK 流程的第一道守門員，就是 **Reviewer Agent（冷酷審核員）**。

Reviewer 的使命非常明確：**執行確定性門檻過濾與 Early-exit 分流**。它依據資訊密度、技術實質指標與事實佐證度進行量化評分（0-100）。若評分低於門檻（例如 60 分），流程立即熔斷並標記為 `ARCHIVED`，不再觸發後續高運算成本節點。

---

## 核心設計：結構化評分輸出契約

依循六角架構與 Pydantic V2，我們先定義 Reviewer 的結構化輸出模型 `ReviewResult`，確保 ADK 呼叫 Gemini 時能以 JSON Schema 約束輸出：

```python
# src/agents/reviewer.py
from typing import Tuple
from typing import Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

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

```

💡 關鍵架構細節：解密 Field(...) 中的 Ellipsis（省略號）
在定義 ReviewResult 時，讀者可能會注意到屬性皆宣告為 Field(..., ...)。在 Python 與 Pydantic 規範中，首個參數 ...（Ellipsis 物件）代表「**該欄位為強制必填（Required），不允許任何預設值**」。
這樣的設計在多代理人串接中至關重要：
1. 約束 JSON Schema 生成：Pydantic 導出 Schema 時，會強制將該鍵值寫入 OpenAPI 的 "required": [...] 陣列中，杜絕 LLM 漏填欄位。
2. 嚴格拒絕缺漏：若模型回傳的 JSON 缺少 raw_score 或 decision，Pydantic 在 model_validate_json() 階段便會立即拋出 ValidationError，防止不完整的髒資料流入下游管線。
3. 與選填欄位的對比：相對於必填欄位，像是初審時「不一定能抓到量化數據」的 key_metrics_found，我們則使用 default_factory=list 提供初始空容器，兼顧合約的嚴謹度與彈性。

---

## 審核員 Prompt 與 Agent 實作

Reviewer 必須被賦予嚴苛的 Persona 與明確的扣分標準，嚴格抵禦標題黨（Clickbait）與毫無量化數據的空泛論述：

```python
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

```

---

## 運作機制與架構價值

1. **零污染與六角封裝**：`ReviewerAgent` 只依賴領域模型 `IntelligenceItem` 與標準 SDK，運作結果只變更模型狀態與評分欄位，不直接碰觸外部資料庫或工作表。
2. **Early-exit 成本截斷**：當 `should_continue` 為 `False` 時，Orchestrator 可直接呼叫 `SheetsAdapter.update_item_status(item)` 刷回 `ARCHIVED`，在第一站直接攔截 60% 以上的平庸雜訊，兼顧系統吞吐量與 API 預算控管。

明天 **Day 14**，我們將接續放行通過門檻的高價值情報，實作 **Domain Expert Agent** 進行深度的技術指標萃取與限制挑戰剖析！
