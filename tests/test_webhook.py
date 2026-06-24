"""
Ticket 16: 工单系统 Webhook 对接 测试

验证 Reporter 能通过 HTTP POST 推送排障报告到外部系统。
"""
import pytest
from unittest.mock import patch, MagicMock
import json


@pytest.fixture
def webhook_config():
    return {
        "url": "https://hooks.example.com/troubleshooting",
        "headers": {"Authorization": "Bearer test-token"},
        "timeout": 10,
    }


class TestWebhookClient:
    """Webhook HTTP 客户端"""

    def test_webhook_sends_post_with_report(self, webhook_config):
        from agent.webhook import WebhookClient
        client = WebhookClient(webhook_config)

        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_post.return_value = mock_response

            result = client.send({
                "session_id": "test-001",
                "root_cause": "OSPF 邻居断开",
                "confidence": 0.85,
                "risk_level": "high",
            })

            assert result["success"] is True
            assert result["status_code"] == 200
            mock_post.assert_called_once()

    def test_webhook_handles_timeout(self, webhook_config):
        from agent.webhook import WebhookClient
        client = WebhookClient(webhook_config)

        with patch("httpx.post", side_effect=Exception("Connection timeout")):
            result = client.send({"test": "data"})
            assert result["success"] is False
            assert "timeout" in result["error"].lower() or "connection" in result["error"].lower()

    def test_webhook_handles_4xx(self, webhook_config):
        from agent.webhook import WebhookClient
        client = WebhookClient(webhook_config)

        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_post.return_value = mock_response

            result = client.send({"test": "data"})
            assert result["success"] is False
            assert result["status_code"] == 401