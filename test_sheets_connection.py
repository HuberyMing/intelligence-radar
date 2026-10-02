import gspread
from google.oauth2.service_account import Credentials

# 1. 定義授權範圍 (Scope)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 2. 載入服務帳號憑證
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_NAME = "Intelligence_Radar_Hub"
WORKSHEET_NAME = "raw_feed"

print("🔑 正在載入 Service Account 憑證...")
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

try:
    print(f"📡 正在連線至 Google Sheets: [{SPREADSHEET_NAME}]...")
    sheet = client.open(SPREADSHEET_NAME)
    worksheet = sheet.worksheet(WORKSHEET_NAME)
    
    # 讀取現有表頭 (Row 1)
    headers = worksheet.row_values(1)
    print(f"\n🎉【連線成功！】目前工作表 [{WORKSHEET_NAME}] 的表頭為：")
    print(headers)

    # 執行一次安全的末端追加測試 (Append Row)
    print("\n✍️ 正在測試寫入一筆連線驗證資料...")
    test_row = [
        "test_001",
        "2026-09-24 15:30:00",
        "PENDING",
        "COMMUNITY",
        "Test_Track",
        "機器人連線權限驗證成功",
        "https://example.com",
        "這是一筆由 service_account 自動寫入的測試資料",
        "", "", "3", "", "", "", "{}"
    ]
    worksheet.append_row(test_row)
    print("✅ 寫入成功！請立刻打開瀏覽器查看試算表是否多了一列資料！")

except Exception as e:
    print(f"\n❌ 連線或寫入失敗: {e}")
    