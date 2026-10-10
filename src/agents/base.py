# src/agents/base.py
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
    # 預設備援清單：若主力 503，降級至 gemini-3.8-flash-lite
    self.models_to_try = [primary_model] + (
        fallback_models or ["gemini-3.8-flash-lite"]
    )


# src/agents/base.py
def _generate_with_fallback(self, prompt: str, schema: Any, system_instruction: Optional[str] = None) -> Tuple[Any, str]:
    """統一封裝呼叫邏輯：支援 503 自動降級與 JSON 解析

    回傳：(parsed_json_dict, 實際跑成功的模型名稱)
    """
    last_exception = None

    for model_name in self.models_to_try:
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
            # 只有在遇到 503 / UNAVAILABLE 且還有備援模型時才降級
            if (
                "503" in err_msg or "UNAVAILABLE" in err_msg
            ) and model_name != self.models_to_try[-1]:
                logger.warning(
                    f"模型 [{model_name}] 遭遇 503 尖峰，自動降級切換至"
                    "備援模型嘗試..."
                )
                time.sleep(2)
                continue
            # 若是 429 或其他不可切換的邏輯錯誤，直接向上拋出
            raise e

    raise last_exception
