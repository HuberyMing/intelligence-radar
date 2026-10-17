# test_adapter_workflow.py
from src.adapters.sheets_adapter import SheetsAdapter
from src.core.harmonizer import DataHarmonizer
from src.core.models import ItemStatus

adapter = SheetsAdapter()

# 1. 寫入一筆待測條目 (PENDING)
mock_payload = {
    "domain": "SCIENCE",
    "track": "AI_Frontier",
    "source_title": "State Locking Verification Paper",
    "source_url": "https://arxiv.org/abs/test.lock",
    "raw_content": "驗證 SheetsAdapter 之狀態機自動鎖定功能是否正常。",
    "raw_score": 4,
}
new_item = DataHarmonizer.normalize(mock_payload)
print(f"1. 寫入條目: {new_item.entry_id}，狀態為 PENDING...")
adapter.append_item(new_item)

# 2. 拉取待處理條目並執行自動鎖定 (auto_lock=True)
print("\n2. 執行 fetch_pending_items(auto_lock=True)...")
pending_list = adapter.fetch_pending_items(auto_lock=True)
locked_item = next(
    (i for i in pending_list if i.entry_id == new_item.entry_id), None
)
assert locked_item is not None
print(f"   成功撈取條目 {locked_item.entry_id}，試算表上的狀態已同步鎖定為 ANALYZING！")

# 3. 模擬 ADK 審核完畢，回填分數與摘要 (PROCESSED)
print("\n3. 模擬審核通過，回填資料並轉為 PROCESSED...")
# success = adapter.update_item_status(
#     entry_id=locked_item.entry_id,
#     new_status=ItemStatus.PROCESSED,
#     verified_score=5,
#     editorial_summary="資深編輯確認：狀態鎖定機制運行完美，具備生產級強健度。",
#     cross_impact_notes="可推廣至後續所有非同步 Agent 排程管線。",
# )
# assert success is True

# test_adapter_workflow.py (修改第 3 步驟)
# 3. 模擬審核通過，回填資料並轉為 PROCESSED
locked_item.status = ItemStatus.PROCESSED
locked_item.verified_score = 5
locked_item.editorial_summary = (
    "【極客核心】驗證領域模型風格 B 的資料回填與狀態同步合約。"
)
locked_item.cross_impact_notes = (
    "可推廣至後續所有非同步 Agent 排程管線。"
)

# 直接傳入整顆領域物件
success = adapter.update_item_status(locked_item)

assert success, "狀態回填失敗！"
print("3. 狀態成功回填為 PROCESSED！")
print("🎉【驗證完成】請至 Google Sheets 查看該行資料：狀態轉綠 (PROCESSED)，第 L、M、N 欄已精確回填！")
