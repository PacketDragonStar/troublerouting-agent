"""Webhook 客户端——推送排障报告到外部工单系统

支持 ServiceNow、Jira 等任何 HTTP 端点。
环境变量 WEBHOOK_URL 和 WEBHOOK_TOKEN 控制目标。
"""

import os
import httpx
from typing import Any, Optional


class WebhookClient:
    """通用 Webhook HTTP 客户端"""

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {
            "url": os.getenv("WEBHOOK_URL", ""),
            "headers": {
                "Authorization": f"Bearer {os.getenv('WEBHOOK_TOKEN', '')}",
                "Content-Type": "application/json",
            },
            "timeout": int(os.getenv("WEBHOOK_TIMEOUT", "10")),
        }

    def send(self, data: dict[str, Any]) -> dict[str, Any]:
        """发送 POST 请求推送报告数据

        Returns:
            {"success": bool, "status_code": int, "error": str}
        """
        try:
            response = httpx.post(
                url=self.config["url"],
                json=data,
                headers=self.config.get("headers", {}),
                timeout=self.config.get("timeout", 10),
            )
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "error": "" if response.status_code < 400 else response.text,
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "error": f"Connection/timeout error: {e}",
            }