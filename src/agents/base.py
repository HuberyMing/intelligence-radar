# src/agents/base.py (正確縮排版)
import json
import logging
import time
from typing import Any, List, Optional, Tuple

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class BaseAgent:

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
        """統一封裝呼叫邏輯：具備 503 原地退避重試與 429 配額自動切換模型的強韌調用器

        回傳：(parsed_json_dict, 實際跑成功的模型名稱)
        """
        last_exception = None

        for model_name in self.models_to_try:
            # 針對單一模型，遇到 503 給予最多 2 次原地短暫重試
            for attempt in range(2):
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

                    # 1. 遇到 429 RESOURCE_EXHAUSTED：當日額度已空，不需原地等待，直接跳出換下一個模型
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        logger.warning(
                            f"模型 [{model_name}] 觸發每日配額上限 (429)，立即切換至下一備援模型..."
                        )
                        break

                    # 2. 遇到 503 UNAVAILABLE：可能是尖峰抖動，先原地重試 1 次
                    if ("503" in err_msg or "UNAVAILABLE" in err_msg) and attempt == 0:
                        logger.info(
                            f"模型 [{model_name}] 遭遇 503 暫時尖峰，等待 3 秒後進行原地重試..."
                        )
                        time.sleep(3)
                        continue

                    # 若原地重試依然 503，且還有下一個備援模型，才切換
                    if ("503" in err_msg or "UNAVAILABLE" in err_msg) and model_name != self.models_to_try[-1]:
                        logger.warning(
                            f"模型 [{model_name}] 重試後仍為 503，自動切換至下一備援模型..."
                        )
                        time.sleep(2)
                        break

                    # 其他邏輯錯誤或已是最後一個模型，向上拋出
                    raise e

        raise last_exception

