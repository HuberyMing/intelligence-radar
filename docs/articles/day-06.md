### Day 06：Gemini Spark 實戰：設定產經與專家社群長文巡邏技能（Skill & Schedule）

在前五天的架構鋪陳中，我們完成了系統藍圖、REST 連線驗證，以及透過 Pydantic 確立了全系統唯一的資料契約。今天，我們正式邁入「第二階段：前端邊緣收集與工作空間」！

今天的第一位主角，是擔任前哨偵察兵的 **Gemini Spark**。

---

**一、 為什麼前端收集需要 Gemini Spark？**

在構建情報雷達時，最耗費心力的往往不是後端模型推論，而是**前端的非結構化網頁爬取**：

* 專業深度長文（如 SemiAnalysis、Epoch AI、各類產業 Substack）通常沒有標準 API。
* 現代網頁充斥大量 JavaScript 動態渲染、Cookie 驗證與反爬蟲機制。
* 若自行使用 Headless Browser（如 Playwright / Puppeteer）維護，只要網站前端 DOM 結構一改版，爬蟲腳本就會掛掉。

**Gemini Spark 的核心優勢在於：將「網頁渲染、語意理解、資料提煉」打包為全託管的雲端巡邏能力。** 它像是一位不知疲倦的駐外研究助理，定期進入指定網站閱讀長文，並依照我們設定的 Schema 直接產出乾淨的結構化資料。

---

**二、 打造專屬巡邏技能（Spark Custom Skill）**

在 Gemini Spark 控制台中，我們可以透過定義 **System Instructions** 與 **Extraction Rules**，將 Day 05 確立的 `IntelligenceItem` 資料契約內化為 Spark 的思考準則。

進入 Spark 的 Skill 設定面板，填入以下配置：

```markdown
# Role & Objective
你是一名嚴謹的科技前沿與產業深度研究員。你的任務是巡邏指定來源最新發布的文章，過濾掉行銷公關稿與情緒化短評，提取具備高資訊密度、底層架構分析或關鍵數據推演的內容。

# Execution Rules
1. 嚴格對齊資料契約，僅輸出標準 JSON 陣列，嚴禁輸出任何前導問候語或結尾廢話。
2. 評分標準 raw_score (1-5)：
   - 5: 典範轉移級分析（如突破性架構評測、重大供應鏈結構性轉折）。
   - 4: 具備扎實第一手數據或深入供應鏈調研的高價值長文。
   - 3: 常規分析或觀點整理。
   - 1-2: 雜訊與公關宣傳（直接過濾，不輸出）。
3. 輸出欄位必須精確包含：domain, track, source_title, source_url, raw_content, metrics, limitations, raw_score。

```

---

**三、 自動化排程設定（Schedule & Ingestion）**

技能定義完成後，設定其執行週期與觸發條件：

1. **巡邏信源清單（Watchlist）**：
* **科技與架構**：Hugging Face Daily Papers、頂尖實驗室技術部落格。
* **產業與資本**：半導體深度專題、總經研究智庫。


2. **觸發頻率（Schedule）**：
* 設定為 **每日 UTC 00:00（台灣時間早晨 08:00）** 自動執行。
* 避開日間推論尖峰，確保在工作日開始前完成前哨掃描。


3. **輸出對齊**：
Spark 執行完畢後產生的 JSON 封包，會直接對應到 Google Sheets 的中繼欄位。

```json
[
  {
    "domain": "COMMUNITY",
    "track": "Deep_Dive",
    "source_title": "CoWoS 產能瓶頸推演與先進封裝路線圖",
    "source_url": "https://example.com/cowos-deep-dive",
    "raw_content": "詳解 2026-2027 先進封裝產能預估，指出關鍵設備交期與基板短缺仍是主要擴產阻礙...",
    "metrics": "預估月產能從 45k 擴展至 75k；關鍵設備交期長達 9-12 個月",
    "limitations": "建立在雲端服務商資本支出未見頂的前提假設",
    "raw_score": 4
  }
]

```

---

**今日小結與明天預告**

今天我們成功部署了前哨收集端的第一軌：透過 **Gemini Spark** 完成無代碼、高容錯的深度長文巡邏與結構化提煉。

收集到了資料，下一步需要一個穩固的「中繼基地」來承接。
明天（**Day 07**），我們將正式搭建 **Google Sheets 中繼資料庫**，設計符合狀態機生命週期的試算表結構與條件格式化視覺看板！

