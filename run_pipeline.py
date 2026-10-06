# run_pipeline.py
import logging
import os
import sys
import time

from google import genai

from src.adapters.notifier import WebhookNotifier
from src.adapters.sheets_adapter import SheetsAdapter
from src.core.models import ItemStatus
from src.services.pipeline import IntelligencePipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    notifier = WebhookNotifier()
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("找不到 GEMINI_API_KEY 環境變數")

        client = genai.Client(api_key=api_key)
        sheets_adapter = SheetsAdapter()
        pipeline = IntelligencePipeline(client)

        pending_items = sheets_adapter.fetch_pending_items(auto_lock=True)
        logger.info(f"成功鎖定待處理情報數量: {len(pending_items)}")

        stats = {ItemStatus.PROCESSED: 0, ItemStatus.ARCHIVED: 0, ItemStatus.ERROR: 0}

        for item in pending_items:
            try:
                processed_item = pipeline.process_item(item)
                # 傳入 item 以及其目標狀態
                sheets_adapter.update_item_status(processed_item)
                stats[processed_item.status] = stats.get(processed_item.status, 0) + 1
                # 🌟 防 429 護城河：每處理完一筆，喘口氣 10 秒
                time.sleep(10)
            except Exception as item_err:
                logger.error(f"條目 {item.entry_id} 處理異常: {item_err}")
                item.status = ItemStatus.ERROR
                item.metadata["pipeline_error"] = str(item_err)
                # 捕捉到異常時： 明確傳入 ItemStatus.ERROR
                sheets_adapter.update_item_status(item, new_status=ItemStatus.ERROR)
                stats[ItemStatus.ERROR] += 1

        # 若有處理到項目，發布巡航總結推播
        if pending_items:
            notifier.send_pipeline_report(
                processed_count=stats.get(ItemStatus.PROCESSED, 0),
                archived_count=stats.get(ItemStatus.ARCHIVED, 0),
                error_count=stats.get(ItemStatus.ERROR, 0),
            )

    except Exception as fatal_err:
        logger.critical(f"管線遭遇致命崩潰: {fatal_err}", exc_info=True)
        notifier.send_critical_alert(str(fatal_err), context="Fatal Unhandled Exception")
        sys.exit(1)

if __name__ == "__main__":
    main()