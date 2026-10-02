# tests/test_models.py
import pytest
from pydantic import ValidationError

from src.core.models import DomainType, IntelligenceItem, ItemStatus


def test_valid_item_creation():
    """測試正常建立條目"""
    item = IntelligenceItem(
        domain=DomainType.SCIENCE,
        track="AI_Frontier",
        source_title="Scaling State Space Models to 100B Parameters",
        source_url="https://arxiv.org/abs/xxxx.xxxxx",
        raw_content="提出新型硬體感知 Mamba 架構，推論顯存大幅降低...",
        raw_score=4,
        metadata={"arxiv_id": "2609.12345", "authors": ["Alice", "Bob"]}
    )

    assert item.status == ItemStatus.PENDING
    assert item.raw_score == 4
    assert len(item.entry_id) == 8
    assert item.metadata["arxiv_id"] == "2609.12345"


def test_invalid_score_boundary():
    """測試評分越界防呆 (必須在 1-5 之間)"""
    with pytest.raises(ValidationError):
        IntelligenceItem(
            domain=DomainType.FINANCE,
            track="Macro_Econ",
            source_title="US 10Y Yield Jumps",
            source_url="https://bloomberg.com/...",
            raw_content="殖利率上升...",
            raw_score=6  # 故意超出 5 分上限
        )