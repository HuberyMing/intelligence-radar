# tests/conftest.py
from datetime import datetime
import pytest
from src.core.models import IntelligenceItem, ItemStatus

@pytest.fixture
def sample_intelligence_item() -> IntelligenceItem:
    """提供標準、完整的已處理高價值情資作為全域測試基準"""
    return IntelligenceItem(
        entry_id="test_abc123",
        timestamp=datetime(2026, 10, 12, 14, 30, 0),
        status=ItemStatus.PROCESSED,
        domain="SCIENCE",
        track="AI_Frontier",
        source_title="動態狀態鎖定協議：分散式代理人架構實作",
        source_url="https://arxiv.org/abs/2610.99999",
        raw_content="針對分散式多代理人系統，提出動態狀態鎖定協議，保證並發情境下狀態機的一致性。",
        metrics="吞吐量提升 45%，鎖定衝突率降低至 0.02%",
        limitations="跨節點網路延遲大於 200ms 時會降級為悲觀鎖",
        raw_score=5,
        verified_score=5,
        editorial_summary="技術審查：確認動態狀態鎖定協議兼具理論與實務價值，有效避免分散式管線重入衝突。",
        cross_impact_notes="動態狀態鎖定協議架構可直接搬移至金融高頻訂單簿與工業機器人協同調度。",
        metadata={"reviewer_decision": "PASS"}
    )