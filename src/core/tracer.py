# src/core/tracer.py
import functools
import logging
import time
from typing import Callable

from src.core.models import AgentSpan, IntelligenceItem

logger = logging.getLogger("agent.tracer")

def trace_agent_step(agent_name: str):
    """攔截代理人執行過程，自動記錄耗時、決策推導與思考鏈追蹤。"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, item: IntelligenceItem, *args, **kwargs):
            start_time = time.perf_counter()
            error_msg = None
            decision = None
            thought_process = None

            logger.info(f"[{item.entry_id}] 開始執行節點: {agent_name}")

            try:
                # 執行實際的代理人邏輯
                result_item, should_continue = func(self, item, *args, **kwargs)
                
                # 動態萃取關鍵代理人的決策與思考
                if agent_name == "Reviewer":
                    decision = f"SCORE_{result_item.verified_score}" if result_item.verified_score else "ARCHIVED"
                    thought_process = result_item.metadata.get("review_reasoning")
                elif agent_name == "Synthesizer":
                    decision = "SYNTHESIZED"
                    thought_process = result_item.cross_impact_notes
                
                return result_item, should_continue

            except Exception as exc:
                error_msg = str(exc)
                logger.error(f"[{item.entry_id}] 節點 {agent_name} 執行失敗: {exc}")
                raise exc

            finally:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                span = AgentSpan(
                    agent_name=agent_name,
                    duration_ms=duration_ms,
                    decision=decision,
                    thought_process=thought_process[:200] if thought_process else None,
                    error=error_msg
                )

                # 將 Span 寫入 IntelligenceItem 的追蹤歷史中
                if "traces" not in item.metadata:
                    item.metadata["traces"] = []
                item.metadata["traces"].append(span.model_dump(mode="json"))

                logger.info(
                    f"[{item.entry_id}] 節點 {agent_name} 完成 "
                    f"| 耗時: {duration_ms}ms "
                    f"| 決策: {decision or 'OK'} "
                    f"| 錯誤: {error_msg is not None}"
                )

        return wrapper
    return decorator
