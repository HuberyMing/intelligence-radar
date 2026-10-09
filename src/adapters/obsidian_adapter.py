# src/adapters/obsidian_adapter.py
from __future__ import annotations

import re
from pathlib import Path
from jinja2 import Template
from src.ports.knowledge_sync import KnowledgeSyncPort
from src.core.models import IntelligenceItem

OBSIDIAN_TEMPLATE = """---
id: "{{ item.entry_id }}"
title: "{{ (item.source_title or item.title or '') | replace('"', '\\"') }}"
source: "{{ item.source_url }}"
domain: "{{ item.domain }}"
score: {{ item.verified_score or item.raw_score or 0 }}
date: "{{ item.timestamp if item.timestamp else '' }}"
tags:
  - intelligence-radar
  - domain/{{ item.domain | lower }}
---

# {{ item.source_title or item.title }}

> [!abstract] 核心提煉
> {{ item.editorial_summary or item.executive_summary or "暫無摘要" }}

## 📊 量化對比與效能指標
{{ item.metrics or item.benchmarks_and_metrics or "無顯著量化指標揭露。" }}

## ⚠️ 技術邊界與潛在缺陷
{{ item.limitations or "作者未於論文中強調顯著邊界。" }}

## 🔮 二階效應與跨領域衝擊
> [!tip] 跨界推演
> {{ item.second_order_effects if item.second_order_effects else "暫無推演。" }}

---
## 關聯實體
- 領域節點: [[{{ item.domain }}]]
- 來源追蹤: [原始文章連結]({{ item.source_url }})
"""

class ObsidianVaultAdapter(KnowledgeSyncPort):
    def __init__(self, vault_path: str | Path, subfolder: str = "00_Inbox/Radar"):
        self.vault_path = Path(vault_path).resolve()
        self.target_dir = self.vault_path / subfolder
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.template = Template(OBSIDIAN_TEMPLATE)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        # 去除 Windows / POSIX 檔案系統禁用的字元
        sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
        # 壓縮過長檔名，避免超出作業系統 255 字元上限
        return sanitized.strip()[:100]

    def _build_filepath(self, item: IntelligenceItem) -> Path:
        # 1. 取得日期：優先讀取 timestamp，若無則讀 created_at，再無則以當日代入
        raw_date = getattr(item, "timestamp", None) or getattr(item, "created_at", None)
        
        if hasattr(raw_date, "strftime"):
            date_prefix = raw_date.strftime("%Y-%m-%d")
        elif isinstance(raw_date, str) and len(raw_date) >= 10:
            # 若為字串 (例如 "2026-09-25 14:50:55")，擷取前 10 碼
            date_prefix = raw_date[:10]
        else:
            from datetime import datetime
            date_prefix = datetime.now().strftime("%Y-%m-%d")

        # 2. 取得標題：對齊 source_title 或 title
        title = getattr(item, "source_title", None) or getattr(item, "title", "Untitled")
        safe_title = self._sanitize_filename(title)
        
        # 3. 取得領域 (domain)
        domain = getattr(item, "domain", "GENERAL")

        # 取 entry_id 前 8 碼作為唯一區隔
        entry_short = str(getattr(item, "entry_id", ""))[:8]
        if entry_short:
            filename = f"{date_prefix} - [{domain}] {safe_title} ({entry_short}).md"
        else:
            filename = f"{date_prefix} - [{domain}] {safe_title}.md"

        return self.target_dir / filename

    def sync_item(self, item: IntelligenceItem, overwrite: bool = False) -> bool:
        target_file = self._build_filepath(item)
        if target_file.exists() and not overwrite:
            return False

        content = self.template.render(item=item)
        target_file.write_text(content, encoding="utf-8")
        return True

    def batch_sync(self, items: list[IntelligenceItem], overwrite: bool = False) -> dict[str, int]:
        stats = {"synced": 0, "skipped": 0}
        for item in items:
            if self.sync_item(item, overwrite=overwrite):
                stats["synced"] += 1
            else:
                stats["skipped"] += 1
        return stats
