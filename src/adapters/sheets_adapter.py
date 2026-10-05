# src/adapters/sheets_adapter.py
import json
import os
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
        # 1. 優先取用環境變數指定之憑證路徑，本地預設退回 service_account.json
        sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", credentials_path)
        if not os.path.exists(sa_path):
            raise FileNotFoundError(f"找不到服務帳號金鑰檔案: {sa_path}")

        creds = Credentials.from_service_account_file(sa_path, scopes=self.SCOPES)
        self.client = gspread.authorize(creds)

        # 2. 優先支援 SPREADSHEET_ID (open_by_key)，若無則依名稱開啟 (相容舊版)
        spreadsheet_id = os.getenv("SPREADSHEET_ID")
        if spreadsheet_id:
            self.sheet = self.client.open_by_key(spreadsheet_id)
        else:
            self.sheet = self.client.open(spreadsheet_name)

        # 3. 綁定工作表
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

    # src/adapters/sheets_adapter.py (推薦的重構實作) 風格 B：豐富領域模型簽章
    def update_item_status(
        self,
        item: IntelligenceItem,
        new_status: Optional[ItemStatus] = None
    ) -> bool:
        """
        接收領域模型物件，自動取用其最新數據回填至 Google Sheets
        """
        # 若有指定新狀態則覆寫，否則沿用 item 自身狀態
        status_to_write = new_status or item.status
        
        # 內部直接從 item 提取各欄位，外界呼叫極致簡潔
        target_row = self._find_row_by_entry_id(item.entry_id)
        if not target_row:
            return False

        # 批次更新狀態、評分、總編摘要與推演筆記 (L, M, N 欄位)
        update_cells = [
            {"range": f"C{target_row}", "values": [[status_to_write.value if hasattr(status_to_write, 'value') else str(status_to_write)]]},
            {"range": f"L{target_row}", "values": [[item.verified_score or item.raw_score]]},
            {"range": f"M{target_row}", "values": [[item.editorial_summary or ""]]},
            {"range": f"N{target_row}", "values": [[item.cross_impact_notes or ""]]},
        ]
        self.worksheet.batch_update(update_cells)
        return True
