# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Telegram Client.
"""

import io
import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from app.telegram.client import TelegramClient, TelegramResponse
from config import TelegramConfig


class TestTelegramClient:
    """Test suite cho TelegramClient."""

    def test_client_initialization_with_config(self):
        """Khởi tạo client từ TelegramConfig."""
        cfg = TelegramConfig(bot_token="test_token", chat_id="123456", enabled=True)
        client = TelegramClient(config=cfg)

        assert client.bot_token == "test_token"
        assert client.chat_id == "123456"
        assert client.enabled is True
        assert client.is_configured is True

    def test_client_is_configured_false_when_missing_values(self):
        """is_configured trả về False khi thiếu token hoặc chat_id."""
        c1 = TelegramClient(bot_token="", chat_id="123")
        assert c1.is_configured is False

        c2 = TelegramClient(bot_token="abc", chat_id="")
        assert c2.is_configured is False

        c3 = TelegramClient(config=TelegramConfig(bot_token="abc", chat_id="123", enabled=False))
        assert c3.is_configured is False

    def test_send_message_missing_token(self):
        """Thiếu bot_token trả về TelegramResponse(ok=False)."""
        client = TelegramClient(bot_token="", chat_id="123")
        resp = client.send_message("Hello")
        assert resp.ok is False
        assert "Missing bot_token" in resp.description

    def test_send_message_missing_chat_id(self):
        """Thiếu chat_id trả về TelegramResponse(ok=False)."""
        client = TelegramClient(bot_token="abc", chat_id="")
        resp = client.send_message("Hello")
        assert resp.ok is False
        assert "Missing chat_id" in resp.description

    def test_send_message_empty_text(self):
        """Nội dung tin nhắn rỗng trả về TelegramResponse(ok=False)."""
        client = TelegramClient(bot_token="abc", chat_id="123")
        resp = client.send_message("")
        assert resp.ok is False
        assert "Empty message text" in resp.description

    @patch("urllib.request.urlopen")
    def test_send_message_success(self, mock_urlopen):
        """Gửi tin nhắn thành công qua Telegram Bot API."""
        mock_resp_data = {
            "ok": True,
            "result": {
                "message_id": 9999,
                "chat": {"id": 123456},
                "text": "Hello Telegram",
            },
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = TelegramClient(bot_token="fake_token", chat_id="123456")
        resp = client.send_message("<b>Hello</b>")

        assert resp.ok is True
        assert resp.message_id == 9999
        assert "OK" in str(resp)

    @patch("urllib.request.urlopen")
    def test_send_message_api_error_response(self, mock_urlopen):
        """Xử lý khi Telegram API trả về ok=False."""
        mock_resp_data = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: can't parse entities",
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = TelegramClient(bot_token="fake_token", chat_id="123456")
        resp = client.send_message("Broken HTML")

        assert resp.ok is False
        assert resp.error_code == 400
        assert "can't parse entities" in resp.description
        assert "FAIL" in str(resp)

    @patch("urllib.request.urlopen")
    def test_send_message_http_error(self, mock_urlopen):
        """Xử lý HTTPError từ urllib."""
        err_body = json.dumps({"ok": False, "error_code": 401, "description": "Unauthorized"}).encode("utf-8")
        http_err = urllib.error.HTTPError(
            url="http://test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(err_body),
        )
        mock_urlopen.side_effect = http_err

        client = TelegramClient(bot_token="wrong_token", chat_id="123456", max_retries=1)
        resp = client.send_message("Test")

        assert resp.ok is False
        assert resp.error_code == 401

    @patch("urllib.request.urlopen")
    def test_verify_connection_true(self, mock_urlopen):
        """verify_connection trả về True khi getMe thành công."""
        mock_resp_data = {"ok": True, "result": {"id": 123, "is_bot": True, "first_name": "VietKeyBot"}}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = TelegramClient(bot_token="valid_token", chat_id="123456")
        assert client.verify_connection() is True

    def test_verify_connection_missing_token(self):
        """verify_connection trả về False khi không có token."""
        client = TelegramClient(bot_token="", chat_id="123")
        assert client.verify_connection() is False
