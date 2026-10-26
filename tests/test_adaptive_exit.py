# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Adaptive Exit & Smart Profit Protection Tests (Phase 12).

Kiểm thử toàn diện động cơ quản lý thoát lệnh thông minh:
1. Dynamic Breakeven (BUY & SELL).
2. Tự động bù đệm Spread thực tế vào mức hòa vốn.
3. Breakeven sớm trong Regime COMPRESSION_SQUEEZE & RANGING.
4. Regime-Adaptive Trailing Stop (ATR co giãn theo High Volatility vs Ranging vs Trending).
5. Swing Structure Trailing Stop bám sát đáy/đỉnh nến M5.
6. Quy tắc chốt lời từng bậc Multi-Tier Scaled Exits (50/30/20).
7. Cảnh báo suy yếu động lượng (Momentum Exhaustion Rejection Wick).
8. Cảnh báo lệnh ứ đọng (Time Stagnation Decay).
9. Thông báo Telegram Scaled Exit Formatters.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.smart_exit import ExitActionType, ExitDecision, SmartExitConfig, SmartExitEngine
from app.telegram.formatter import format_scaled_exit_alert
from app.telegram.notifier import TelegramNotifier


@pytest.fixture
def sample_buy_signal():
    return TradingSignal(
        signal_id="SIG_BUY_01",
        direction=SignalDirection.BUY,
        status=SignalStatus.ENTRY_REACHED,
        entry_price=2700.0,
        stop_loss=2690.0,
        take_profit_1=2715.0,
        take_profit_2=2730.0,
        sl_distance=10.0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_sell_signal():
    return TradingSignal(
        signal_id="SIG_SELL_01",
        direction=SignalDirection.SELL,
        status=SignalStatus.ENTRY_REACHED,
        entry_price=2700.0,
        stop_loss=2710.0,
        take_profit_1=2685.0,
        take_profit_2=2670.0,
        sl_distance=10.0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_m5_df():
    data = []
    base_price = 2700.0
    for i in range(10):
        t = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=5 * i)
        o = base_price + i * 1.0
        h = o + 2.0
        l = o - 0.5
        c = o + 1.5
        data.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "atr_14": 2.2,
        })
    return pd.DataFrame(data)


