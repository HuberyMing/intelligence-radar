# tests/adapters/test_obsidian_adapter.py
from pathlib import Path

from src.adapters.obsidian_adapter import ObsidianVaultAdapter
from src.core.models import IntelligenceItem


def test_obsidian_sync_success(tmp_path: Path, sample_intelligence_item: IntelligenceItem):
    """驗證筆記檔案能夠正確生成，且 YAML Frontmatter 內容符合規格"""
    adapter = ObsidianVaultAdapter(vault_path=tmp_path, subfolder="Radar_Inbox")
    
    # 執行同步
    success = adapter.sync_item(sample_intelligence_item, overwrite=False)
    
    assert success is True
    
    # 檢查目標檔案是否存在
    expected_files = list((tmp_path / "Radar_Inbox").glob("*.md"))
    assert len(expected_files) == 1
    
    note_path = expected_files[0]
    content = note_path.read_text(encoding="utf-8")
    
    # 驗證核心屬性與 Markdown 結構
    assert 'id: "test_abc123"' in content
    assert 'domain: "SCIENCE"' in content
    assert 'score: 5' in content
    assert "> [!abstract] 核心提煉" in content
    assert "動態狀態鎖定協議" in content
    assert "[[SCIENCE]]" in content

def test_obsidian_filename_sanitization(tmp_path: Path, sample_intelligence_item: IntelligenceItem):
    """驗證標題包含作業系統非法字元時，能被安全清洗且不引發異常"""
    sample_intelligence_item.source_title = 'What is "AGI"?: A/B Testing & Scaling*Rules'
    adapter = ObsidianVaultAdapter(vault_path=tmp_path, subfolder="Radar_Inbox")
    
    success = adapter.sync_item(sample_intelligence_item)
    assert success is True
    
    generated_file = list((tmp_path / "Radar_Inbox").glob("*.md"))[0]
    filename = generated_file.name
    
    # 確認非法字元已全數拔除
    for char in ['"', '?', ':', '/', '*', '<', '>', '|']:
        assert char not in filename

def test_obsidian_idempotency_skip(tmp_path: Path, sample_intelligence_item: IntelligenceItem):
    """驗證冪等性：當檔案已存在且未指定 overwrite 時，應優雅略過並回傳 False"""
    adapter = ObsidianVaultAdapter(vault_path=tmp_path, subfolder="Radar_Inbox")
    
    # 首次寫入
    first_run = adapter.sync_item(sample_intelligence_item, overwrite=False)
    assert first_run is True
    
    # 第二次重複寫入（不覆寫）
    second_run = adapter.sync_item(sample_intelligence_item, overwrite=False)
    assert second_run is False