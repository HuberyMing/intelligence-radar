# run_pipeline.py
import os

from google import genai

from src.adapters.sheets_adapter import SheetsAdapter
from src.services.pipeline import IntelligencePipeline


def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    sheets_adapter = SheetsAdapter()
    pipeline = IntelligencePipeline(client)

    # 1. 拉取 PENDING 狀態資料並自動加鎖為 ANALYZING
    pending_items = sheets_adapter.fetch_pending_items(auto_lock=True)
    print(f"成功鎖定待處理情報數量: {len(pending_items)}")

    # 2. 依序通過多代理人管線並寫回
    for item in pending_items:
        try:
            processed_item = pipeline.process_item(item)
            sheets_adapter.update_item_status(processed_item)
            print(f"條目 {processed_item.entry_id} 處理回填成功（狀態: {processed_item.status}）")
        except Exception as e:
            print(f"條目 {item.entry_id} 處理異常: {str(e)}")
            item.status = "ERROR"
            item.metadata["pipeline_error"] = str(e)
            sheets_adapter.update_item_status(item)

if __name__ == "__main__":
    main()
