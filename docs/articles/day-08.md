### Day 08：雙軌收集之二：在 Colab 建立輕量 Python Worker（批次抓取 arXiv API 與 FRED 總經指標）

在 Day 06，我們運用了 Gemini Spark 擔任前哨長文巡邏兵，並在 Day 07 完成了 Google Sheets 的 15 欄標準資料庫架構。今天，我們要打造情報收集管線的「第二軌」——**在 Google Colab 部署輕量級 Python Worker**。

很多人建置 AI 專案時會有一個誤區：恨不得所有事情都交給大語言模型（LLM）處理。但身為架構師必須清楚一件事：**結構化數據與公開 API，用純 Python 爬蟲抓取才是速度最快、精準度最高、且成本為 0 的最佳選擇。**

---

**一、 為什麼第二軌選擇 Google Colab？**

1. **環境完全免維護**：內建齊全的網路請求庫（`requests`、`feedparser`），在瀏覽器中即可即時除錯與驗證。
2. **零成本雲端執行**：完全不需要開著本機筆電耗電，使用免費標準 CPU 執行階段（Runtime）即可跑完批次抓取。
3. **讀者體驗友好**：提供一個「Open in Colab」連結，讀者無須處理本機環境即可親眼見證資料採集流程。

---

**二、 實戰一：批次抓取 arXiv API 最新 AI 論文**

arXiv 提供了穩定的 Atom Feed API，我們可以直接篩選 `cs.AI` 或 `cs.CL` 領域最新發布的論文，提取標題、摘要、作者與 PDF 連結。

在 Colab 筆記本的第一個儲存格執行：

```python
import feedparser
import urllib.parse
from datetime import datetime, timezone

def fetch_latest_arxiv(category="cs.AI", max_results=3):
    """從 arXiv API 批次擷取最新論文並轉換為初步資料字典"""
    query = f"cat:{category}"
    url = f"https://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    
    print(f"📡 正在從 arXiv 抓取 [{category}] 最新 {max_results} 篇論文...")
    feed = feedparser.parse(url)
    items = []
    
    for entry in feed.entries:
        # 提取核心論文屬性
        title = entry.title.replace("\n", " ").strip()
        summary = entry.summary.replace("\n", " ").strip()
        paper_id = entry.id.split("/abs/")[-1]
        pdf_url = next((link.href for link in entry.links if link.type == 'application/pdf'), entry.link)
        authors = [a.name for a in entry.authors]
        
        items.append({
            "domain": "SCIENCE",
            "track": "AI_Frontier",
            "source_title": title,
            "source_url": entry.link,
            "raw_content": summary[:250] + "...",  # 擷取關鍵摘要
            "metrics": None,
            "limitations": None,
            "raw_score": 4,  # arXiv 頂級前沿預設基準分
            "metadata": {
                "arxiv_id": paper_id,
                "pdf_url": pdf_url,
                "authors": authors[:3],
                "collector": "Colab_arXiv_Worker"
            }
        })
    return items

# 測試執行
arxiv_results = fetch_latest_arxiv(max_results=2)
print(f"✅ 成功抓取 {len(arxiv_results)} 筆論文情報！")
```

---

**三、 實戰二：打通聖路易聯準銀 FRED API 獲取總經信號**

對於總體經濟趨勢，觀察**美國 10 年期國債殖利率（DGS10）**與**基準利率**是判斷全球資金流向的關鍵。FRED（Federal Reserve Economic Data）提供了官方免費 API。

在 Colab 中填入你的免費 FRED API Key（至 [stlouisfed.org](https://fred.stlouisfed.org/?utm_source=gemini) 即可 30 秒免費申請）：

```python
import requests

FRED_API_KEY = "你的_FRED_API_KEY"  # 可使用 Colab Secrets 管理

def fetch_fred_indicator(series_id="DGS10"):
    """抓取關鍵經濟指標最新數值 (例如 DGS10: 美國10年期公債殖利率)"""
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=2"
    
    print(f"📈 正在從 FRED 抓取指標 [{series_id}]...")
    resp = requests.get(url, timeout=10)
    data = resp.json()
    
    obs = data.get("observations", [])
    if len(obs) >= 2:
        latest_val = obs[0]["value"]
        latest_date = obs[0]["date"]
        prev_val = obs[1]["value"]
        
        # 計算變動幅度
        try:
            diff = round(float(latest_val) - float(prev_val), 3)
            diff_str = f"+{diff}" if diff > 0 else f"{diff}"
        except ValueError:
            diff_str = "N/A"
            
        return [{
            "domain": "FINANCE",
            "track": "Macro_Econ",
            "source_title": f"美國 10 年期公債殖利率 ({series_id}) 最新數據",
            "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
            "raw_content": f"最新觀測日期 {latest_date}，殖利率報 {latest_val}%，較前一期變動 {diff_str}%。",
            "metrics": f"現值: {latest_val}%, 變動: {diff_str} bps",
            "limitations": "單日高頻波動，需結合 CPI 與 FOMC 利率路徑觀察",
            "raw_score": 3,
            "metadata": {
                "series_id": series_id,
                "observation_date": latest_date,
                "collector": "Colab_FRED_Worker"
            }
        }]
    return []

# 測試執行
fred_results = fetch_fred_indicator("DGS10")
print(f"✅ 成功抓取 {len(fred_results)} 筆總經信號！")
```

使用 Colab Secrets 管理 API Key 的方式：
1. 點擊 Colab 左側工具欄的 鑰匙圖示 (Secrets)。
2. 點擊 "Add new secret"：
* Name：輸入 FRED_API_KEY
* Value：貼入你的 API Key 字串。
3. 關鍵開關：務必將該 Secret 旁邊的 "Notebook access"（筆記本存取權）開關切換為開啟（藍色）。
在程式碼中讀取：
```python
from google.colab import userdata
FRED_API_KEY = userdata.get('FRED_API_KEY')
```

---

**四、 架構對齊：雙軌成果匯流**

注意到了嗎？無論是從 arXiv 抓取的非同步論文資料，還是從 FRED 抓取的結構化數據，它們產出的 Dictionary 格式，**全部精準對齊了 Day 05 定義的欄位與結構！**

更重要的是：

* 特有的論文下載網址（`pdf_url`）與指標代碼（`series_id`），完全不需要更動 Google Sheets 的既有欄位，而是直接收納進 **`metadata` 彈性預留槽** 中。
* 這證明了我們先前在 Day 03 定下「核心定死、彈性留活」的強大擴充威力。

---

**今日小結與明天預告**

今天我們完成了「雙軌收集器」的建置，體會了純 Python 腳本在抓取 API 數據時的輕快與精準。

現在，我們手中已經有兩股水流：

1. **第一軌**：Gemini Spark 提煉的深度長文 JSON。
2. **第二軌**：Colab 批次拉取的結構化 API 資料。

明天（**Day 09**），我們將編寫「異構資料對齊轉換器」，將這兩軌不同來源的資料，自動補充 `entry_id`、`timestamp` 與 `PENDING` 狀態，正式合併注入我們的 Google Sheets 中繼基地！