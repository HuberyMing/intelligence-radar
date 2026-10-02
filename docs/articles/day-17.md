### Day 17：合約測試與 GitHub Actions CI 自動化守門：打造零 Token 成本的防護網

在 Day 16 中，我們成功串接了 Reviewer、Domain Expert、Synthesizer 與 Editor 四大多代理人節點，建立了完整的 `IntelligencePipeline`。然而，隨著系統日漸複雜，軟體工程中最常面臨的兩大痛點也浮出水面：

1. **LLM 測試成本高昂且緩慢**：如果每次執行測試或推進程式碼都要真實發送 API 請求給 Gemini，不僅會快速耗盡開發配額，測試速度也會被網路與推論延遲拖垮。
2. **Schema 隱性破壞**：一旦工程師微調了某個 Pydantic 模型的欄位或驗證邊界，若未及時發現，可能導致 LLM 生成的 JSON 與下游資料庫或 Google Sheets 的解析器脫節。

本篇將實作系統的軟體工程護城河：透過 **資料契約測試（Contract Testing）**、**離線 Mock 測試**，以及 **GitHub Actions CI 自動化檢查**，在完全不消耗任何 API Token 的前提下，打造 100% 確定性的自動化品質守門機制。

---

## 測試策略：分層驗證金字塔

在 LLM 代理人系統中，測試應分為兩個維度：

* **資料契約層（Contract Layer）**：檢驗 Pydantic 模型能否正確限制數值邊界（如 `0 <= score <= 100`）、字串枚舉（`Literal`），以及是否正確導出給 LLM 閱讀的 OpenAPI/JSON Schema。
* **管線狀態層（Pipeline Layer）**：利用 `unittest.mock` 模擬 LLM 的回傳，驗證核心的 **Early-exit 熔斷機制** 與狀態機轉移。

```
       ▲
      / \     [Pipeline Mock 測試]  -> 驗證狀態機轉移與 Early-exit 熔斷 (零成本)
     /   \
    /     \   [資料契約測試 (Schema)] -> 驗證 Pydantic 邊界與 JSON Schema 導出
   /-------\

```

---

## 模組一：資料契約測試（Contract Testing）

我們建立 `tests/test_agents_schema.py`，專門測試代理人間傳遞的資料結構契約：

```python
# tests/test_agents_schema.py
import pytest
from pydantic import ValidationError

from src.agents.domain_expert import ExpertAnalysisResult
from src.agents.reviewer import ReviewResult
from src.core.models import IntelligenceItem


class TestAgentSchemas:
    """驗證多代理人輸出資料契約 (Data Contract) 的邊界約束與 Schema 產出"""

    def test_review_result_valid(self):
        """測試正常的 ReviewResult 實例化與預設容器工廠"""
        data = {
            "raw_score": 75,
            "decision": "PASS",
            "reason": "具備詳盡量化對比測試"
        }
        result = ReviewResult.model_validate(data)
        assert result.raw_score == 75
        assert result.decision == "PASS"
        assert result.key_metrics_found == []

    def test_review_result_score_boundary_and_literal(self):
        """測試分數邊界 (0-100) 與 Literal 枚舉防禦"""
        # 超出評分上限 (le=100)
        with pytest.raises(ValidationError):
            ReviewResult(raw_score=105, decision="PASS", reason="Valid")

        # 低於評分下限 (ge=0)
        with pytest.raises(ValidationError):
            ReviewResult(raw_score=-1, decision="PASS", reason="Valid")

        # 決策非合約內的 PASS/DROP (驗證 Literal 防禦)
        with pytest.raises(ValidationError):
            ReviewResult(raw_score=80, decision="INVALID_DECISION", reason="Valid")

    def test_expert_analysis_result_validation(self):
        """測試專家節點提取之欄位完整性與必填欄位"""
        payload = {
            "verified_score": 85,
            "key_metrics": ["MMLU: 82.4%", "Latency: 12ms/tok"],
            "limitations": ["僅支援 FP8，需 Ada Lovelace 架構顯卡"],
            "technical_takeaway": "透過自適應量化顯著降低推論延遲"
        }
        expert_obj = ExpertAnalysisResult.model_validate(payload)
        assert len(expert_obj.key_metrics) == 2
        assert "FP8" in expert_obj.limitations[0]

        # 缺少必填欄位 (Field(...)) 應觸發 ValidationError
        incomplete_payload = payload.copy()
        del incomplete_payload["limitations"]
        with pytest.raises(ValidationError):
            ExpertAnalysisResult.model_validate(incomplete_payload)

    def test_json_schema_contains_required_fields(self):
        """確保導出的 JSON Schema 確實將 Field(...) 標記為 required"""
        schema = ReviewResult.model_json_schema()
        assert "raw_score" in schema["required"]
        assert "decision" in schema["required"]
        assert "reason" in schema["required"]
        # key_metrics_found 具備預設值，不應出現在 required 陣列中
        assert "key_metrics_found" not in schema.get("required", [])
        # 驗證 Literal 是否轉換為 JSON Schema 的 enum
        assert schema["properties"]["decision"]["enum"] == ["PASS", "DROP"]

# 加在 tests/test_agents_schema.py 裡面

def test_intelligence_item_strict_contract_violation():
    """展示六角核心模型對非法 domain 與越界評分的嚴格攔截 (Negative Testing)"""
    
    # 測試 1：非法 domain (例如傳入 'AI' 而非 'SCIENCE' | 'FINANCE' | 'COMMUNITY')
    with pytest.raises(ValidationError) as exc_info:
        IntelligenceItem(
            entry_id="TEST-ERR-1",
            timestamp="2026-10-01 10:00:00",
            domain="AI",  # 非法
            track="LLM",
            source_title="測試標題",
            source_url="https://example.com",
            raw_content="內容..."
        )
    assert "Input should be 'SCIENCE', 'FINANCE' or 'COMMUNITY'" in str(exc_info.value)

    # 測試 2：評分超出 5 分制邊界 (例如傳入 45)
    with pytest.raises(ValidationError) as exc_info:
        IntelligenceItem(
            entry_id="TEST-ERR-2",
            timestamp="2026-10-01 10:00:00",
            domain="SCIENCE",
            track="LLM",
            source_title="測試標題",
            source_url="https://example.com",
            raw_content="內容...",
            raw_score=45  # 違反 le=5
        )
    assert "Input should be less than or equal to 5" in str(exc_info.value)

    # 加在 tests/test_agents_schema.py 的 test_intelligence_item_strict_contract_violation 內
    with pytest.raises(ValidationError) as exc_info:
        IntelligenceItem(
            entry_id="TEST-ERR-LOW",
            timestamp="2026-10-01 10:00:00",
            domain="SCIENCE",
            track="LLM",
            source_title="測試標題",
            source_url="https://example.com",
            raw_content="內容...",
            raw_score=0  # 違反 ge=1
        )
    assert "Input should be greater than or equal to 1" in str(exc_info.value)
```

