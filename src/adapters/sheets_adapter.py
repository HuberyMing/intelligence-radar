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
    