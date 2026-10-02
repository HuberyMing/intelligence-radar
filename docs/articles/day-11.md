### Day 11：中繼轉接器封裝：實作 SheetsAdapter 核心讀寫與狀態鎖定

在 Day 10，我們透過 Google Cloud 服務帳號打通了遠端連線，並驗證了 Google Sheets 的讀寫能力。然而，在昨天的煙霧測試中，我們是直接在腳本中裸寫 `gspread` 的底層 API。

在六角架構（Hexagonal Architecture）中，**領域核心（Domain）絕對不能直接依賴第三方套件或特定的儲存實作**。如果未來我們想從 Google Sheets 遷移到 PostgreSQL、Redis 或本機 DuckDB，散落在各處的 `worksheet.append_row()` 將會引發災難性的重構。

今天我們要將資料庫操作徹底物件化，封裝出高內聚、低耦合的 **`SheetsAdapter`（外接口轉接器）**，並實作最關鍵的「狀態鎖定」邏輯！

---

**一、 為什麼需要「狀態鎖定（State Locking）」？**

在非同步多代理人架構中，Google Sheets 扮演的是訊息佇列（Message Queue）。
當後端 ADK 排程啟動時，它必須拉取所有標記為 `PENDING` 的情報。

若直接撈取而不改動狀態，當系統有多個 Worker 並行或排程短時間內重複觸發時，就會發生**競爭條件（Race Condition）**——同一篇論文被兩台代理人重複分析兩次，白白浪費推論 Token。

因此，`SheetsAdapter` 必須提供原子性思維的鎖定操作：

1. **讀取（Fetch）**：撈取 `status == "PENDING"` 的條目。
2. **鎖定（Lock）**：在交付給代理人分析前，**立刻將試算表中的狀態就地更新為 `ANALYZING**`，完成鎖定保護。

---

**二、 落地實作：`src/adapters/sheets_adapter.py`**

在 `src/adapters/` 目錄下建立 `sheets_adapter.py`，完整整合 Day 05 的資料模型、Day 09 的序列化器與 Day 10 的認證機制：

```python
# src/adapters/sheets_adapter.py
import json
from typing import List, Optional
import gspread
from google.oauth2.service_account import Credentials

from src.core.harmonizer import DataHarmonizer, SheetSerializer
from src.core.models import IntelligenceItem, ItemStatus


class SheetsAdapter:
    """Google Sheets 外部轉接器：提供符合領域模型的強型別資料庫操作介面"""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(
        self,
        credentials_path: str = "service_account.json",
        spreadsheet_name: str = "Intelligence_Radar_Hub",
        worksheet_name: str = "raw_feed",
    ):
        creds = Credentials.from_service_account_file(
            credentials_path, scopes=self.SCOPES
        )
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open(spreadsheet_name)
        self.worksheet = self.sheet.worksheet(worksheet_name)

    def append_item(self, item: IntelligenceItem) -> None:
        """寫入單一標準情報條目至試算表末端"""
        row_data = SheetSerializer.to_row(item)
        self.worksheet.append_row(row_data)

    def fetch_pending_items(self, auto_lock: bool = True) -> List[IntelligenceItem]:
        """
        拉取所有待處理 (PENDING) 條目
        若 auto_lock=True，則在回傳前就地將試算表狀態改為 ANALYZING 進行鎖定
        """
        all_records = self.worksheet.get_all_records()
        pending_items: List[IntelligenceItem] = []
        rows_to_lock: List[int] = []

        # Google Sheets 列號由 1 開始，Row 1 為表頭，故資料從 Row 2 起算
        for idx, record in enumerate(all_records, start=2):
            if record.get("status") == ItemStatus.PENDING.value:
                # 反序列化 metadata
                raw_meta = record.get("metadata", "{}")
                metadata_dict = (
                    json.loads(raw_meta) if isinstance(raw_meta, str) and raw_meta else {}
                )
                record["metadata"] = metadata_dict

                # 透過 Harmonizer 驗證還原為強型別物件
                item = DataHarmonizer.normalize(record)
                pending_items.append(item)
                rows_to_lock.append(idx)

        # 狀態鎖定：防止多 Worker 重複處理
        if auto_lock and rows_to_lock:
            # 狀態欄位固定位於第 C 欄 (Column 3)
            cell_updates = [
                gspread.Cell(row=r, col=3, value=ItemStatus.ANALYZING.value)
                for r in rows_to_lock
            ]
            self.worksheet.update_cells(cell_updates)

        return pending_items

    def update_item_status(
        self,
        entry_id: str,
        new_status: ItemStatus,
        verified_score: Optional[int] = None,
        editorial_summary: Optional[str] = None,
        cross_impact_notes: Optional[str] = None,
    ) -> bool:
        """
        依據 entry_id 定位資料行，並回填 ADK 推演層產出的審核結果
        """
        # 尋找 entry_id (位於 A 欄，Column 1)
        cell = self.worksheet.find(entry_id, in_column=1)
        if not cell:
            return False

        row = cell.row
        # 準備批次更新的儲存格清單
        updates = [
            gspread.Cell(row=row, col=3, value=new_status.value)  # status
        ]
        if verified_score is not None:
            updates.append(gspread.Cell(row=row, col=12, value=verified_score))
        if editorial_summary is not None:
            updates.append(gspread.Cell(row=row, col=13, value=editorial_summary))
        if cross_impact_notes is not None:
            updates.append(gspread.Cell(row=row, col=14, value=cross_impact_notes))

        self.worksheet.update_cells(updates)
        return True

```

---

**三、 撰寫測試驗證：狀態機鎖定與回填實測**

在專案根目錄建立 `test_adapter_workflow.py`，模擬一次完整的生命週期流轉：

```python
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
success = adapter.update_item_status(
    entry_id=locked_item.entry_id,
    new_status=ItemStatus.PROCESSED,
    verified_score=5,
    editorial_summary="資深編輯確認：狀態鎖定機制運行完美，具備生產級強健度。",
    cross_impact_notes="可推廣至後續所有非同步 Agent 排程管線。",
)
assert success is True
print("🎉【驗證完成】請至 Google Sheets 查看該行資料：狀態轉綠 (PROCESSED)，第 L、M、N 欄已精確回填！")

```

執行 `python test_adapter_workflow.py`，你將親眼目睹儲存格經歷 `PENDING` ➔ `ANALYZING` ➔ `PROCESSED` 的完整流轉！

---

**今日小結與明天預告**

今天我們完成了「中繼轉接器封裝」，透過物件導向與六角架構設計，將試算表的低階 CRUD 提升為具備狀態機防呆與型別約束的領域操作介面。

至此，**「第二階段：前端邊緣收集與工作空間」正式圓滿落幕！**

明天開始，我們將昂首挺胸跨入全系列的核心重頭戲——**「第三階段：Google ADK 多代理人核心建置」**！
在 **Day 12** 中，我們將剖析 Google ADK 的系統架構，完成本地 ADK 環境初始化，並定義協同思考的多代理人分工藍圖！