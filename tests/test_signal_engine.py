# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Signal Engine.
"""

from datetime import datetime, timezone
import pandas as pd
import numpy as np
import pytest

from app.market.indicators import add_all_indicators
from app.market.market_structure import TrendDirection
from app.market.volatility import VolatilityLevel, VolatilityResult
from app.strategy.risk_filter import FilterConfig
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection, SignalStatus


def _generate_synthetic_candles(
    n_bars: int = 50,
    start_price: float = 2000.0,
    trend: str = "FLAT",
) -> pd.DataFrame:
    """Tạo chuỗi nến giả lập OHLCV cơ bản."""
    prices = [start_price]
    step = 0.5 if trend == "UP" else -0.5 if trend == "DOWN" else 0.0

    for i in range(1, n_bars):
        p = prices[-1] + step
        prices.append(p)

    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n_bars, freq="h"),
        "open": [p - 0.5 for p in prices],
        "high": [p + 2.0 for p in prices],
        "low": [p - 2.0 for p in prices],
        "close": [float(p) for p in prices],
        "tick_volume": [100.0] * n_bars,
    })
    return df


def _make_zigzag_uptrend_df() -> pd.DataFrame:
    """Tạo DataFrame uptrend có cấu trúc đỉnh đáy HH, HL rõ rệt (> 50 nến)."""
    prices: list[float] = []
    prices += [100.0, 98.0, 96.0, 95.0, 96.0, 98.0, 100.0]
    prices += [103.0, 106.0, 110.0, 107.0, 104.0]
    prices += [102.0, 103.0, 105.0]
    prices += [110.0, 115.0, 120.0, 117.0, 114.0]
    prices += [112.0, 113.0, 115.0]
    prices += [120.0, 125.0, 130.0, 127.0, 124.0]
    prices += [122.0, 120.0, 122.0, 124.0, 126.0]
    prices += [128.0, 130.0, 135.0, 132.0, 129.0]
    prices += [131.0, 134.0, 140.0, 137.0, 133.0]
    prices += [135.0, 138.0, 145.0, 142.0, 139.0]
    prices += [141.0, 143.0, 145.0, 147.0, 149.0, 150.0]

    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=len(prices), freq="h"),
        "open": [p - 0.5 for p in prices],
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": [float(p) for p in prices],
        "tick_volume": [100.0] * len(prices),
    })
    return df


class TestSignalEngine:
    """Test suite cho Signal Engine."""

    def test_engine_initialization(self):
        """Khởi tạo SignalEngine thành công với cấu hình mặc định."""
        engine = SignalEngine(strategy_version="v1.0", symbol="XAUUSD")
        assert engine.strategy_version == "v1.0"
        assert engine.symbol == "XAUUSD"
        assert engine.default_timeframe == "H1"
        assert len(engine.get_active_signals()) == 0

    def test_generate_signal_insufficient_data(self):
        """Dữ liệu quá ngắn (< 20 bars) phải trả về WAIT signal."""
        engine = SignalEngine()
        df_short = _generate_synthetic_candles(n_bars=10)
        signal = engine.generate_signal(df=df_short)

        assert signal.direction == SignalDirection.WAIT
        assert signal.is_wait is True
        assert any("Dữ liệu nến không đủ" in r for r in signal.reasons)

    def test_generate_signal_no_setup_wait(self):
        """Khi thị trường không có setup đạt chuẩn -> trả về WAIT."""
        engine = SignalEngine()
        df_flat = _generate_synthetic_candles(n_bars=50, trend="FLAT")
        df_flat = add_all_indicators(df_flat)
        df_flat["rsi_14"] = 50.0  # RSI trung tính, không kích hoạt RSI extreme
        signal = engine.generate_signal(df=df_flat)

        assert signal.direction == SignalDirection.WAIT
        assert signal.is_wait is True

    def test_generate_buy_signal_on_confluence(self):
        """Setup BUY thỏa mãn đầy đủ điều kiện sinh ra BUY TradingSignal."""
        engine = SignalEngine()

        df = _make_zigzag_uptrend_df()
        df = add_all_indicators(df)

        last_idx = df.index[-1]
        prev_idx = df.index[-2]
        df.loc[prev_idx, "close"] = 145.1
        df.loc[last_idx, "close"] = 148.0
        df.loc[last_idx, "ema_20"] = 145.0
        df.loc[last_idx, "ema_50"] = 135.0
        df.loc[last_idx, "rsi_14"] = 50.0
        df.loc[last_idx, "atr_14"] = 3.0

        h4_df = df.copy()

        signal = engine.generate_signal(df=df, h4_df=h4_df)

        assert signal.direction == SignalDirection.BUY
        assert signal.is_buy is True
        assert signal.status == SignalStatus.ACTIVE
        assert signal.entry_price == 148.0
        assert signal.entry_zone_low < signal.entry_price
        assert signal.entry_zone_high >= signal.entry_price
        assert signal.stop_loss < signal.entry_price
        assert signal.take_profit_1 > signal.entry_price
        assert signal.risk_reward_ratio >= 1.5
        assert signal.score > 0
        assert signal.confidence in ("LOW", "MEDIUM", "HIGH")
        assert len(signal.reasons) > 0

        # Kiểm tra đã được lưu vào active signals
        assert len(engine.get_active_signals()) == 1

    def test_duplicate_signal_returns_wait(self):
        """Khi đã có BUY active, lần phân tích tiếp theo trả về WAIT do trùng lặp."""
        engine = SignalEngine()
        df = _make_zigzag_uptrend_df()
        df = add_all_indicators(df)

        last_idx = df.index[-1]
        prev_idx = df.index[-2]
        df.loc[prev_idx, "close"] = 145.1
        df.loc[last_idx, "close"] = 148.0
        df.loc[last_idx, "ema_20"] = 145.0
        df.loc[last_idx, "ema_50"] = 135.0
        df.loc[last_idx, "rsi_14"] = 50.0
        df.loc[last_idx, "atr_14"] = 3.0

        h4_df = df.copy()

        # Lần 1: Phát tín hiệu BUY
        sig1 = engine.generate_signal(df=df, h4_df=h4_df)
        assert sig1.direction == SignalDirection.BUY

        # Lần 2: Cùng dữ liệu -> Phải trả về WAIT do trùng lặp
        sig2 = engine.generate_signal(df=df, h4_df=h4_df)
        assert sig2.direction == SignalDirection.WAIT
        assert any("trùng lặp" in r.lower() or "cooldown" in r.lower() or "đang hoạt động" in r.lower()
                   for r in sig2.reasons)

    def test_risk_filter_rejection_returns_wait_with_reason(self):
        """Khi setup vi phạm risk filter (R:R quá cao đòi hỏi, hoặc min_score) -> WAIT."""
        strict_config = FilterConfig(min_score=99.0)
        engine = SignalEngine(filter_config=strict_config)

        df = _make_zigzag_uptrend_df()
        df = add_all_indicators(df)

        last_idx = df.index[-1]
        prev_idx = df.index[-2]
        df.loc[prev_idx, "close"] = 145.1
        df.loc[last_idx, "close"] = 148.0
        df.loc[last_idx, "ema_20"] = 145.0
        df.loc[last_idx, "ema_50"] = 135.0
        df.loc[last_idx, "rsi_14"] = 50.0
        df.loc[last_idx, "atr_14"] = 3.0

        h4_df = df.copy()

        signal = engine.generate_signal(df=df, h4_df=h4_df)
        assert signal.direction == SignalDirection.WAIT
        assert any("Score quá thấp" in r or "bộ lọc" in r for r in signal.reasons)

    def test_update_market_price(self):
        """Kiểm tra cập nhật giá thị trường qua SignalEngine."""
        engine = SignalEngine()
        df = _make_zigzag_uptrend_df()
        df = add_all_indicators(df)

        last_idx = df.index[-1]
        prev_idx = df.index[-2]
        df.loc[prev_idx, "close"] = 145.1
        df.loc[last_idx, "close"] = 148.0
        df.loc[last_idx, "ema_20"] = 145.0
        df.loc[last_idx, "ema_50"] = 135.0
        df.loc[last_idx, "rsi_14"] = 50.0
        df.loc[last_idx, "atr_14"] = 3.0

        h4_df = df.copy()

        sig = engine.generate_signal(df=df, h4_df=h4_df)
        assert sig.direction == SignalDirection.BUY

        # Cập nhật giá chạm entry
        changed = engine.update_market_price(current_price=sig.entry_price)
        assert len(changed) == 1
        assert sig.status == SignalStatus.ENTRY_REACHED
