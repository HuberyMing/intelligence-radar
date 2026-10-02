### Day 09：異構資料對齊：讓 Spark 與 Colab 遵循同一資料契約寫入 Sheets

在過去三天，我們完成了前哨收集端的雙軌建置：

* **第一軌（Day 06）**：Gemini Spark 負責長文巡邏，提煉具備深度的非結構化文章。
* **第二軌（Day 08）**：Colab Python Worker 負責定時發起請求，抓取 arXiv 論文與 FRED 總經指標。

但此時面臨一個經典工程挑戰：**異構資料的形狀差異**。
Gemini Spark 吐出的是 8 個欄位的分析 JSON；Colab 抓到的是包含論文作者或指標代碼的自訂結構。如果各自直接往資料庫塞，Google Sheets 很快會淪為欄位錯位、缺漏主鍵的垃圾場。

今天我們要打造「異構資料對齊轉換器（Data Harmonizer / Normalizer）」，將多來源的輸入統合成 15 欄的 `IntelligenceItem`，並批次注入 Google Sheets 中繼站！

---

**一、 為什麼需要對齊轉換器（Data Harmonizer）？**

在六角架構（Hexagonal Architecture）中，收集端屬於系統的最外層。它們只負責「採集」，不應該也不需要理解資料庫底層長什麼樣子。

對齊轉換器的核心責任是補足「系統生命週期資訊」：

1. **補齊主鍵與時間**：自動生成全域唯一 8 碼 `entry_id`，並打上 UTC `timestamp`。
2. **初始化狀態機標籤**：強制將初始狀態設定為 `PENDING`，禁止任何來源繞過審核直接變成已處理。
3. **吸收特定欄位至萬用槽**：將 arXiv 的作者名冊、FRED 的指標代號等差異屬性，自動打包進 `metadata` 字典。
4. **預留後續分析空槽**：將 `verified_score`、`editorial_summary` 與 `cross_impact_notes` 初始化為 `None`，等待 ADK 推理層接手。

---

**二、 實作資料轉換核心：`src/core/harmonizer.py`**

在 `src/core/` 目錄下建立 `harmonizer.py`，負責將任意來源的 Raw Data 轉換為標準 Pydantic 模型：

```python
# src/core/harmonizer.py
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from src.core.models import IntelligenceItem, ItemStatus, DomainType


class DataHarmonizer:
    """異構資料對齊轉換器：將各收集端原始字典轉換為標準 IntelligenceItem"""

    @staticmethod
    def normalize(raw_payload: Dict[str, Any]) -> IntelligenceItem:
        """
        將前端輸入標準化為完整 15 欄合約
        自動處理預設值、欄位映射與型別容錯
        """
        # 1. 提取或生成主鍵與時間
        entry_id = raw_payload.get("entry_id") or str(uuid.uuid4())[:8]
        timestamp = raw_payload.get("timestamp") or datetime.now(timezone.utc)

        # 2. 提取或打包自訂 metadata
        core_fields = {
            "entry_id", "timestamp", "status", "domain", "track",
            "source_title", "source_url", "raw_content", "metrics",
            "limitations", "raw_score", "verified_score",
            "editorial_summary", "cross_impact_notes", "metadata"
        }
        
        # 既有的 metadata 加上未在核心定義的外掛欄位
        merged_metadata = dict(raw_payload.get("metadata", {}))
        for k, v in raw_payload.items():
            if k not in core_fields:
                merged_metadata[k] = v

        # 3. 建立並嚴格驗證 Pydantic 物件
        item = IntelligenceItem(
            entry_id=entry_id,
            timestamp=timestamp,
            status=ItemStatus.PENDING,  # 強制鎖定為待處理
            domain=raw_payload["domain"],
            track=raw_payload["track"],
            source_title=raw_payload["source_title"].strip(),
            source_url=raw_payload["source_url"].strip(),
            raw_content=raw_payload["raw_content"].strip(),
            metrics=raw_payload.get("metrics"),
            limitations=raw_payload.get("limitations"),
            raw_score=int(raw_payload.get("raw_score", 3)),
            verified_score=None,
            editorial_summary=None,
            cross_impact_notes=None,
            metadata=merged_metadata
        )
        return item

```

---

**三、 序列化器：平整化為 Google Sheets 15 欄橫列**

