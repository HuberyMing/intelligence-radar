# src/ports/knowledge_sync.py
from abc import ABC, abstractmethod
from typing import List, Dict
from src.core.models import IntelligenceItem

class KnowledgeSyncPort(ABC):
    @abstractmethod
    def sync_item(self, item: IntelligenceItem, overwrite: bool = False) -> bool:
        """將單筆情報同步至外部知識庫，回傳是否成功寫入（若存在且未覆寫則回傳 False）。"""
        pass

    @abstractmethod
    def batch_sync(self, items: List[IntelligenceItem], overwrite: bool = False) -> Dict[str, int]:
        """批次同步情報清單，回傳成功與略過筆數。"""
        pass