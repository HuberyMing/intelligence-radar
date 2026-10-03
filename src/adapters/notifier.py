# src/adapters/notifier.py
import logging
import os

import requests

logger = logging.getLogger(__name__)

class WebhookNotifier:
    """輕量級 Webhook 告警轉接器 (相容 Discord / Slack Webhook 格式)"""

    def __init__(self):
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")

    def send_pipeline_report(self, processed_count: int, archived_count: int, error_count: int):
        """推送每日巡航成功總結報告"""
        if not self.webhook_url:
            logger.info("未設定 ALERT_WEBHOOK_URL，跳過推播。")
            return

        payload = {
            "embeds": [
                {
                    "title": "📡 Intelligence Radar 巡航巡邏完畢",
                    "color": 3066993 if error_count == 0 else 15158332, # 綠色或紅色
                    "fields": [
                        {"name": "通過精煉 (PROCESSED)", "value": f"**{processed_count}** 則", "inline": True},
                        {"name": "雜訊熔斷 (ARCHIVED)", "value": f"**{archived_count}** 則", "inline": True},
                        {"name": "異常中斷 (ERROR)", "value": f"**{error_count}** 則", "inline": True},
                    ],
                    "footer": {"text": "Google ADK x Hexagonal Intelligence Radar 2026"}
                }
            ]
        }
        self._dispatch(payload)

    def send_critical_alert(self, error_message: str, context: str = "Pipeline Failure"):
        """管線發生未預期崩潰時的緊急告警"""
        if not self.webhook_url:
            return

        payload = {
            "content": "🚨 **【緊急告警】情報雷達管線發生崩潰異常！**",
            "embeds": [
                {
                    "title": f"系統錯誤情境: {context}",
                    "color": 15158332, # 醒目紅
                    "description": f"```python\n{error_message[:1500]}\n```",
                    "footer": {"text": "請盡速檢查 GitHub Actions 執行記錄"}
                }
            ]
        }
        self._dispatch(payload)

    def _dispatch(self, payload: dict):
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"發送 Webhook 告警失敗: {e}")
