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