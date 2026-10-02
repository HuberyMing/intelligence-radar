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
