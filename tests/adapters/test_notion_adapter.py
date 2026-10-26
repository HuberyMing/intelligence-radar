# tests/adapters/test_notion_adapter.py
from unittest.mock import patch

from notion_client.errors import APIResponseError

from src.adapters.notion_adapter import NotionSyncAdapter

# 使用合法的 32 碼假 UUID
MOCK_DB_ID = "3f44e1c203bf8097815fef01e424ddc1"

def test_notion_create_new_page(sample_intelligence_item):
    adapter = NotionSyncAdapter(auth_token="fake_token", database_id=MOCK_DB_ID)
    
    with patch.object(adapter, "_find_page_by_entry_id", return_value=None):
        with patch.object(adapter.client.pages, "create") as mock_create:
            mock_create.return_value = {"id": "new_page_999"}
            success = adapter.sync_item(sample_intelligence_item)
            assert success is True
            mock_create.assert_called_once()

def test_notion_update_existing_page(sample_intelligence_item):
    adapter = NotionSyncAdapter(auth_token="fake_token", database_id=MOCK_DB_ID)
    
    with patch.object(adapter, "_find_page_by_entry_id", return_value="existing_page_888"):
        # 測試 overwrite=False (預設略過)
        success_skip = adapter.sync_item(sample_intelligence_item, overwrite=False)
        assert success_skip is False
        
        # 測試 overwrite=True (執行更新)
        with patch.object(adapter.client.pages, "update") as mock_update:
            mock_update.return_value = {"id": "existing_page_888"}
            success_update = adapter.sync_item(sample_intelligence_item, overwrite=True)
            assert success_update is True
            mock_update.assert_called_once()


def test_notion_api_error_handling(sample_intelligence_item):
    adapter = NotionSyncAdapter(auth_token="fake_token", database_id=MOCK_DB_ID)
    
    # 繞過 __init__ 的參數限制，動態生成合法的 APIResponseError 實例
    mock_err = APIResponseError.__new__(APIResponseError)
    Exception.__init__(mock_err, "Mock Notion API 400 Bad Request")
    mock_err.code = "validation_error"
    mock_err.status = 400

    with patch.object(adapter, "_find_page_by_entry_id", return_value=None):
        with patch.object(adapter.client.pages, "create", side_effect=mock_err):
            success = adapter.sync_item(sample_intelligence_item)
            # 驗證：遇到 API 異常時是否安全捕捉並回傳 False
            assert success is False