Google Sheets API 寫入需要的是二維陣列（Row by Row），我們需要一個專門的方法，將 `IntelligenceItem` 依照 Day 07 定義的 A 到 O 欄順序平整化（Flatten）：

```python
# 在 src/core/harmonizer.py 追加序列化方法
import json

class SheetSerializer:
    """負責將 IntelligenceItem 映射至 Google Sheets A~O 欄位"""

    HEADERS = [
        "entry_id", "timestamp", "status", "domain", "track",
        "source_title", "source_url", "raw_content", "metrics",
        "limitations", "raw_score", "verified_score", "editorial_summary",
        "cross_impact_notes", "metadata"
    ]

    @staticmethod
    def _val(field: Any) -> str:
        """輔助函式：安全提取 Enum 或純字串的值"""
        if hasattr(field, "value"):
            return str(field.value)
        return str(field) if field is not None else ""

    @staticmethod
    def to_row(item: IntelligenceItem) -> List[Any]:
        """按嚴格順序序列化為 Google Sheets 寫入陣列 (15 欄)"""
        return [
            item.entry_id,
            item.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            SheetSerializer._val(item.status),
            SheetSerializer._val(item.domain),
            item.track,
            item.source_title,
            item.source_url,
            item.raw_content,
            item.metrics or "",
            item.limitations or "",
            item.raw_score,
            item.verified_score if item.verified_score is not None else "",
            item.editorial_summary or "",
            item.cross_impact_notes or "",
            json.dumps(item.metadata, ensure_ascii=False) if item.metadata else "{}"
        ]
```

---

**四、 端到端轉換驗證：撰寫整合測試**

在 `tests/test_harmonizer.py` 中，我們模擬分別吃進「Gemini Spark 格式」與「Colab 爬蟲格式」，驗證能否產出完全相同的 15 欄規格：

```python
# tests/test_harmonizer.py
from src.core.harmonizer import DataHarmonizer, SheetSerializer
from src.core.models import ItemStatus

def test_harmonize_spark_and_colab_payloads():
    # 模擬 Gemini Spark 吐出的 8 欄格式
    spark_payload = {
        "domain": "COMMUNITY",
        "track": "Deep_Dive",
        "source_title": "CoWoS 產能與先進封裝路線圖",
        "source_url": "https://semianalysis.com/test",
        "raw_content": "分析封裝產能結構性瓶頸...",
        "metrics": "2026 年預估擴充 30%",
        "limitations": "依賴台積電擴產進度",
        "raw_score": 4
    }

    # 模擬 Colab 爬到的 FRED 格式 (含有外掛欄位 observation_date)
    fred_payload = {
        "domain": "FINANCE",
        "track": "Macro_Econ",
        "source_title": "美國 10 年期公債殖利率",
        "source_url": "https://fred.stlouisfed.org/...",
        "raw_content": "最新公債殖利率變動更新...",
        "raw_score": 3,
        "observation_date": "2026-09-22"  # 特有額外欄位
    }

    # 執行轉換
    item_a = DataHarmonizer.normalize(spark_payload)
    item_b = DataHarmonizer.normalize(fred_payload)

    # 驗證狀態機均為 PENDING 且有獨立 entry_id
    assert item_a.status == ItemStatus.PENDING
    assert item_b.status == ItemStatus.PENDING
    assert len(item_a.entry_id) == 8
    assert item_b.metadata["observation_date"] == "2026-09-22"

    # 驗證轉為 Google Sheets 列格式時，欄位長度皆精確等於 15
    row_a = SheetSerializer.to_row(item_a)
    row_b = SheetSerializer.to_row(item_b)

    assert len(row_a) == 15
    assert len(row_b) == 15
    assert row_a[2] == "PENDING"
    assert row_b[2] == "PENDING"

```

執行指令：

```bash
python -m pytest tests/test_harmonizer.py

```

若終端機亮起綠燈，代表不管是文字提煉還是數據爬蟲，在進入 Google Sheets 前已經被全部規格化！

---

**今日小結與明天預告**

今天我們完成了「異構資料對齊轉換器」，將異質、多源的前端情報統一約束至 15 欄的規範下，實現了真正意義上的資料標準化。

明天（**Day 10**），我們將正式打造系統的外部連接橋樑：**配置 Google Cloud 服務帳號（Service Account）與啟用 Google Sheets API**，授權我們的 Python 程式具備遠端自動讀寫試算表的核心權限！