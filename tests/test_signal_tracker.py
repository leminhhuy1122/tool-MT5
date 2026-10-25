# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Signal Tracker & Duplicate Filter.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.strategy.signal_models import (
    SignalDirection,
    SignalStatus,
    TradingSignal,
)
from app.strategy.signal_tracker import (
    SignalTracker,
    TrackerConfig,
)


def _make_signal(
    direction: SignalDirection = SignalDirection.BUY,
    entry_low: float = 1999.0,
    entry_high: float = 2001.0,
    sl: float = 1990.0,
    tp: float = 2020.0,
    symbol: str = "XAUUSD",
    created_at: datetime | None = None,
) -> TradingSignal:
    return TradingSignal(
        direction=direction,
        status=SignalStatus.ACTIVE,
        symbol=symbol,
        entry_price=2000.0,
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        stop_loss=sl,
        take_profit_1=tp,
        created_at=created_at or datetime.now(timezone.utc),
    )


class TestSignalTracker:
    """Test suite cho Signal Tracker."""

    def test_register_signal(self):
        """Đăng ký tín hiệu hợp lệ thành công."""
        tracker = SignalTracker()
        sig = _make_signal()
        success = tracker.register_signal(sig)
        assert success is True
        assert len(tracker.active_signals) == 1
        assert sig.expires_at is not None
        assert tracker.get_signal(sig.signal_id) == sig

    def test_register_wait_signal_rejected(self):
        """Tín hiệu WAIT không được lưu vào tracker."""
        tracker = SignalTracker()
        sig = TradingSignal(direction=SignalDirection.WAIT)
        success = tracker.register_signal(sig)
        assert success is False
        assert len(tracker.all_signals) == 0

    def test_duplicate_active_signal(self):
        """Không cho phép phát 2 tín hiệu cùng hướng đang active."""
        tracker = SignalTracker()
        sig1 = _make_signal(direction=SignalDirection.BUY)
        assert tracker.register_signal(sig1) is True

        sig2 = _make_signal(direction=SignalDirection.BUY)
        assert tracker.is_duplicate("XAUUSD", SignalDirection.BUY) is True
        assert tracker.register_signal(sig2) is False
        assert len(tracker.active_signals) == 1

    def test_cooldown_rejection(self):
        """Tín hiệu vừa kết thúc vẫn bị chặn nếu còn trong cooldown."""
        config = TrackerConfig(cooldown_minutes=30)
        tracker = SignalTracker(config)
        now = datetime.now(timezone.utc)
        sig1 = _make_signal(direction=SignalDirection.BUY, created_at=now)
        tracker.register_signal(sig1)

        # Giả lập tín hiệu 1 đã TP_REACHED
        sig1.status = SignalStatus.TP_REACHED

        # Kiểm tra sau 10 phút (< 30 phút cooldown)
        check_time = now + timedelta(minutes=10)
        assert tracker.is_duplicate("XAUUSD", SignalDirection.BUY, check_time=check_time) is True

        # Kiểm tra sau 35 phút (> 30 phút cooldown) -> Cho phép
        check_time_passed = now + timedelta(minutes=35)
        assert tracker.is_duplicate("XAUUSD", SignalDirection.BUY, check_time=check_time_passed) is False

    def test_max_active_signals_limit(self):
        """Vượt quá max_active_signals sẽ bị chặn."""
        config = TrackerConfig(max_active_signals=2, cooldown_minutes=0)
        tracker = SignalTracker(config)

        sig1 = _make_signal(symbol="XAUUSD", direction=SignalDirection.BUY)
        sig2 = _make_signal(symbol="EURUSD", direction=SignalDirection.BUY)
        sig3 = _make_signal(symbol="GBPUSD", direction=SignalDirection.BUY)

        assert tracker.register_signal(sig1) is True
        assert tracker.register_signal(sig2) is True
        assert tracker.register_signal(sig3) is False  # Đạt giới hạn 2

    def test_update_price_entry_reached(self):
        """Giá vào vùng entry -> chuyển status sang ENTRY_REACHED."""
        tracker = SignalTracker()
        sig = _make_signal(entry_low=1999.0, entry_high=2001.0)
        tracker.register_signal(sig)

        # Giá 2005 chưa vào entry
        changed = tracker.update_price(current_price=2005.0)
        assert len(changed) == 0
        assert sig.status == SignalStatus.ACTIVE

        # Giá 2000.5 chạm entry
        changed = tracker.update_price(current_price=2000.5)
        assert len(changed) == 1
        assert sig.status == SignalStatus.ENTRY_REACHED

    def test_update_price_buy_tp_and_sl(self):
        """BUY: ENTRY_REACHED -> TP_REACHED hoặc SL_REACHED."""
        tracker = SignalTracker()
        sig = _make_signal(entry_low=1999.0, entry_high=2001.0, sl=1990.0, tp=2020.0)
        tracker.register_signal(sig)
        sig.status = SignalStatus.ENTRY_REACHED

        # Chạm TP (high = 2021)
        changed = tracker.update_price(current_price=2015.0, high_price=2021.0, low_price=2010.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.TP_REACHED
        assert sig.is_active is False

    def test_update_price_sell_tp_and_sl(self):
        """SELL: ENTRY_REACHED -> TP_REACHED hoặc SL_REACHED."""
        tracker = SignalTracker()
        sig = _make_signal(
            direction=SignalDirection.SELL,
            entry_low=1999.0,
            entry_high=2001.0,
            sl=2010.0,
            tp=1980.0,
        )
        tracker.register_signal(sig)
        sig.status = SignalStatus.ENTRY_REACHED

        # Chạm SL (high = 2011)
        changed = tracker.update_price(current_price=2005.0, high_price=2011.0, low_price=2000.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.SL_REACHED

    def test_update_price_invalidation_before_entry(self):
        """Giá chạm SL trước khi khớp entry -> INVALIDATED."""
        tracker = SignalTracker()
        sig = _make_signal(direction=SignalDirection.BUY, sl=1990.0)
        tracker.register_signal(sig)

        # Giá rơi thẳng qua SL (low = 1988) khi còn ACTIVE
        changed = tracker.update_price(current_price=1989.0, high_price=1995.0, low_price=1988.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.INVALIDATED

    def test_update_price_expired(self):
        """Tín hiệu quá thời hạn -> EXPIRED."""
        tracker = SignalTracker()
        now = datetime.now(timezone.utc)
        sig = _make_signal(created_at=now - timedelta(hours=15))
        tracker.register_signal(sig)
        sig.expires_at = now - timedelta(hours=1)  # Đã quá hạn

        changed = tracker.update_price(current_price=2000.0, current_time=now)
        assert len(changed) == 1
        assert sig.status == SignalStatus.EXPIRED

    def test_clear_tracker(self):
        """Xóa sạch bộ nhớ tracker."""
        tracker = SignalTracker()
        tracker.register_signal(_make_signal())
        assert len(tracker.all_signals) == 1
        tracker.clear()
        assert len(tracker.all_signals) == 0
