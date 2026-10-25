# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Signal Models.
"""

from datetime import datetime, timezone
import pytest

from app.strategy.signal_models import (
    SignalDirection,
    SignalStatus,
    TradingSignal,
)


class TestSignalModels:
    """Test suite cho Signal Models."""

    def test_signal_direction_enums(self):
        """Kiểm tra các giá trị của SignalDirection."""
        assert SignalDirection.BUY.value == "BUY"
        assert SignalDirection.SELL.value == "SELL"
        assert SignalDirection.WAIT.value == "WAIT"

    def test_signal_status_enums(self):
        """Kiểm tra các giá trị của SignalStatus."""
        assert SignalStatus.ACTIVE.value == "ACTIVE"
        assert SignalStatus.ENTRY_REACHED.value == "ENTRY_REACHED"
        assert SignalStatus.TP_REACHED.value == "TP_REACHED"
        assert SignalStatus.SL_REACHED.value == "SL_REACHED"
        assert SignalStatus.INVALIDATED.value == "INVALIDATED"
        assert SignalStatus.EXPIRED.value == "EXPIRED"
        assert SignalStatus.UNRESOLVED.value == "UNRESOLVED"

    def test_default_trading_signal(self):
        """Kiểm tra giá trị mặc định của TradingSignal."""
        sig = TradingSignal()
        assert sig.direction == SignalDirection.WAIT
        assert sig.status == SignalStatus.ACTIVE
        assert sig.symbol == "XAUUSD"
        assert sig.timeframe == "H1"
        assert sig.is_wait is True
        assert sig.is_buy is False
        assert sig.is_sell is False
        assert sig.is_active is True

    def test_buy_trading_signal_properties(self):
        """Kiểm tra properties của BUY TradingSignal."""
        sig = TradingSignal(
            direction=SignalDirection.BUY,
            status=SignalStatus.ACTIVE,
            entry_price=2000.0,
            entry_zone_low=1998.0,
            entry_zone_high=2002.0,
            stop_loss=1990.0,
            take_profit_1=2020.0,
            risk_reward_ratio=2.0,
            sl_distance=10.0,
            tp_distance=20.0,
            score=75.0,
            confidence="HIGH",
            setup_type="BOS_RETEST",
            reasons=["BOS Bullish", "Trend Bullish"],
            invalidation="Close dưới 1990.00",
        )
        assert sig.is_buy is True
        assert sig.is_sell is False
        assert sig.is_wait is False
        assert sig.is_active is True

        summary = sig.summary()
        assert "BUY XAUUSD" in summary
        assert "Entry: 1998.00 – 2002.00" in summary
        assert "SL: 1990.00" in summary
        assert "TP1: 2020.00" in summary
        assert "Score: 75/100 (HIGH)" in summary

    def test_wait_trading_signal_summary(self):
        """Kiểm tra summary của WAIT TradingSignal."""
        sig = TradingSignal(
            direction=SignalDirection.WAIT,
            reasons=["Thị trường sideway"],
        )
        assert "WAIT — Thị trường sideway" in sig.summary()

    def test_inactive_statuses(self):
        """Kiểm tra is_active khi ở các trạng thái kết thúc."""
        sig = TradingSignal(direction=SignalDirection.BUY, status=SignalStatus.TP_REACHED)
        assert sig.is_active is False

        sig.status = SignalStatus.SL_REACHED
        assert sig.is_active is False

        sig.status = SignalStatus.INVALIDATED
        assert sig.is_active is False

        sig.status = SignalStatus.EXPIRED
        assert sig.is_active is False

        sig.status = SignalStatus.ENTRY_REACHED
        assert sig.is_active is True
