# scripts/sync_to_obsidian.py
import os
import argparse
import logging
from pathlib import Path
from src.adapters.sheets_adapter import SheetsAdapter
from src.adapters.obsidian_adapter import ObsidianVaultAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="將 Google Sheets 已審查高分情資同步至 Obsidian Vault")
    parser.add_argument(
        "--vault-dir",
        type=str,
        default=os.getenv("OBSIDIAN_VAULT_PATH", "~/ObsidianVault"),
        help="目標 Obsidian Vault 路徑"
    )
    parser.add_argument(
        "--subfolder",
        type=str,
        default="00_Inbox/Radar",
        help="Vault 內存放情報的子目錄"
    )
    args = parser.parse_args()

    vault_path = Path(args.vault_dir).expanduser().resolve()
    logger.info(f"初始化 Obsidian 轉接器，目標路徑: {vault_path}")

    obsidian_adapter = ObsidianVaultAdapter(
        vault_path=vault_path,
        subfolder=args.subfolder
    )

    logger.info("連線至 Google Sheets 讀取已處理情資...")
    sheets_adapter = SheetsAdapter()
    candidates = sheets_adapter.fetch_processed_items(min_score=4)
    logger.info(f"[*] 找到 {len(candidates)} 筆高價值情報候選項目...")

    results = obsidian_adapter.batch_sync(candidates)
    logger.info(f"[+] 同步完成！新增: {results['synced']} 篇，略過: {results['skipped']} 篇。")

if __name__ == "__main__":
    main()