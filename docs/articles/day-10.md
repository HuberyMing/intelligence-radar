### Day 10：打通雲端管線：Google Cloud 服務帳號設定與 Sheets API 授權

在 Day 07，我們在 Google Sheets 上完成了 15 欄位資料庫與狀態機標籤的設計，並在 Day 09 透過 `DataHarmonizer` 確保了所有收集資料的型別相容性。

然而，截至目前為止，我們的試算表仍只能由人類透過瀏覽器手動檢視。為了讓後續的 Python Worker 與 ADK 推理管線能夠「無人值守」自動讀寫，今天我們將為系統取得合法的機器人通行證——**Google Cloud 服務帳號（Service Account）**，並正式打通遠端讀寫權限！

---

**一、 為什麼不能用個人帳號？認識 Service Account**

許多開發者在串接 Google 服務時，直覺會使用 OAuth 2.0（每次彈跳視窗要求使用者點擊「允許」）。但對於後端自動化系統、定時爬蟲與多代理人排程而言，不可能有人隨時在螢幕前等待授權。

* **OAuth 2.0 Client**：代表「使用者本人」，適合桌面應用程式或需要取得特定用戶個人授權的服務。
* **Service Account（服務帳號）**：代表「應用程式機器人自身」。它擁有獨立的金鑰憑證與專屬的機器人信箱（`xxxx@xxxx.iam.gserviceaccount.com`）。我們只需將 Google Sheets 當成一般文件「共用（Share）」給該信箱，程式碼就能以編輯者身分全天候自由存取。

---

**二、 實戰指南：取得 Google 機器人憑證四步法**

1. **建立 GCP 專案**：
* 前往 [Google Cloud Console](https://console.cloud.google.com/?utm_source=gemini)。
* 點擊頂部導覽列左側 **「Google Cloud」標誌右方的專案挑選器（Project Picker，快捷鍵 `⌘ + O`）**，點選彈出視窗右上角的 **「新增專案 (New Project)」**。
* 專案名稱填入 `intelligence-radar`，完成建立並切換至該專案。

2. **啟用核心 API 服務**：
* 展開左側選單 ➔ **「API 和服務」** ➔ **「程式庫 (Library)」**。
* 依序搜尋並啟用：
* **`Google Sheets API`**（提供試算表讀寫支援）
* **`Google Drive API`**（授權程式依試算表名稱搜尋與定位檔案）


3. **建立服務帳號並下載金鑰**：
* 進入 **「IAM 與管理員」** ➔ **「服務帳號 (Service Accounts)」** ➔ 點擊 **「＋ 建立服務帳號」**。
* 命名為 `sheets-writer`，連續點選「建立並繼續」完成初始設定。
* 在清單中點擊該帳號 ➔ 切換至 **「金鑰 (Keys)」** 分頁 ➔ **「新增金鑰」 ➔ 「建立新的金鑰」 ➔ 選擇 JSON**。
* 將下載的 JSON 檔案重新命名為 `service_account.json`，並移至本機專案根目錄。


4. **授權試算表權限**：
* 打開 `service_account.json`，複製其中的 `"client_email"` 欄位值。
* 打開 Day 07 建立的 `Intelligence_Radar_Hub` 試算表，點擊右上角 **「共用 (Share)」**。
* 貼上機器人信箱，角色選為 **「編輯者 (Editor)」**，取消勾選通知後完成共用。



> **資安防呆提醒**：金鑰檔案包含完整操作權限，請立刻確認專案的 `.gitignore` 包含 `service_account.json`，嚴防金鑰意外推上公開儲存庫。

---

**三、 驗證遠端管線：撰寫煙霧測試腳本**

安裝官方相容的高階存取封裝庫：

```bash
pip install gspread google-auth

```

在專案根目錄建立 `test_sheets_connection.py`，驗證憑證有效性並測試寫入首筆資料：

```python
# test_sheets_connection.py
import gspread
from google.oauth2.service_account import Credentials

# 1. 配置授權範圍 (Scopes)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

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
    
    # 讀取現有表頭
    headers = worksheet.row_values(1)
    print(f"\n🎉【連線成功！】目前工作表表頭共有 {len(headers)} 欄：")
    print(headers)

    # 執行末端追加 (Append Row) 驗證
    print("\n✍️ 正在測試寫入連線驗證資料...")
    test_row = [
        "test_001",
        "2026-09-24 15:30:00",
        "PENDING",
        "COMMUNITY",
        "Test_Track",
        "機器人連線權限驗證成功",
        "https://example.com",
        "這是一筆由 service_account 自動寫入的測試資料",
        "", "", 3, "", "", "", "{}"
    ]
    worksheet.append_row(test_row)
    print("✅ 寫入成功！請檢視試算表是否即時新增資料行。")

except Exception as e:
    print(f"\n❌ 連線或寫入失敗: {e}")

```

執行 `python test_sheets_connection.py`，終端機回傳完整的 15 欄表頭並順利追加資料列，代表本地環境與雲端資料庫之間的專屬網路管線已正式暢通無阻！

---

**今日小結與明天預告**

今天我們完成了「雲端中繼通道打通」，透過 GCP Service Account 讓程式碼取得穩健且安全的雲端讀寫能力。

明天（**Day 11**），我們將依循六角架構，撰寫專門的 **`SheetsAdapter`（外接口轉接器）**，將 Day 09 的 `DataHarmonizer` 與今天的遠端連線合體，提供 `fetch_pending_items()` 與 `update_item_status()` 等核心高階方法，宣告第二階段大功告成！
