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