---

## 模組二：Pipeline 離線模擬測試（Mocking Pipeline）

測試 Pipeline 的關鍵在於：**驗證在極端雜訊進入時，Early-exit 熔斷是否確實中斷了下游調用**。我們建立 `tests/test_pipeline.py`：

```python
# tests/test_pipeline.py
from unittest.mock import MagicMock

from src.core.models import IntelligenceItem, ItemStatus
from src.services.pipeline import IntelligencePipeline


def test_pipeline_early_exit_on_low_score():
    """驗證當 Reviewer 評分過低時，流水線立即熔斷，不觸發下游 Agent"""
    mock_client = MagicMock()
    pipeline = IntelligencePipeline(mock_client)

    # 1. 模擬 Reviewer 回傳未達標熔斷狀態 (raw_score=2)
    pipeline.reviewer.evaluate = MagicMock(return_value=(
        IntelligenceItem(
            entry_id="TEST-001",
            timestamp="2026-10-01 10:00:00",
            status=ItemStatus.ARCHIVED,
            domain="SCIENCE",
            track="LLM",
            source_title="低質量行銷稿",
            source_url="https://example.com/ad",
            raw_content="這是一個即將顛覆世界的革命性技術，但沒有任何數據...",
            raw_score=2,
            editorial_summary="[雜訊過濾歸檔] 缺乏量化數據與測試指標"
        ),
        False
    ))

    # 2. 將下游 Agent 設為 Spy
    pipeline.expert.analyze = MagicMock()
    pipeline.synthesizer.synthesize = MagicMock()
    pipeline.editor.edit = MagicMock()

    # 3. 初始 Dummy Item：傳入合法值 raw_score=1 (符合 ge=1, le=5)
    dummy_item = IntelligenceItem(
        entry_id="TEST-001",
        timestamp="2026-10-01 10:00:00",
        domain="SCIENCE",
        track="LLM",
        source_title="低質量行銷稿",
        source_url="https://example.com/ad",
        raw_content="內文...",
        raw_score=1
    )

    result = pipeline.process_item(dummy_item)

    # 4. 斷言檢查
    assert result.status == ItemStatus.ARCHIVED
    pipeline.expert.analyze.assert_not_called()
    pipeline.synthesizer.synthesize.assert_not_called()
    pipeline.editor.edit.assert_not_called()
```

