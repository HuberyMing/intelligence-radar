# src/services/pipeline.py
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agents.domain_expert import DomainExpertAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.synthesizer import SynthesizerAgent
from src.core.models import IntelligenceItem, ItemStatus

# 確保 logs/traces 目錄存在
os.makedirs("logs/traces", exist_ok=True)



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
    

    def _record_trace(self, item, stage_name: str, duration: float, error=None):
        """將單一 Agent 執行軌跡追加到 metadata 與本地日誌中（含思考鏈輸出預覽）"""
        
        # 依階段提取該 Agent 剛產出的思維摘要
        output_preview = ""
        if stage_name == "Reviewer":
            score_text = f"評分: {item.raw_score} 分" if hasattr(item, "raw_score") else ""
            reason = item.metadata.get("reviewer_reason") or "通過初審"
            output_preview = f"{score_text} | 審核結果: {reason}"
        elif stage_name == "DomainExpert":
            m = item.metrics or "無特殊量化指標"
            lim = item.limitations or "無特殊技術限制"
            output_preview = f"【指標】{m}\n【限制】{lim}"
        elif stage_name == "Synthesizer":
            output_preview = item.cross_impact_notes or "無跨領域推演"
        elif stage_name == "Editor":
            output_preview = item.editorial_summary or "無定稿摘要"

        span = {
            "stage": stage_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_sec": round(duration, 2),
            "status": "ERROR" if error else "SUCCESS",
            "error": str(error) if error else None,
            "output_preview": output_preview,  # 🌟 加入關鍵的思考輸出文字！
        }
        
        if "execution_trace" not in item.metadata:
            item.metadata["execution_trace"] = []
        item.metadata["execution_trace"].append(span)

        # 即時寫入本地 JSONL
        today_str = datetime.now().strftime("%Y-%m-%d")
        trace_file = f"logs/traces/trace_{today_str}.jsonl"
        with open(trace_file, "a", encoding="utf-8") as f:
            log_entry = {
                "entry_id": item.entry_id,
                "source_title": item.source_title,
                "span": span,
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def _execute_stage_with_trace(self, stage_name: str, stage_fn, item):
        """無侵入式 Trace 包覆器"""
        start_time = time.time()
        err = None
        
        try:
            # 調用原本具備 tenacity retry 的執行器
            return self._execute_stage_with_retry(stage_fn, item)
        except Exception as e:
            err = e
            raise e
        finally:
            duration = time.time() - start_time
            self._record_trace(item, stage_name, duration, error=err)


    def process_item(self, item: IntelligenceItem) -> IntelligenceItem:
        """
        執行單一條目的完整多代理人串接管線。
        """
        logger.info(f"開始處理情資 [{item.entry_id}]: {item.source_title}")

        try:
            # 1. Reviewer 初審: 守門員審核與 Early-exit 分流 (帶重試)
            # item, should_continue = self._execute_stage_with_retry(
            #     self.reviewer.evaluate, item
            # )
            item, should_continue = self._execute_stage_with_trace(
                "Reviewer", self.reviewer.evaluate, item
            )
            if not should_continue:
                logger.warning(f"條目 [{item.entry_id}] 未達門檻 (得分: {item.raw_score})，熔斷歸檔。")
                return item
            time.sleep(12)  # 均勻節奏：確保每分鐘不超過 5 次 (60s / 5 = 12s)

            # 2. Domain Expert 專家提煉 (帶重試)
            logger.info(f"條目 [{item.entry_id}] 通過初審，進入 Domain Expert 深入萃取。")
            # item = self._execute_stage_with_retry(self.expert.analyze, item)
            item = self._execute_stage_with_trace("DomainExpert", self.expert.analyze, item)
            time.sleep(12)

            # 3. Synthesizer 跨領域推演: 綜合研判與二階推演 (帶重試)
            logger.info(f"條目 [{item.entry_id}] 進入 Synthesizer 進行跨領域影響推演。")
            # item = self._execute_stage_with_retry(self.synthesizer.synthesize, item)
            item = self._execute_stage_with_trace(
                "Synthesizer", self.synthesizer.synthesize, item
            )
            time.sleep(12)

            # 4. Editor 總編潤飾: 編定稿與排版成型 (帶重試)
            logger.info(f"條目 [{item.entry_id}] 進入 Editor 進行最終摘要定稿。")
            # item = self._execute_stage_with_retry(self.editor.edit, item)
            item = self._execute_stage_with_trace("Editor", self.editor.edit, item)

            # 5. 標記處理完成
            item.status = ItemStatus.PROCESSED
            logger.info(f"條目 [{item.entry_id}] 流水線全流程執行完畢，狀態切換為 PROCESSED。")
            return item

        except Exception as e:
            err_str = str(e)
            logger.error(f"處理情資 [{item.entry_id}] 遭遇未捕獲例外: {err_str}", exc_info=True)

            # 若主力模型遇到 503 伺服器尖峰，記錄並拋給上層標記 ERROR，不卡住其他條目
            if "503" in err_str or "UNAVAILABLE" in err_str:
                logger.warning(
                    f"條目 [{item.entry_id}] 遭遇 Google 503 尖峰，已耗盡重試配額。"
                )
            # raise e # 這個例外就會把整個程式炸飛
            item.status = ItemStatus.ERROR
            item.metadata["error_reason"] = err_str
            return item


def dump_traces(items: list[IntelligenceItem]):
    log_dir = Path("logs/traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    trace_file = log_dir / f"trace_{today_str}.jsonl"

    with trace_file.open("a", encoding="utf-8") as f:
        for item in items:
            record = {
                "entry_id": item.entry_id,
                "source_title": item.source_title,
                "status": item.status,
                "verified_score": item.verified_score,
                "traces": item.metadata.get("traces", [])
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
