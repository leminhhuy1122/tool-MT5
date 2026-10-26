# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Telegram Formatter.
"""

from datetime import datetime, timezone
import pytest

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.telegram.formatter import (
    format_signal_message,
    format_signal_update,
    format_system_notification,
)


def _make_buy_signal() -> TradingSignal:
    return TradingSignal(
        signal_id="sig12345",
        strategy_version="v1.0",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        symbol="XAUUSD",
        timeframe="H1",
        entry_price=2000.0,
        entry_zone_low=1999.0,
        entry_zone_high=2001.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        risk_reward_ratio=2.0,
        sl_distance=10.0,
        tp_distance=20.0,
        score=78.5,
        confidence="HIGH",
        trend_h4="BULLISH",
        trend_h1="BULLISH",
        setup_type="BOS_RETEST",
        reasons=["BOS Bullish xác nhận", "Retest vùng Support 2000.00", "RSI neutral"],
        invalidation="Nến H1 đóng cửa dưới 1990.00",
        created_at=datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc),
    )


class TestTelegramFormatter:
    """Test suite cho Telegram Formatter."""

    def test_format_buy_signal(self):
        """Kiểm tra format tin nhắn tín hiệu BUY chuẩn phong cách ngắn gọn."""
        sig = _make_buy_signal()
        text = format_signal_message(sig)

        assert "🏆 <b>BUY Gold: <code>2000.0</code></b>" in text
        assert "❌ <b>SL:</b> <code>1990.0</code>" in text
        assert "✅ <b>TP1:</b> <code>2020.0</code>" in text
        assert "✅ <b>TP2:</b> <code>2030.0</code>" in text
        assert "Entry (điểm vào lệnh) ±1 giá." in text
        assert "Lãi 5 giá → Kéo SL về hòa vốn (BE)." in text
        assert "Lãi 10 giá → Chốt 1 phần, kéo SL dương nuôi TP." in text
        assert "1:2.0" in text
        assert "78/100" in text
        assert "HIGH" in text
        assert "BOS_RETEST" in text
        assert "Nến H1 đóng cửa dưới 1990.00" in text
        assert "#sig12345" in text
        assert "v1.0" in text

    def test_format_sell_signal(self):
        """Kiểm tra format tin nhắn tín hiệu SELL chuẩn phong cách ngắn gọn."""
        sig = _make_buy_signal()
        sig.direction = SignalDirection.SELL
        sig.entry_price = 2000.0
        sig.stop_loss = 2010.0
        sig.take_profit_1 = 1980.0
        sig.take_profit_2 = 1970.0
        text = format_signal_message(sig)

        assert "🔴 <b>SELL Gold: <code>2000.0</code></b>" in text
        assert "❌ <b>SL:</b> <code>2010.0</code>" in text
        assert "✅ <b>TP1:</b> <code>1980.0</code>" in text
        assert "✅ <b>TP2:</b> <code>1970.0</code>" in text

    def test_format_wait_signal(self):
        """Kiểm tra format tin nhắn tín hiệu WAIT."""
        sig = TradingSignal(
            direction=SignalDirection.WAIT,
            symbol="XAUUSD",
            timeframe="H1",
            trend_h4="BEARISH",
            trend_h1="NEUTRAL",
            reasons=["Thị trường đang sideway"],
        )
        text = format_signal_message(sig)

        assert "CHỜ SETUP (WAIT)" in text
        assert "BEARISH" in text
        assert "Thị trường đang sideway" in text

    def test_format_signal_update_entry_reached(self):
        """Kiểm tra format cập nhật ENTRY_REACHED."""
        sig = _make_buy_signal()
        sig.status = SignalStatus.ENTRY_REACHED
        text = format_signal_update(sig, price=2000.5)

        assert "KHỚP ENTRY" in text
        assert "2000.5" in text
        assert "#sig12345" in text
        assert "Lãi 5 giá nhớ kéo SL về hòa vốn!" in text

    def test_format_signal_update_tp_reached(self):
        """Kiểm tra format cập nhật TP_REACHED."""
        sig = _make_buy_signal()
        sig.status = SignalStatus.TP_REACHED
        text = format_signal_update(sig, price=2020.5)

        assert "TAKE PROFIT THÀNH CÔNG" in text
        assert "+2.0R" in text
        assert "+20.0 giá" in text
        assert "Chốt 1 phần, dời SL dương" in text

    def test_format_signal_update_sl_reached(self):
        """Kiểm tra format cập nhật SL_REACHED."""
        sig = _make_buy_signal()
        sig.status = SignalStatus.SL_REACHED
        text = format_signal_update(sig, price=1989.5)

        assert "STOP LOSS" in text
        assert "-10.0 giá" in text

    def test_format_signal_update_invalidated(self):
        """Kiểm tra format cập nhật INVALIDATED."""
        sig = _make_buy_signal()
        sig.status = SignalStatus.INVALIDATED
        text = format_signal_update(sig, price=1995.0, custom_message="Tin tức CPI bất thường")

        assert "HỦY SETUP" in text
        assert "Tin tức CPI bất thường" in text

    def test_format_signal_update_expired(self):
        """Kiểm tra format cập nhật EXPIRED."""
        sig = _make_buy_signal()
        sig.status = SignalStatus.EXPIRED
        text = format_signal_update(sig, price=2005.0)

        assert "HẾT HẠN" in text

    def test_format_system_notification(self):
        """Kiểm tra format thông báo hệ thống."""
        text_startup = format_system_notification("STARTUP", "Hệ thống đã khởi động thành công.")
        assert "HỆ THỐNG: STARTUP" in text_startup
        assert "Hệ thống đã khởi động thành công." in text_startup

        text_error = format_system_notification("ERROR", "Mất kết nối với sàn MT5.")
        assert "HỆ THỐNG: ERROR" in text_error
        assert "Mất kết nối với sàn MT5." in text_error

    def test_format_early_exit_alert(self):
        """Kiểm tra format cảnh báo thoát lệnh sớm (Early Structural Exit)."""
        from app.telegram.formatter import format_early_exit_alert
        sig = _make_buy_signal()
        sig.direction = SignalDirection.SELL
        sig.stop_loss = 4003.34
        text = format_early_exit_alert(sig, close_price=4000.80, invalidation_level=4000.42)

        assert "CẢNH BÁO CẤU TRÚC (THOÁT LỆNH SỚM): SELL Gold" in text
        assert "4000.80" in text
        assert "4000.42" in text
        assert "4003.34" in text
        assert "Giảm thiểu được" in text
