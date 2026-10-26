# -*- coding: utf-8 -*-
"""
Tests for Smart Profit Protection & Dynamic Exit features in VietKey Gold AI.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pandas as pd
import pytest

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_tracker import SignalTracker
from app.telegram.formatter import (
    format_momentum_exhaustion_alert,
    format_time_stagnation_alert,
    format_trailing_stop_update,
)


def test_format_momentum_exhaustion_alert():
    sig = TradingSignal(
        signal_id="TEST01",
        direction=SignalDirection.BUY,
        symbol="XAUUSD",
        entry_price=2730.0,
        stop_loss=2720.0,
        take_profit_1=2745.0,
    )
    msg = format_momentum_exhaustion_alert(
        signal=sig,
        current_price=2734.5,
        pnl_points=4.5,
        exhaustion_reason="Râu từ chối bán 60% tại đỉnh 2736.0",
    )
    assert "CẢNH BÁO ĐỘNG LƯỢNG SUY YẾU" in msg
    assert "+4.50 giá" in msg
    assert "+45.0 pips" in msg
    assert "BUY Gold" in msg


def test_format_time_stagnation_alert():
    sig = TradingSignal(
        signal_id="TEST02",
        direction=SignalDirection.SELL,
        symbol="XAUUSD",
        entry_price=2740.0,
        stop_loss=2750.0,
        take_profit_1=2725.0,
    )
    msg = format_time_stagnation_alert(
        signal=sig,
        current_price=2736.8,
        pnl_points=3.2,
        minutes_open=65,
    )
    assert "CẢNH BÁO LỆNH Ứ ĐỌNG (TIME DECAY)" in msg
    assert "65 phút" in msg
    assert "+3.20 giá" in msg


def test_format_trailing_stop_update():
    sig = TradingSignal(
        signal_id="TEST03",
        direction=SignalDirection.BUY,
        symbol="XAUUSD",
        entry_price=2730.0,
        stop_loss=2720.0,
        take_profit_1=2740.0,
        take_profit_2=2755.0,
    )
    msg = format_trailing_stop_update(
        signal=sig,
        current_price=2738.5,
        old_sl=2720.0,
        new_sl=2730.5,
        locked_points=0.5,
    )
    assert "BẢO VỆ LỢI NHUẬN (TRAILING STOP)" in msg
    assert "2720.00" in msg
    assert "2730.50" in msg
    assert "+0.50 giá" in msg


def test_runner_trailing_stop_and_breakeven():
    from app.bot.runner import LiveBotRunner

    runner = LiveBotRunner.__new__(LiveBotRunner)
    runner.tracker = SignalTracker()
    runner.signal_repo = MagicMock()
    runner.notifier = MagicMock()
    runner.notifier.is_enabled = True

    # 1. Test BUY Signal at +5.5 giá -> Breakeven moved to 2730.5
    buy_sig = TradingSignal(
        signal_id="BUY01",
        direction=SignalDirection.BUY,
        status=SignalStatus.ENTRY_REACHED,
        entry_price=2730.0,
        stop_loss=2720.0,
        take_profit_1=2745.0,
    )
    runner.tracker._signals["BUY01"] = buy_sig

    runner.check_trailing_stop_and_breakeven(current_price=2735.5)

    assert buy_sig.stop_loss == 2730.5
    runner.signal_repo.update_stop_loss.assert_called_with("BUY01", 2730.5)
    runner.notifier.send_trailing_stop_update.assert_called()

    # 2. Test BUY Signal reaches +9.0 giá -> Trailing Stop moved to max(2739 - 3.5 = 2735.5, 2734) = 2735.5
    runner.check_trailing_stop_and_breakeven(current_price=2739.0)
    assert buy_sig.stop_loss == 2735.5
    runner.signal_repo.update_stop_loss.assert_called_with("BUY01", 2735.5)


def test_runner_rejection_wick_detection():
    from app.bot.runner import LiveBotRunner

    runner = LiveBotRunner.__new__(LiveBotRunner)
    runner.tracker = SignalTracker()
    runner.signal_repo = MagicMock()
    runner.notifier = MagicMock()
    runner.notifier.is_enabled = True

    buy_sig = TradingSignal(
        signal_id="BUY02",
        direction=SignalDirection.BUY,
        status=SignalStatus.ENTRY_REACHED,
        entry_price=2730.0,
        stop_loss=2730.5,
        take_profit_1=2745.0,
    )
    runner.tracker._signals["BUY02"] = buy_sig

    # Tạo nến M5 có râu trên dài (High 2736, Open 2734, Close 2733.8, Low 2733.5)
    # Range = 2.5, Upper wick = 2736 - 2734 = 2.0 (80% râu)
    df_m5 = pd.DataFrame([
        {"time": "2026-10-26 10:00:00", "open": 2732.0, "high": 2733.0, "low": 2731.0, "close": 2732.5},
        {"time": "2026-10-26 10:05:00", "open": 2734.0, "high": 2736.0, "low": 2733.5, "close": 2733.8},
    ])

    runner.check_momentum_exhaustion_and_stagnation(
        df_m5=df_m5,
        current_price=2733.8,
        now_utc=datetime.now(timezone.utc),
    )

    runner.notifier.send_momentum_exhaustion_alert.assert_called_once()
