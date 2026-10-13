# src/agents/base.py (正確縮排版)
import json
import logging
import time
from typing import Any, List, Optional, Set, Tuple

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class BaseAgent:
    # 類別層級黑名單：所有 Agent 共享，當天額度死掉的模型直接跳過，不再浪費請求
    _exhausted_daily_models: Set[str] = set()

    def __init__(
        self,
        client: genai.Client,
        primary_model: str = "gemini-3.8-flash",
        fallback_models: Optional[List[str]] = None,
    ):
        self.client = client
        self.primary_model = primary_model

        # 依序降級：主力 (3.8) -> 官方推薦標準 (3.6) -> 備援模型
        # 只保留 2026 當前真正合法存在且支援 generateContent 的型號
        default_fallbacks = [
            "gemini-3.6-flash",
        ]
        self.models_to_try = [primary_model] + (
            fallback_models if fallback_models is not None else default_fallbacks
        )

    def _generate_with_fallback(
        self, prompt: str, schema: Any, system_instruction: Optional[str] = None
    ) -> Tuple[Any, str]:
        """具備 503/429-RPM 原地退避重試與 全域模型降級 的調用器"""
        last_exception = None

        # 過濾掉今天已經被標記為「每日額度用光」的模型
        active_models = [m for m in self.models_to_try if m not in BaseAgent._exhausted_daily_models]
        if not active_models:
            active_models = self.models_to_try  # 若全部都被黑名單，退回最後嘗試

        for model_name in active_models:
            # 單一模型最多嘗試 3 次 (處理 503 抖動或 429 速率冷卻)
            for attempt in range(3):
                try:
                    config_kwargs = {
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                        "temperature": 0.1,
                    }
                    if system_instruction:
                        config_kwargs["system_instruction"] = system_instruction

                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(**config_kwargs),
                    )

                    # 支援 Pydantic 模型驗證
                    if hasattr(schema, "model_validate_json"):
                        result = schema.model_validate_json(response.text)
                    else:
                        result = json.loads(response.text)
                    return result, model_name

                except Exception as e:
                    last_exception = e
                    err_msg = str(e)

                    # 情境 A：429 RESOURCE_EXHAUSTED
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        # 情況 A-1：每日限額用光 (PerDay) -> 加入全域黑名單，換下一個模型
                        if "PerDay" in err_msg or "day" in err_msg.lower():
                            logger.warning(
                                f"模型 [{model_name}] 觸發每日限額 (PerDay)，加入當日黑名單，切換至備援模型..."
                            )
                            BaseAgent._exhausted_daily_models.add(model_name)
                            break
                        # 情況 A-2：每分鐘超速 (PerMinute 5 RPM) -> 原地睡 15 秒冷卻後重試！
                        else:
                            logger.info(
                                f"模型 [{model_name}] 撞上每分鐘速率限制 (5 RPM)，冷卻 15 秒後重試 (第 {attempt+1} 次)..."
                            )
                            time.sleep(15)
                            continue

                    # 情境 B：503 暫時伺服器抖動 -> 原地等待 3 秒後重試
                    if "503" in err_msg or "UNAVAILABLE" in err_msg:
                        if attempt < 2:
                            logger.info(f"模型 [{model_name}] 遭遇 503 尖峰，等待 3 秒後原地重試...")
                            time.sleep(3)
                            continue
                        elif model_name != active_models[-1]:
                            logger.warning(f"模型 [{model_name}] 重試仍為 503，切換至備援模型...")
                            break

                    # 其他嚴重邏輯錯誤或已無備援
                    raise e

        raise last_exception

