### Day 07：中繼基地落地：Google Sheets 資料表結構化設計與狀態機標籤

在 Day 05 我們用 Pydantic 定義了核心契約，並在 Day 06 讓前哨兵 Gemini Spark 上線巡邏。今天我們要讓全系統的資訊匯流心臟——**Google Sheets 中繼基地正式落地**！

很多人以為 Google Sheets 只是個記帳或存資料的試算表，但在微服務或多代理人架構中，它可以被提升為極具可視化優勢的**輕量分散式訊息佇列（Message Queue）與狀態中繼站**。

今天我們要做的核心工作，就是將「收納箱規格」**與**「狀態流轉規則」徹底固化在試算表中。

---

**一、 固化收納箱：Google Sheets 欄位結構化設計**

建立一個新的 Google 試算表，命名為 `Intelligence_Radar_Hub`，工作表（Tab）命名為 `raw_feed`。

表頭第一列（Row 1）必須完全對齊 Day 05 的 `IntelligenceItem` 資料契約，共規劃 15 個標準欄位：

| 欄位編號 | Header 欄位名稱 | 型別 / 格式 | 說明與約束 |
| --- | --- | --- | --- |
| **A** | `entry_id` | Text (8碼) | 唯一識別碼（如 `a1b2c3d4`），防重複主鍵 |
| **B** | `timestamp` | Datetime (UTC) | 收集入庫時間，格式 `YYYY-MM-DD HH:mm:ss` |
| **C** | `status` | Dropdown | **狀態機標籤**：`PENDING` / `ANALYZING` / `PROCESSED` / `ARCHIVED` / `ERROR` |
| **D** | `domain` | Text | 主領域（`SCIENCE`, `FINANCE`, `HEALTH`, `COMMUNITY`） |
| **E** | `track` | Text | 子軌道（如 `AI_Frontier`, `Macro_Econ`, `Biomechanics`） |
| **F** | `source_title` | Text | 文章或報告原始標題 |
| **G** | `source_url` | Text (URL) | 超連結網址 |
| **H** | `raw_content` | Text | 收集端提煉之 100-150 字核心論點 |
| **I** | `metrics` | Text | 關鍵數據或量化表現（無則留空） |
| **J** | `limitations` | Text | 侷限、硬體門檻或適用邊界（無則留空） |
| **K** | `raw_score` | Number (1-5) | 收集端初級評分 |
| **L** | `verified_score` | Number (1-5) | 後端審核員校準後的最終評分（初始為空） |
| **M** | `editorial_summary` | Text | 後端編輯整理之週報用摘要（初始為空） |
| **N** | `cross_impact_notes` | Text | 後端合成器整理之跨領域筆記（初始為空） |
| **O** | `metadata` | Text (JSON) | **彈性預留槽**，儲存作者、特定信源屬性等自訂 JSON |

> **設計哲學**：前 11 欄（A~K）由「收集端（Spark / Colab）」負責寫入；後續的 L、M、N 欄由「ADK 推演層」後續回填；O 欄則是吸收所有客製化欄位的萬用擴充槽。

---

**二、 固化狀態流轉：資料驗證（Data Validation）與下拉選單**

狀態機的靈魂在於「狀態值絕不允許人為手民之誤或模型隨意生成字串」。

1. 選取整欄 **C 欄（`status`）**（由 C2 開始向下選取）。
2. 點擊功能表的 **「資料」 ➔ 「資料驗證（Data Validation）」 ➔ 「新增規則」**。
3. 條件選擇 **「下拉式選單」**，並依序填入以下 5 個嚴格狀態節點：
* `PENDING`（待處理，預設初始值）
* `ANALYZING`（分析鎖定中）
* `PROCESSED`（已審核通過 / 已納入週報）
* `ARCHIVED`（常規雜訊已封存）
* `ERROR`（處理異常 / 需重試）


4. 進階選項中勾選 **「拒絕不合規格的輸入」**，徹底杜絕無效狀態寫入。

---

**三、 視覺化戰情看板：設定條件式格式化（Conditional Formatting）**

為了讓開發者或使用者肉眼一秒辨識整座雷達當前的運轉健康度，我們為 C 欄加入顏色編碼：

* **`PENDING`**：**灰色底色**（代表水庫中的待辦蓄水量）。
* **`ANALYZING`**：**鵝黃色底色**（代表正在被後端 ADK 多代理人運算鎖定）。
* **`PROCESSED`**：**亮綠色底色**（代表高價值情資，即將/已被產出為週報）。
* **`ARCHIVED`**：**淡藍色或淺灰字**（代表已安全歸檔的低分雜訊）。
* **`ERROR`**：**粉紅色底色 + 紅字**（代表網路逾時或解析失敗，一目了然需要介入）。

---

**四、 模擬首筆資料寫入驗證**

我們手動在第二列（Row 2）填入 Day 06 由 Gemini Spark 提煉出的測試資料：

* **`entry_id`**：`f8a91c2b`
* **`timestamp`**：`2026-09-21 08:00:00`
* **`status`**：`PENDING`
* **`domain`**：`COMMUNITY`
* **`track`**：`Deep_Dive`
* **`source_title`**：`CoWoS 產能瓶頸推演與先進封裝路線圖`
* **`source_url`**：`[https://semianalysis.com/](https://semianalysis.com/)...`
* **`raw_content`**：`詳解 2026-2027 先進封裝產能預估，指出關鍵設備交期與基板短缺仍是主要擴產阻礙...`
* **`metrics`**：`預估月產能從 45k 擴展至 75k；關鍵設備交期長達 9-12 個月`
* **`limitations`**：`建立在雲端服務商資本支出未見頂的前提假設`
* **`raw_score`**：`4`
* **`metadata`**：`{"analyst": "Dylan", "source_type": "newsletter"}`

當你在 C2 選取 `PENDING`，看到儲存格自動亮起灰色，整座中繼基地的「規格（Schema）」與「狀態機（State）」便正式成型！

---

**今日小結與明天預告**

今天我們完成了「中繼基地落地」，為分散式情報雷達打造了一個具備型別拘束、防重複鎖定與直觀視覺看板的 Google Sheets 訊息核心。

明天（**Day 08**），我們將正式打造雙軌收集器的第二軌：**在 Google Colab 撰寫輕量 Python Worker**，向 arXiv API 與聖路易聯準銀 FRED 發起結構化請求，親身體會「非結構化交給 Spark，結構化交給爬蟲」的極致架構分工！