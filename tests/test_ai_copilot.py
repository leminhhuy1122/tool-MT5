# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for AI Trading Copilot Companion.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.strategy.ai_companion import AITradingCopilot
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal


@pytest.fixture
def buy_signal():
    return TradingSignal(
        signal_id="SIG-COPILOT-001",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.BUY,
        entry_price=2700.0,
        stop_loss=2692.0,
        take_profit_1=2715.0,
        invalidation_level=2694.0,
        status=SignalStatus.ENTRY_REACHED,
    )


@pytest.fixture
def sell_signal():
    return TradingSignal(
        signal_id="SIG-COPILOT-002",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.SELL,
        entry_price=2700.0,
        stop_loss=2708.0,
        take_profit_1=2685.0,
        invalidation_level=2706.0,
        status=SignalStatus.ENTRY_REACHED,
    )


def test_copilot_green_alert(buy_signal):
    copilot = AITradingCopilot(min_message_interval_minutes=0.0)
    now = datetime.now(timezone.utc)

    # 1. Giá tăng lên 2704.0 (+4.0 giá -> Xanh)
    msg = copilot.evaluate(buy_signal, current_price=2704.0, now_utc=now)
    assert msg is not None
    assert "LỆNH BẮT ĐẦU XANH MƯỚT" in msg
    assert "Stop Loss về Hòa Vốn (BE)" in msg
    assert "+4.0 giá" in msg

    # 2. Không gửi lại lần thứ hai (Anti-spam)
    msg2 = copilot.evaluate(buy_signal, current_price=2705.0, now_utc=now + timedelta(seconds=10))
    assert msg2 is None


def test_copilot_pullback_reassurance(sell_signal):
    copilot = AITradingCopilot(min_message_interval_minutes=0.0)
    now = datetime.now(timezone.utc)

    # 1. SELL ở 2700.0, giá giật nhẹ lên 2702.5 (âm 2.5 giá, cản 2706 chưa thủng)
    msg = copilot.evaluate(sell_signal, current_price=2702.5, now_utc=now)
    assert msg is not None
    assert "NHỊP RUNG LẮC QUÉT THANH KHOẢN" in msg
    assert "gồng qua cơn sóng này" in msg
    assert "-2.5 giá" in msg

    # 2. Không lặp lại
    msg2 = copilot.evaluate(sell_signal, current_price=2703.0, now_utc=now + timedelta(seconds=10))
    assert msg2 is None


def test_copilot_trend_broken_cut_warning(buy_signal):
    copilot = AITradingCopilot(min_message_interval_minutes=0.0)
    now = datetime.now(timezone.utc)

    # BUY ở 2700, cản 2694. Giá rơi thủng cản xuống 2693.0
    msg = copilot.evaluate(buy_signal, current_price=2693.0, now_utc=now)
    assert msg is not None
    assert "CẢNH BÁO LỆCH XU HƯỚNG THỊ TRƯỜNG" in msg
    assert "chủ động cắt lệnh sớm" in msg
    assert "đừng cố chấp gồng lỗ" in msg


def test_copilot_interval_capping(buy_signal):
    # Cấu hình interval 15 phút
    copilot = AITradingCopilot(min_message_interval_minutes=15.0)
    now = datetime.now(timezone.utc)

    # Lần 1: Xanh -> gửi
    msg1 = copilot.evaluate(buy_signal, current_price=2704.0, now_utc=now)
    assert msg1 is not None

    # Lần 2: 5 phút sau biến động khác -> bị chặn bởi interval
    buy_signal.signal_id = "SIG-COPILOT-ANOTHER"
    msg2 = copilot.evaluate(buy_signal, current_price=2690.0, now_utc=now + timedelta(minutes=5))
    assert msg2 is None

    # Lần 3: 20 phút sau (> 15 phút) -> được gửi
    msg3 = copilot.evaluate(buy_signal, current_price=2690.0, now_utc=now + timedelta(minutes=20))
    assert msg3 is not None
