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

    def test_load_active_signals_restoration(self):
        """Khôi phục các tín hiệu active từ nguồn bên ngoài (DB) và chặn trùng lặp."""
        tracker = SignalTracker()
        sig1 = _make_signal(direction=SignalDirection.SELL)
        sig1.signal_id = "sig_active_1"
        sig2 = _make_signal(direction=SignalDirection.BUY)
        sig2.signal_id = "sig_done_2"
        sig2.status = SignalStatus.TP_REACHED

        # Nạp vào tracker
        tracker.load_active_signals([sig1, sig2])

        # Chỉ có tín hiệu active được nạp vào
        assert len(tracker.active_signals) == 1
        assert tracker.get_signal("sig_active_1") is not None
        assert tracker.get_signal("sig_done_2") is None

        # Kiểm tra chống trùng lặp nhận diện đúng tín hiệu đã khôi phục
        assert tracker.is_duplicate("XAUUSD", SignalDirection.SELL) is True

    def test_active_signal_invalidated_when_tp_hit_before_entry(self):
        """Nếu giá chạm TP1 mà chưa từng khớp Entry thì hủy lệnh (kèo đã chạy xong)."""
        tracker = SignalTracker(config=TrackerConfig(max_unfilled_distance_pts=15.0, unfilled_expiry_minutes=60))
        sig = TradingSignal(
            signal_id="sig_missed",
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            status=SignalStatus.ACTIVE,
            entry_price=4009.0,
            entry_zone_low=4008.0,
            entry_zone_high=4010.0,
            stop_loss=3998.0,
            take_profit_1=4018.0,
            created_at=datetime.now(timezone.utc),
        )
        tracker.register_signal(sig)

        # Giá tăng từ 4012 lên 4020 (chạm TP1 4018) mà không chạm đáy 4010
        changed = tracker.update_price(current_price=4020.0, high_price=4020.0, low_price=4012.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.INVALIDATED
        assert "TP1" in sig.invalidation

    def test_active_signal_invalidated_when_out_of_reach(self):
        """Nếu giá đi quá xa vùng Entry (>= 8 giá) mà không khớp thì hủy lệnh chờ để đón kèo mới."""
        tracker = SignalTracker(config=TrackerConfig(max_unfilled_distance_pts=8.0, unfilled_expiry_minutes=60))
        sig = TradingSignal(
            signal_id="sig_far",
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            status=SignalStatus.ACTIVE,
            entry_price=4010.0,
            entry_zone_low=4008.0,
            entry_zone_high=4010.0,
            stop_loss=3998.0,
            take_profit_1=4035.0,
            created_at=datetime.now(timezone.utc),
        )
        tracker.register_signal(sig)

        # Giá bay lên 4019 (cách entry_zone_high 4010 là 9 giá >= 8 giá)
        changed = tracker.update_price(current_price=4019.0, high_price=4019.0, low_price=4012.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.INVALIDATED
        assert "quá xa" in sig.invalidation

    def test_active_signal_expired_when_unfilled_timeout(self):
        """Nếu quá 45 phút chưa khớp entry thì hủy hết hạn (EXPIRED)."""
        tracker = SignalTracker(config=TrackerConfig(max_unfilled_distance_pts=15.0, unfilled_expiry_minutes=45))
        old_time = datetime.now(timezone.utc) - timedelta(minutes=50)
        sig = TradingSignal(
            signal_id="sig_stale",
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            status=SignalStatus.ACTIVE,
            entry_price=4010.0,
            entry_zone_low=4008.0,
            entry_zone_high=4010.0,
            stop_loss=3998.0,
            take_profit_1=4035.0,
            created_at=old_time,
        )
        tracker._signals[sig.signal_id] = sig

        changed = tracker.update_price(current_price=4013.0, high_price=4014.0, low_price=4012.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.EXPIRED


