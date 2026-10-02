### Day 04：開發環境配置：Google AI Studio API Key 與本機 Python 虛擬環境

在昨天定好系統資料流與狀態機的規格後，今天我們正式挽起袖子，把本地開發環境與 Google 模型端點打通。

很多初學者一提到「串接 Google Gemini 模型」，直覺就是去 GCP（Google Cloud Platform）開關繁雜的 IAM 權限、綁定信用卡帳單。但在原型驗證與個人決策雷達的開發階段，**最輕量、最敏捷的途徑是透過 Google AI Studio**。

---

**一、 透過 Google AI Studio 取得免費 API Key**

Google AI Studio 是 Google 提供給開發者的模型沙盒與 API 入口，具備相當慷慨的免費用量層（Free Tier），非常適合拿來跑初期測試。

1. 前往 [Google AI Studio](https://aistudio.google.com/?utm_source=gemini)，使用 Google 帳號登入。
2. 點擊左側導覽列的 **「Get API key」** ➔ **「Create API key」**。
3. 複製生成的 API Key。**切記不要直接寫死在程式碼中或推上公開 GitHub Repo**。

---

**二、 本機 Python 隔離環境搭建**

為了避免與系統其他專案的套件版本衝突，我們使用 Python 內建的 `venv` 建立乾淨的虛擬環境。

打開終端機，依序執行：

```bash
# 1. 建立並切換至專案根目錄
mkdir intelligence-radar && cd intelligence-radar

# 2. 建立 Python 虛擬環境 (建議 Python 3.10+)
python3 -m venv .venv

# 3. 啟動虛擬環境
source .venv/bin/activate

# 4. 升級 pip 並安裝核心套件
pip install --upgrade pip
pip install google-adk pydantic python-dotenv requests

```

---

**三、 集中管理環境變數（`.env`）**

在專案根目錄建立 `.env` 檔案。注意：新建立的 Google AI Studio API Key 必須指定當前官方標準模型（如 `gemini-3.6-flash`）：

```bash
# .env
GEMINI_API_KEY="AIzaSyYourActualKeyHere..."
DEFAULT_MODEL="gemini-3.6-flash"

```

同時務必建立 `.gitignore`，防止金鑰意外洩漏：

```text
# .gitignore
.venv/
.env
__pycache__/
*.pyc

```

---

**四、 實戰排坑：為什麼我們採用 REST 架構進行連線？**

在環境搭建過程中，開發者常遇到兩個典型暗坑：

1. **模型棄用與權限問題 (404 NOT_FOUND)**：舊文件常標註 `gemini-2.5-flash`，但新註冊的 API Key 會被強制導向到最新一代模型（如 `gemini-3.6-flash`），否則會直接回傳 404 錯誤。
2. **SDK 連線掛起 (Read Operation Timed Out)**：高版本 Python（如 3.13）在特定作業系統下，高階 SDK 底層的連線池或 gRPC 握手偶爾會發生逾時卡死。

在軟體工程中，**「保持依賴最小化」是構建穩健系統的核心原則**。我們直接使用標準 HTTP REST 端點進行連線驗證，不僅秒級響應，而且未來封裝成 `ILLMProvider` 介面時更輕量、更好維護。

建立煙霧測試腳本 `test_connection.py`：

```python
import os
import requests
from dotenv import load_dotenv

# 1. 載入環境變數
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("DEFAULT_MODEL", "gemini-3.6-flash")

if not api_key:
    raise ValueError("❌ 找不到 GEMINI_API_KEY，請確認 .env 檔案設定！")

# 2. 組合 Google 官方標準 REST 端點
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
headers = {"Content-Type": "application/json"}
payload = {
    "contents": [{
        "parts": [{"text": "請用繁體中文回覆一句：『Google Gemini API 連線測試成功！』"}]
    }]
}

print(f"📡 正在發送 REST 請求至 {model}...")

try:
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    
    reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    print("\n🎉【連線成功！】模型回應：")
    print(reply.strip())

except Exception as e:
    print(f"\n❌ 連線失敗: {e}")

```

執行 `python test_connection.py`，終端機若印出模型的回應，即代表本地開發基座正式打通！

---

**今日小結與明天預告**

今天我們完成了 API Key 申請、隔離虛擬環境，並繞過 SDK 底層連線問題，以乾淨的 REST 架構驗證了 Gemini 模型端點。

明天（Day 05），我們將把 Day 03 定義的資料契約落地，使用 Python 的 **Pydantic** 實作強型別的 Schema 驗證模組！