class TestAdaptiveExitEngine:
    """Bộ kiểm thử cho SmartExitEngine."""

    # 1. Dynamic Breakeven BUY
    def test_dynamic_breakeven_buy(self, sample_buy_signal):
        engine = SmartExitEngine(SmartExitConfig(enable_scaled_exits=False))
        # Giá chạy từ 2700 lên 2705.5 (+5.5 giá)
        decisions = engine.evaluate_signal(
            signal=sample_buy_signal,
            current_price=2705.5,
            current_spread=0.25,
        )
        be_dec = next((d for d in decisions if d.action_type == ExitActionType.MOVE_BREAKEVEN), None)
        assert be_dec is not None
        assert be_dec.new_sl == 2700.5
        assert be_dec.locked_points == 0.5
        assert sample_buy_signal.stop_loss == 2700.5

    # 2. Dynamic Breakeven SELL
    def test_dynamic_breakeven_sell(self, sample_sell_signal):
        engine = SmartExitEngine(SmartExitConfig(enable_scaled_exits=False))
        # Giá giảm từ 2700 về 2694.5 (+5.5 giá lãi)
        decisions = engine.evaluate_signal(
            signal=sample_sell_signal,
            current_price=2694.5,
            current_spread=0.25,
        )
        be_dec = next((d for d in decisions if d.action_type == ExitActionType.MOVE_BREAKEVEN), None)
        assert be_dec is not None
        assert be_dec.new_sl == 2699.5
        assert be_dec.locked_points == 0.5
        assert sample_sell_signal.stop_loss == 2699.5

    # 3. Tự động bù đệm Spread cao vào Breakeven
    def test_spread_adaptive_breakeven(self, sample_buy_signal):
        engine = SmartExitEngine(SmartExitConfig(enable_scaled_exits=False))
        # Ban đêm hoặc giờ ra tin spread giãn lên 0.9 giá
        decisions = engine.evaluate_signal(
            signal=sample_buy_signal,
            current_price=2706.0,
            current_spread=0.9,
        )
        be_dec = next((d for d in decisions if d.action_type == ExitActionType.MOVE_BREAKEVEN), None)
        assert be_dec is not None
        # be_cushion = max(0.5, 0.9 + 0.2) = 1.1 giá
        assert be_dec.new_sl == 2701.1
        assert be_dec.locked_points == 1.1

    # 4. Kích hoạt Breakeven sớm trong Regime COMPRESSION_SQUEEZE
    def test_regime_adaptive_breakeven_compression(self, sample_buy_signal):
        engine = SmartExitEngine(SmartExitConfig(enable_scaled_exits=False))
        df = pd.DataFrame([{"atr_14": 1.5}])
        # Trong thị trường ép nén, ngưỡng BE chỉ là min(10, 1.2*1.5=1.8, 4.0) = 1.8 giá
        decisions = engine.evaluate_signal(
            signal=sample_buy_signal,
            current_price=2702.5,  # Lãi chỉ +2.5 giá
            df_m5=df,
            market_regime="COMPRESSION_SQUEEZE",
        )
        be_dec = next((d for d in decisions if d.action_type == ExitActionType.MOVE_BREAKEVEN), None)
        assert be_dec is not None
        assert be_dec.new_sl == 2700.5

    # 5. Regime-Adaptive Trailing Stop: HIGH_VOLATILITY (ATR k = 2.0)
    def test_regime_adaptive_trailing_high_volatility(self, sample_buy_signal):
        engine = SmartExitEngine()
        df = pd.DataFrame([{"atr_14": 3.0}] * 5)
        # Giá chạy lên 2718 (+18 giá)
        decisions = engine.evaluate_signal(
            signal=sample_buy_signal,
            current_price=2718.0,
            df_m5=df,
            market_regime="HIGH_VOLATILITY_EXPANSION",
        )
        trail_dec = next((d for d in decisions if d.action_type == ExitActionType.TRAILING_UPDATE), None)
        assert trail_dec is not None
        # k = 2.0, atr = 3.0 -> atr_dist = 6.0 giá -> new_sl = 2718.0 - 6.0 = 2712.0
        assert trail_dec.new_sl == 2712.0
        assert trail_dec.locked_points == 12.0

    # 6. Regime-Adaptive Trailing Stop: RANGING (ATR k = 1.0)
    def test_regime_adaptive_trailing_ranging(self, sample_buy_signal):
        engine = SmartExitEngine()
        df = pd.DataFrame([{"atr_14": 2.0}] * 5)
        # Giá chạy lên 2712 (+12 giá)
        decisions = engine.evaluate_signal(
            signal=sample_buy_signal,
            current_price=2712.0,
            df_m5=df,
            market_regime="RANGING",
        )
        trail_dec = next((d for d in decisions if d.action_type == ExitActionType.TRAILING_UPDATE), None)
        assert trail_dec is not None
        # k = 1.0, atr = 2.0 -> atr_dist = max(2.5, 2.0) = 2.5 giá -> new_sl = 2712.0 - 2.5 = 2709.5
        assert trail_dec.new_sl == 2709.5
        assert trail_dec.locked_points == 9.5

    # 7. Swing Structure Trailing Stop bám sát đáy nến M5
    def test_swing_structure_trailing_m5(self, sample_buy_signal, sample_m5_df):
        engine = SmartExitEngine(SmartExitConfig(enable_swing_trailing=True))
        # sample_m5_df có các nến cuối cùng với low tăng dần
        current_price = 2716.0
        decisions = engine.evaluate_signal(
            signal=sample_buy_signal,
            current_price=current_price,
            df_m5=sample_m5_df,
            market_regime="TRENDING_BULLISH",
        )
        trail_dec = next((d for d in decisions if d.action_type == ExitActionType.TRAILING_UPDATE), None)
        assert trail_dec is not None
        assert trail_dec.trailing_mode in ("SWING_STRUCTURE", "ATR_DYNAMIC")
        assert trail_dec.new_sl > sample_buy_signal.entry_price

    # 8. Multi-Tier Scaled Exits (Tier 1 chốt 50% & Tier 2 chốt 30%)
    def test_multi_tier_scaled_exits_progression(self, sample_buy_signal):
        engine = SmartExitEngine(
            SmartExitConfig(
                enable_scaled_exits=True,
                tier1_r_threshold=1.0,
                tier2_r_threshold=2.0,
            )
        )
        # Bước 1: Giá đạt 2710.5 (+10.5 giá với SL 10 giá -> +1.05R)
        d1 = engine.evaluate_signal(sample_buy_signal, current_price=2710.5)
        t1_dec = next((d for d in d1 if d.action_type == ExitActionType.SCALED_EXIT_TIER1), None)
        assert t1_dec is not None
        assert t1_dec.close_ratio == 0.5
        assert t1_dec.tier_name == "TIER_1 (50%)"
        assert sample_buy_signal.tier_reached == 1
        assert t1_dec.new_sl == 2700.5
        assert sample_buy_signal.stop_loss >= 2700.5  # Đã dời SL về BE hoặc Trailing Stop cao hơn

        # Bước 2: Giá tiếp tục bứt phá lên 2721.0 (+2.1R)
        d2 = engine.evaluate_signal(sample_buy_signal, current_price=2721.0)
        t2_dec = next((d for d in d2 if d.action_type == ExitActionType.SCALED_EXIT_TIER2), None)
        assert t2_dec is not None
        assert t2_dec.close_ratio == 0.3
        assert t2_dec.tier_name == "TIER_2 (30%)"
        assert sample_buy_signal.tier_reached == 2

    # 9. Cảnh báo suy yếu động lượng (Momentum Exhaustion Rejection Wick)
    def test_momentum_exhaustion_detection(self, sample_buy_signal):
        engine = SmartExitEngine()
        # Nến M5 có râu trên dài 70% thân nến
        df_exhaust = pd.DataFrame([
            {"time": "2026-10-26 10:00:00", "open": 2702.0, "high": 2703.0, "low": 2701.0, "close": 2702.5},
            {"time": "2026-10-26 10:05:00", "open": 2703.5, "high": 2706.0, "low": 2703.0, "close": 2703.8},
        ])
        decision = engine.evaluate_candle_exhaustion(
            signal=sample_buy_signal,
            df_m5=df_exhaust,
            current_price=2703.8,  # Lãi +3.8 giá
        )
        assert decision is not None
        assert decision.action_type == ExitActionType.MOMENTUM_EXHAUSTION
        assert "râu từ chối bán" in decision.reason

    # 10. Cảnh báo lệnh ứ đọng (Time Stagnation Decay)
    def test_time_stagnation_detection(self, sample_buy_signal):
        engine = SmartExitEngine()
        df = pd.DataFrame([
            {"open": 2702.0, "high": 2702.5, "low": 2701.8, "close": 2702.2},
            {"open": 2702.2, "high": 2702.4, "low": 2702.0, "close": 2702.1},
        ])
        sample_buy_signal.created_at = datetime.now(timezone.utc) - timedelta(minutes=75)
        decision = engine.evaluate_candle_exhaustion(
            signal=sample_buy_signal,
            df_m5=df,
            current_price=2702.2,  # Lãi +2.2 giá
        )
        assert decision is not None
        assert decision.action_type == ExitActionType.TIME_STAGNATION
        assert "Lệnh ngâm 75 phút" in decision.reason

    # 11. Định dạng tin nhắn Scaled Exit Telegram Formatter
    def test_format_scaled_exit_alert(self, sample_buy_signal):
        msg = format_scaled_exit_alert(
            signal=sample_buy_signal,
            current_price=2711.0,
            tier_name="TIER_1 (50%)",
            close_ratio=0.5,
            pnl_points=11.0,
            pnl_r=1.1,
            new_sl=2700.5,
        )
        assert "KHUYẾN NGHỊ CHỐT LỜI TỪNG PHẦN (TIER_1 (50%))" in msg
        assert "+11.00 giá" in msg
        assert "+110.0 pips" in msg
        assert "+1.1R" in msg
        assert "50% khối lượng" in msg
        assert "2700.50" in msg
