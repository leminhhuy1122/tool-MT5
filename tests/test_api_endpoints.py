# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Admin & Telegram API Route Handlers.
"""

from unittest.mock import patch
import pytest
from fastapi import HTTPException

from app.api.server import (
    admin_broadcast_custom,
    admin_broadcast_news,
    get_telegram_status,
    notifier,
    BroadcastCustomRequest,
    BroadcastNewsRequest,
)


def test_telegram_status_endpoint():
    """get_telegram_status trả về đúng thông số."""
    data = get_telegram_status()
    assert "enabled" in data
    assert "isConfigured" in data
    assert "chatId" in data
    assert "totalSent" in data
    assert "totalFailed" in data


def test_admin_broadcast_custom_success():
    """admin_broadcast_custom gửi tin nhắn thành công."""
    with patch.object(notifier, "send_custom_broadcast", return_value=True):
        req = BroadcastCustomRequest(message="Thị trường biến động mạnh đầu phiên Mỹ!")
        res = admin_broadcast_custom(req)
        assert res["ok"] is True
        assert "thành công" in res["message"]


def test_admin_broadcast_custom_empty_rejected():
    """admin_broadcast_custom từ chối tin nhắn rỗng."""
    req = BroadcastCustomRequest(message="   ")
    with pytest.raises(HTTPException) as exc_info:
        admin_broadcast_custom(req)
    assert exc_info.value.status_code == 400


def test_admin_broadcast_news_success():
    """admin_broadcast_news bắn tin tức và dự báo thành công."""
    with patch.object(notifier, "send_news_broadcast", return_value=True):
        req = BroadcastNewsRequest(
            title="US CPI MoM",
            country="USD",
            impact="HIGH",
            forecast="0.3%",
            previous="0.2%",
            bias_direction="BUY",
            reasoning="Lạm phát hạ nhiệt hỗ trợ vàng bứt phá.",
            custom_note="Canh buy vùng 3995-4000.",
        )
        res = admin_broadcast_news(req)
        assert res["ok"] is True
        assert "US CPI MoM" in res["message"]


def test_generate_calendar_digest_route():
    """Tự động tạo bản tin Lịch Kinh Tế từ endpoint."""
    from app.api.server import generate_calendar_digest, GenerateDigestRequest
    req = GenerateDigestRequest(use_ai=False)
    res = generate_calendar_digest(req)
    assert res["ok"] is True
    assert "LỊCH KINH TẾ" in res["content"]


def test_generate_gold_article_route():
    """Tự động tạo bài báo điểm tin vàng từ endpoint."""
    from app.api.server import generate_gold_article, GenerateArticleRequest
    req = GenerateArticleRequest(current_price=4002.5, change_pct=0.35, use_ai=False)
    res = generate_gold_article(req)
    assert res["ok"] is True
    assert "Giá vàng" in res["content"]
    assert "4.002,5 USD/ounce" in res["content"]


def test_publish_news_article_route():
    """Xuất bản trực tiếp bài viết lên Telegram."""
    from app.api.server import publish_news_article, PublishArticleRequest
    with patch.object(notifier, "send_raw_message", return_value=True):
        req = PublishArticleRequest(content="Bản tin kinh tế mẫu thử nghiệm")
        res = publish_news_article(req)
        assert res["ok"] is True
        assert "thành công" in res["message"]


def test_ai_news_settings_route():
    """Đọc cấu hình OpenAI API và auto-post."""
    from app.api.server import get_ai_news_settings
    res = get_ai_news_settings()
    assert "openai_configured" in res
    assert "openai_model" in res
    assert "auto_post_enabled" in res

