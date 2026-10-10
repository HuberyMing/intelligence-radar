# src/services/pipeline.py
import logging
import time

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agents.domain_expert import DomainExpertAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.synthesizer import SynthesizerAgent
from src.core.models import IntelligenceItem, ItemStatus

logger = logging.getLogger(__name__)

class IntelligencePipeline:
    def __init__(self, client: genai.Client):
        self.reviewer = ReviewerAgent(client)
        self.expert = DomainExpertAgent(client)
        self.synthesizer = SynthesizerAgent(client)
        self.editor = EditorAgent(client)

    @retry(
        # 最多重試 3 次（含初次共 3 次）
        stop=stop_after_attempt(3),
        # 指數退避：初次等待 2 秒，每次翻倍 (2s -> 4s -> 8s)，上限 10 秒
        wait=wait_exponential(multiplier=2, min=3, max=15),
        # 只針對包含 503/429 等暫時性伺服器錯誤進行重試，其餘邏輯錯誤立即中斷
        reraise=True,
    )
    def _execute_stage_with_retry(self, stage_fn, item):
        """防禦性單一階段執行器"""
        return stage_fn(item)

    def process_item(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        執行單一條目的完整多代理人串接管線。
        """
        logger.info(f"開始處理情資 [{item.entry_id}]: {item.source_title}")

        try:
            # 1. Reviewer 初審: 守門員審核與 Early-exit 分流 (帶重試)
            item, should_continue = self._execute_stage_with_retry(
                self.reviewer.evaluate, item
            )
            if not should_continue:
                logger.warning(f"條目 [{item.entry_id}] 未達門檻 (得分: {item.raw_score})，熔斷歸檔。")
                return item
            time.sleep(12)  # 均勻節奏：確保每分鐘不超過 5 次 (60s / 5 = 12s)

            # 2. Domain Expert 專家提煉 (帶重試)
            logger.info(f"條目 [{item.entry_id}] 通過初審，進入 Domain Expert 深入萃取。")
            item = self._execute_stage_with_retry(self.expert.analyze, item)
            time.sleep(12)

            # 3. Synthesizer 跨領域推演: 綜合研判與二階推演 (帶重試)
            logger.info(f"條目 [{item.entry_id}] 進入 Synthesizer 進行跨領域影響推演。")
            item = self._execute_stage_with_retry(self.synthesizer.synthesize, item)
            time.sleep(12)

            # 4. Editor 總編潤飾: 編定稿與排版成型 (帶重試)
            logger.info(f"條目 [{item.entry_id}] 進入 Editor 進行最終摘要定稿。")
            item = self._execute_stage_with_retry(self.editor.edit, item)

            # 5. 標記處理完成
            item.status = ItemStatus.PROCESSED
            logger.info(f"條目 [{item.entry_id}] 流水線全流程執行完畢，狀態切換為 PROCESSED。")
            return item

        except Exception as e:
            err_str = str(e)
            # 若主力模型遇到 503 伺服器尖峰，記錄並拋給上層標記 ERROR，不卡住其他條目
            if "503" in err_str or "UNAVAILABLE" in err_str:
                logger.warning(
                    f"條目 [{item.entry_id}] 遭遇 Google 503 尖峰，已耗盡重試配額。"
                )
            raise e