---

## 模組三：配置 GitHub Actions CI 自動化工作流

為了確保每次提交程式碼或發起 Pull Request 時，程式碼品質與資料契約都能被自動檢查，我們建立 `.github/workflows/ci.yml`：

```yaml
# .github/workflows/ci.yml
name: Intelligence Radar CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  test:
    name: Run Lint & Contract Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov ruff
          pip install -r requirements.txt

      - name: Static Code Analysis (Ruff)
        run: |
          ruff check .

      - name: Execute Pytest Suite
        run: |
          pytest tests/ -v --cov=src --cov-report=term-missing

```

---

### 🛠️ 實戰踩坑與防禦精要：從 ValidationError、Linter 紀律到 Git 安全防線

在多代理人核心成型並引入 CI 自動化測試的過程中，我們真實經歷了四個極具代表性的工程洗禮：

#### 1. 契約防禦現場（Negative Testing）：1-5 級分與枚舉的絕對剛性

在編寫測試時，若隨意傳入 `domain="AI"` 或傳入非 5 分制的 `raw_score=45` 甚至 `raw_score=0`，Pydantic V2 會立即拋出 `ValidationError`：

```text
Input should be 'SCIENCE', 'FINANCE' or 'COMMUNITY' [type=enum]
Input should be less than or equal to 5 [type=less_than_equal]
Input should be greater than or equal to 1 [type=greater_than_equal]
```

這說明了六角架構核心模型（`IntelligenceItem`）的防禦力：**不管上游爬蟲或 LLM 回傳多混亂的字串，非預期的型態或越界數值在進入業務邏輯的第一時間就會被物理攔截**。在測試策略上，我們透過 `test_agents_schema.py` 進行負面測試（Negative Testing），徹底鎖死這些邊界。在單元測試設計中，我們應將這類「預期會失敗」的極限情境集中收斂於契約測試（`test_agents_schema.py`），而在流程測試中則專注驗證管線轉移。

#### 2. 必填欄位的初始化張力（Field required: raw_score）

當我們在測試中實例化一筆剛入庫的 `dummy_item` 時，若漏給 `raw_score`，同樣會觸發 `Field required` 錯誤。這反映了單一真相來源（SSOT）的設計原則：在情報條目尚未經過 Reviewer 評分前，必須給予合法的初始基準值（如 `raw_score=1`），而非放任其為 `None`，從而保障後續管線在傳遞過程中的型別安全。

#### 3. Linter 抓出隱性 Bug 與專案邊界劃分（Ruff 實戰）

在引入 Ruff 靜態檢查時，我們體會到現代 Linter 不只檢查排版，更能防範嚴重的執行期錯誤：

* **靜態抓出 NameError**：在編寫 Prompt 組合邏輯時，定義了 `limitations_block` 卻在字串模板中誤植為 `{limitations_str}`，Ruff 透過 `F821 (Undefined name)` 提前在本地捕捉到該隱患，免去了上線後 Python 拋出 `NameError` 的窘境。
* **生產代碼與探索腳本隔離（`pyproject.toml`）**：初期連線實驗檔（`test_connection/`）或一次性端到端驗證檔（`test_adapter_workflow.py`）不應干擾 CI 守門。我們透過 `pyproject.toml` 明確排除這些腳本，並放寬 Prompt 所需的行長限制（`E501`），讓 CI 聚焦於保護核心領域（`src/`）與標準測試（`tests/`）。

#### 4. Git Push 前的安全底線：拒絕憑證進版控

在完成本地全綠測試、準備推送到 GitHub 前，**`.gitignore` 是最後的生命線**：

* 必須徹底封鎖 `.venv/`、`service_account.json`、`*.json`（除 `package.json` 外）、`.env` 與快取檔案。
* 只有乾淨無金鑰的代碼庫才能推送到 GitHub，由雲端 GitHub Actions 虛擬機接手執行無狀態的自動化測試。

---

## 實務價值與成果驗證

1. **零 Token 與極速回饋**：整套測試套件在本地或 GitHub Actions 虛擬機中運行僅需 1 至 2 秒，完全不調用外部 Gemini API，實現真正的「零成本測試」。
2. **防禦性程式設計**：任何人在未來更動欄位（例如將 `raw_score` 門檻修改、更動欄位型別），CI 會第一時間報錯阻擋合併，確保分散式架構下的合約穩定性。

明天 **Day 18**，我們將把焦點轉向生產環境的維運實戰——**配置 GitHub Actions 排程巡航（Cron Schedule）與 GCP 服務帳號金鑰管理**，讓整個情報雷達真正在雲端全自動、無人值守地巡邏運轉！
