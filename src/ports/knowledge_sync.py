# src/ports/knowledge_sync.py
from abc import ABC, abstractmethod
from src.core.models import IntelligenceItem

class KnowledgeSyncPort(ABC):
    @abstractmethod
    def sync_item(self, item: IntelligenceItem) -> bool:
        """將單筆已處理的情報同步至外部知識庫。"""
        pass

    @abstractmethod
    def batch_sync(self, items: list[IntelligenceItem]) -> dict[str, int]:
        """批次同步情報清單，回傳成功與略過筆數。"""
        pass
