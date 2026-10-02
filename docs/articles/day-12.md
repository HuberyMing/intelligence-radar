### Day 12：ADK 核心起步：Google ADK 系統架構剖析與多代理人分工藍圖

在前兩個階段中，我們建立了乾淨強韌的基礎建設：透過 Pydantic V2 定義了不可侵犯的資料契約，並利用 Gemini Spark 與 Colab 建立了雙軌情報收集，最後以 Google Sheets 作為狀態機佇列完成資料匯流。

從今天開始，我們正式跨入全專案的最高潮——**「第三階段：Google ADK 多代理人核心建置」**。

過去我們處理的是「資料的搬運與規格化」；今天起，我們要讓這座雷達具備「專家級的協同認知與推演大腦」。

---

**一、 為什麼捨棄 Single-Prompt，走向 Google ADK 多代理人架構？**

許多人在處理情報分析時，習慣將整篇論文或財經指標一股腦丟給大模型，並在 System Prompt 裡寫著：「*請你扮演兼具頂尖 AI 研究員、華爾街總經分析師與資深總編的角色，幫我客觀審核並寫出週報...*」。

這種「全能單一 Prompt（Monolithic Prompt）」在面對複雜決策時存在致命缺陷：

1. **認知衝突與平庸化**：嚴格的「批判審核員（Reviewer）」需要挑惕漏洞與量化指標；「跨界合成師（Synthesizer）」需要大開大闔尋找科技與資本的交集；「主編（Editor）」則需要流暢好讀。把多種人格混雜在同一個上下文，模型只會產出模稜兩可的平庸總結。
2. **除錯與維護成本高昂**：若分析結果不佳，你無法判定是理解錯誤、評分失真還是文筆問題。

**Google ADK（Agent Development Kit）的核心哲學，就是將複雜認知解構為具備明確職責邊界、狀態隔離且能以程式碼嚴格編排的「多代理人專家團隊（Multi-Agent System）」。**

---

**二、 情報雷達多代理人協同藍圖**

在我們的情報雷達中，後端推演層被劃分為四個專門代理人，各司其職且透過確定性管線（Deterministic Pipeline）鏈接：

```text
[ Google Sheets: PENDING 佇列 ]
               │
               ▼
┌──────────────────────────────┐
│ 1. 審核員 Agent (Reviewer)    │  評估真實含金量與技術門檻
│    (Prompt: 挑骨頭/核實 metrics) │  產出 verified_score (1-5)
└──────────────┬───────────────┘
               │
       [ verified_score >= 4 ? ]
       ├── 否 (Score < 4) ──► 標記 ARCHIVED，終止分析（節省 Token）
       └── 是 (Score >= 4) ──┐
                             ▼
               ┌──────────────────────────────┐
               │ 2. 領域專家 (Domain Expert)   │  深度推演技術/資本底層機制
               │    (Science / Finance 專屬)  │  產出結構化洞見 (Insights)
               └──────────────┬───────────────┘
                             │
                             ▼
               ┌──────────────────────────────┐
               │ 3. 跨界合成師 (Synthesizer)  │  推演「科技 ➔ 資本 ➔ 產業」連鎖反應
               │    (Cross-Domain Thinker)    │  產出 cross_impact_notes
               └──────────────┬───────────────┘
                             │
                             ▼
               ┌──────────────────────────────┐
               │ 4. 首席主編 (Chief Editor)   │  統一語調，輸出高資訊密度文摘
               │    (Editorial Polisher)      │  產出 editorial_summary
               └──────────────┬───────────────┘
                             │
                             ▼
[ 回填 Google Sheets: PROCESSED 狀態 ]

```

* **分流斷路機制（Early Exit）**：審核員具備一票否決權。低於 4 分的邊際改進或雜訊，會直接標記為 `ARCHIVED` 封存，後續三個 Agent 根本不會被觸發，大幅節省 API 成本。

---

**三、 專案結構初始化：準備迎接 ADK**

在專案目錄的 `src/` 底下建立 `agents/` 套件目錄，並規劃清晰的代理人檔案結構：

```bash
mkdir -p src/agents
touch src/agents/__init__.py
touch src/agents/base.py         # 代理人抽象基底類別
touch src/agents/reviewer.py     # 審核員
touch src/agents/synthesizer.py  # 跨界合成師
touch src/agents/editor.py       # 主編
touch src/agents/orchestrator.py # 多代理人編排中樞

```

---

**今日小結與明天預告**

今天我們完成了「ADK 系統架構剖析」，確立了捨棄單一龐大 Prompt、轉向專業分工多代理人的架構決策，並定下了「審核 ➔ 領域推演 ➔ 跨界衝擊 ➔ 主編潤飾」的清晰流水線。

明天（**Day 13**），我們將正式著手實作第一道守門員：**「冷酷審核員 Agent（Reviewer）」**，透過定義嚴格的審查評分提示詞與結構化輸出，把守進入情報雷達的最高標準！