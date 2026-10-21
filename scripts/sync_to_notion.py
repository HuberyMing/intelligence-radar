# scripts/sync_to_notion.py
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from src.adapters.notion_adapter import NotionSyncAdapter
from src.adapters.sheets_adapter import SheetsAdapter

load_dotenv()  # 這行必須在讀取環境變數之前執行


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    token = os.getenv("NOTION_API_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not token or not database_id:
        logger.error("缺少 NOTION_API_TOKEN 或 NOTION_DATABASE_ID 環境變數！")
        return

    logger.info("連線至 Google Sheets 讀取已處理情報...")
    sheets_adapter = SheetsAdapter()
    candidates = sheets_adapter.fetch_processed_items(min_score=4)
    logger.info(f"[*] 找到 {len(candidates)} 筆高價值情報候選項目...")

    notion_adapter = NotionSyncAdapter(auth_token=token, database_id=database_id)
    results = notion_adapter.batch_sync(candidates)
    logger.info(f"[+] Notion 同步完成！新增/更新: {results['synced']} 篇，略過: {results['skipped']} 篇。")

if __name__ == "__main__":
    main()