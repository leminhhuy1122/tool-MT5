# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Admin & Telegram API Route Handlers.
"""

from unittest.mock import MagicMock, patch
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


def test_get_setups_performance_route():
    """Kiểm tra endpoint /api/v1/performance/setups."""
    from app.api.server import get_setups_performance
    res = get_setups_performance()
    assert "hasData" in res
    assert "setups" in res


def test_get_ml_models_and_status_routes():
    """Kiểm tra endpoints /api/v1/ml/models và /api/v1/ml/status."""
    from app.api.server import get_ml_models, get_ml_system_status
    status_res = get_ml_system_status()
    assert "is_active" in status_res
    assert "mode" in status_res

    models_res = get_ml_models()
    assert "total_models" in models_res
    assert "models" in models_res
    assert isinstance(models_res["models"], list)


def test_mt5_trading_status_route():
    """Kiểm tra endpoint /api/v1/mt5-trading/status."""
    from app.api.server import get_mt5_trading_status
    res = get_mt5_trading_status()
    assert "enabled" in res
    assert "trade_allowed" in res
    assert "account" in res
    assert "open_positions" in res
    assert "fast_tick_interval_ms" in res
    assert res["fast_tick_interval_ms"] == 250


def test_mt5_trading_toggle_route():
    """Kiểm tra endpoint /api/v1/mt5-trading/toggle."""
    import app.api.server as srv
    from app.api.server import toggle_mt5_auto_trading, MT5ToggleTradingRequest
    mock_runner = MagicMock()
    mock_runner.toggle_mt5_auto_trading.return_value = True
    mock_runner.mt5_executor.is_trade_allowed.return_value = (True, "Sẵn sàng giao dịch")

    orig = srv.bot_runner
    try:
        srv.bot_runner = mock_runner
        res = toggle_mt5_auto_trading(MT5ToggleTradingRequest(enabled=True))
        assert res["ok"] is True
        assert res["enabled"] is True
        assert "ĐÃ BẬT" in res["message"]
    finally:
        srv.bot_runner = orig


def test_mt5_trading_lot_size_route():
    """Kiểm tra endpoint /api/v1/mt5-trading/lot-size."""
    import app.api.server as srv
    from app.api.server import set_mt5_lot_size, MT5LotSizeRequest
    mock_runner = MagicMock()
    mock_runner.set_mt5_lot_size.return_value = 0.05

    orig = srv.bot_runner
    try:
        srv.bot_runner = mock_runner
        res = set_mt5_lot_size(MT5LotSizeRequest(lot_size=0.05))
        assert res["ok"] is True
        assert res["lot_size"] == 0.05
    finally:
        srv.bot_runner = orig


def test_mt5_trading_open_positions_route():
    """Kiểm tra endpoint /api/v1/mt5-trading/positions."""
    from app.api.server import get_mt5_open_positions
    with patch("app.api.server._get_mt5_executor") as mock_get_exec:
        mock_exec = MagicMock()
        mock_exec.get_open_positions.return_value = []
        mock_get_exec.return_value = mock_exec

        res = get_mt5_open_positions()
        assert isinstance(res, list)
        assert len(res) == 0


def test_mt5_trading_close_all_route():
    """Kiểm tra endpoint /api/v1/mt5-trading/close-all."""
    import app.api.server as srv
    from app.api.server import close_all_mt5_positions
    from app.mt5.executor import OrderResult

    mock_runner = MagicMock()
    mock_runner.close_all_mt5_positions.return_value = [
        OrderResult(success=True, ticket=101, comment="Closed"),
    ]

    orig = srv.bot_runner
    try:
        srv.bot_runner = mock_runner
        res = close_all_mt5_positions()
        assert res["ok"] is True
        assert res["closed_count"] == 1
        assert res["total_attempted"] == 1
    finally:
        srv.bot_runner = orig
