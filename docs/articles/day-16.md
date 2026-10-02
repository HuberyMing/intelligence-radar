### Day 16：總編 Agent：精煉技術摘要與多代理人管線串接（Pipeline Integration）

走過審核員（Reviewer）的雜訊篩選、專家（Domain Expert）的指標深挖，以及綜合研判員（Synthesizer）的跨界衝擊推演，單一情報條目的核心技術事實已被全面提煉。

然而，這些數據目前仍是分散且生硬的結構化資訊。終端讀者（如架構師、技術長或量化研發人員）在晨會或巡檢時，需要的是一份能在 60 秒內掌握技術本質、關鍵數據與行動建議的高密度報告。

**Editor Agent（總編輯代理人）** 的職責正是進行**最後一哩路的文字重構與格式定型**，填充 `IntelligenceItem` 的 `editorial_summary` 欄位。完成後，我們將透過管線編排器（Orchestration Pipeline）將四位代理人串連起來，完成全自動化處理解析。

---

## 核心設計：總編輸出契約

依據六角架構契約，Editor Agent 必須整合前三位 Agent 的輸出，並產出結構化且排版精美的 Markdown 摘要：

```python
# src/agents/editor.py
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

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

```

---

## 提示詞設計與 Editor Agent 實作

Editor Agent 的 Prompt 著重在**資訊結構標準化**與**工程師視角的敘事**：

```python
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
    def __init__(self, client: genai.Client, model_name: str = "gemini-2.5-flash"):
        self.client = client
        self.model_name = model_name

    def edit(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        將已標註的多維情資編排為高品質的 Markdown 編輯摘要。
        """
        metrics_block = "\n".join([f"- {m}" for m in item.metrics]) or "無量化數據"
        limitations_block = "\n".join([f"- {l}" for l in item.limitations]) or "無特別限制"

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

```

---

## 核心串接：多代理人流水線編排器（Orchestration Pipeline）

現在，四位專職代理人已經全部就位。我們在應用層（`src/services/`）建立 `IntelligencePipeline`，負責驅動完整的狀態機生命週期：

```
[Google Sheets / Queue]
         │ (PENDING)
         ▼ (Fetch & Lock)
    [Reviewer] ──(raw_score < 60)──► [ARCHIVED (熔斷)] ──► [Sheets 回填]
         │ (PASS)
         ▼
  [Domain Expert] ── (萃取 metrics & limitations)
         │
         ▼
   [Synthesizer]  ── (推演 cross_impact_notes)
         │
         ▼
     [Editor]     ── (產出 editorial_summary)
         │
         ▼
    [PROCESSED]   ── (寫回 Google Sheets)

```

實作管線編排程式碼：

```python
# src/services/pipeline.py
import logging
from google import genai

from src.core.models import IntelligenceItem, ItemStatus
from src.agents.reviewer import ReviewerAgent
from src.agents.domain_expert import DomainExpertAgent
from src.agents.synthesizer import SynthesizerAgent
from src.agents.editor import EditorAgent

logger = logging.getLogger(__name__)

class IntelligencePipeline:
    def __init__(self, client: genai.Client):
        self.reviewer = ReviewerAgent(client)
        self.expert = DomainExpertAgent(client)
        self.synthesizer = SynthesizerAgent(client)
        self.editor = EditorAgent(client)

    def process_item(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        執行單一條目的完整多代理人串接管線。
        """
        logger.info(f"開始處理情資 [{item.entry_id}]: {item.source_title}")

        # 1. 守門員審核與 Early-exit 分流
        item, should_continue = self.reviewer.evaluate(item)
        if not should_continue:
            logger.warning(f"條目 [{item.entry_id}] 未達門檻 (得分: {item.raw_score})，熔斷歸檔。")
            return item

        # 2. 領域專家深度剖析
        logger.info(f"條目 [{item.entry_id}] 通過初審，進入 Domain Expert 深入萃取。")
        item = self.expert.analyze(item)

        # 3. 綜合研判與二階推演
        logger.info(f"條目 [{item.entry_id}] 進入 Synthesizer 進行跨領域影響推演。")
        item = self.synthesizer.synthesize(item)

        # 4. 總編定稿與排版成型
        logger.info(f"條目 [{item.entry_id}] 進入 Editor 進行最終摘要定稿。")
        item = self.editor.edit(item)

        # 5. 標記處理完成
        item.status = ItemStatus.PROCESSED
        logger.info(f"條目 [{item.entry_id}] 流水線全流程執行完畢，狀態切換為 PROCESSED。")
        return item

```

---

## 端到端整合驗證與實戰

在最外層的進入點（如定時排程執行的 Worker），只需透過 `SheetsAdapter` 與 `IntelligencePipeline` 相互協同即可完成無人值守運作：

```python
# run_pipeline.py
import os
from google import genai
from src.adapters.sheets_adapter import SheetsAdapter
from src.services.pipeline import IntelligencePipeline

def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    sheets_adapter = SheetsAdapter()
    pipeline = IntelligencePipeline(client)

    # 1. 拉取 PENDING 狀態資料並自動加鎖為 ANALYZING
    pending_items = sheets_adapter.fetch_pending_items(auto_lock=True)
    print(f"成功鎖定待處理情報數量: {len(pending_items)}")

    # 2. 依序通過多代理人管線並寫回
    for item in pending_items:
        try:
            processed_item = pipeline.process_item(item)
            sheets_adapter.update_item_status(processed_item)
            print(f"條目 {processed_item.entry_id} 處理回填成功（狀態: {processed_item.status}）")
        except Exception as e:
            print(f"條目 {item.entry_id} 處理異常: {str(e)}")
            item.status = "ERROR"
            item.metadata["pipeline_error"] = str(e)
            sheets_adapter.update_item_status(item)

if __name__ == "__main__":
    main()

```

---

## 架構效益結算

1. **職責極致分離（Single Responsibility）**：每個 Agent 各司其職，Reviewer 專注門檻、Expert 專注解構、Synthesizer 專注推演、Editor 專注文風。任何一個環節的 Prompt 需要微調，都不會干擾其他節點。
2. **熔斷保護（Fail-fast）**：低於 60 分的雜訊在第一道 Reviewer 即被中斷並標記 `ARCHIVED`，後續三個高運算節點直接略過，省下大量 Token 與 API 費用。
3. **無縫對接外部轉接器**：整個流水線完全操作 `IntelligenceItem` 純記憶體模型，透過 `SheetsAdapter` 統一完成讀寫，完美體現六角架構外層依賴內層的解耦優勢。

明天 **Day 17**，我們將進入「第四階段：自動化部署與維運實戰」，介紹如何將這套管線封裝進 GitHub Actions 與無伺服器排程中，實現真正零成本的無人值守日常巡航！