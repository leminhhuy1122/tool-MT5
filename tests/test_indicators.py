# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho Technical Indicators.

Test thuần logic — không cần MT5.
"""

import numpy as np
import pandas as pd
import pytest

from app.market.indicators import (
    calc_ema,
    add_ema,
    calc_rsi,
    add_rsi,
    calc_true_range,
    calc_atr,
    add_atr,
    add_all_indicators,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _make_ohlcv(num_bars: int = 50, base: float = 2650.0) -> pd.DataFrame:
    """Tạo DataFrame OHLCV giả."""
    np.random.seed(42)
    closes = base + np.cumsum(np.random.randn(num_bars) * 2)
    opens = closes + np.random.randn(num_bars) * 0.5
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(num_bars))
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(num_bars))
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=num_bars, freq="h"),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": np.random.randint(100, 1000, num_bars),
        "spread": np.random.randint(20, 40, num_bars),
    })


# ──────────────────────────────────────────────
# TestEMA
# ──────────────────────────────────────────────
class TestEMA:
    """Test EMA calculation."""

    def test_ema_returns_series(self) -> None:
        df = _make_ohlcv()
        result = calc_ema(df["close"], 20)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_ema_name(self) -> None:
        df = _make_ohlcv()
        result = calc_ema(df["close"], 20)
        assert result.name == "ema_20"

    def test_ema_custom_name(self) -> None:
        df = _make_ohlcv()
        result = calc_ema(df["close"], 20, column_name="my_ema")
        assert result.name == "my_ema"

    def test_ema_not_enough_data(self) -> None:
        series = pd.Series([1.0, 2.0, 3.0])
        result = calc_ema(series, 50)
        assert result.isna().all()

    def test_ema_values_not_nan_after_period(self) -> None:
        df = _make_ohlcv(100)
        result = calc_ema(df["close"], 20)
        # Sau period đầu tiên, không nên NaN
        assert not result.iloc[20:].isna().any()

    def test_add_ema_default_periods(self) -> None:
        df = _make_ohlcv(250)
        result = add_ema(df)
        assert "ema_20" in result.columns
        assert "ema_50" in result.columns
        assert "ema_200" in result.columns

    def test_add_ema_custom_periods(self) -> None:
        df = _make_ohlcv(100)
        result = add_ema(df, periods=[10, 30])
        assert "ema_10" in result.columns
        assert "ema_30" in result.columns
        assert "ema_20" not in result.columns

    def test_add_ema_does_not_mutate_input(self) -> None:
        df = _make_ohlcv()
        original_cols = list(df.columns)
        add_ema(df)
        assert list(df.columns) == original_cols


# ──────────────────────────────────────────────
# TestRSI
# ──────────────────────────────────────────────
class TestRSI:
    """Test RSI calculation."""

    def test_rsi_returns_series(self) -> None:
        df = _make_ohlcv(50)
        result = calc_rsi(df["close"], 14)
        assert isinstance(result, pd.Series)

    def test_rsi_range_0_100(self) -> None:
        df = _make_ohlcv(100)
        result = calc_rsi(df["close"], 14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_not_enough_data(self) -> None:
        series = pd.Series([1.0, 2.0, 3.0])
        result = calc_rsi(series, 14)
        assert result.isna().all()

    def test_rsi_all_gains(self) -> None:
        series = pd.Series(range(20), dtype=float)
        result = calc_rsi(series, 14)
        # Khi tất cả đều tăng, RSI → 100
        assert result.iloc[-1] == pytest.approx(100.0)

    def test_add_rsi(self) -> None:
        df = _make_ohlcv(50)
        result = add_rsi(df)
        assert "rsi_14" in result.columns


# ──────────────────────────────────────────────
# TestATR
# ──────────────────────────────────────────────
class TestATR:
    """Test ATR calculation."""

    def test_true_range_positive(self) -> None:
        df = _make_ohlcv(20)
        tr = calc_true_range(df)
        valid = tr.dropna()
        assert (valid >= 0).all()

    def test_true_range_first_bar_is_high_minus_low(self) -> None:
        df = _make_ohlcv(5)
        tr = calc_true_range(df)
        # Nến đầu tiên: prev_close = NaN, nên TR = high - low
        expected = df["high"].iloc[0] - df["low"].iloc[0]
        assert tr.iloc[0] == pytest.approx(expected, abs=0.01)

    def test_atr_returns_series(self) -> None:
        df = _make_ohlcv(50)
        result = calc_atr(df, 14)
        assert isinstance(result, pd.Series)

    def test_atr_positive(self) -> None:
        df = _make_ohlcv(50)
        result = calc_atr(df, 14)
        valid = result.dropna()
        assert (valid > 0).all()

    def test_atr_not_enough_data(self) -> None:
        df = _make_ohlcv(5)
        result = calc_atr(df, 14)
        assert result.isna().all()

    def test_add_atr(self) -> None:
        df = _make_ohlcv(50)
        result = add_atr(df)
        assert "atr_14" in result.columns


# ──────────────────────────────────────────────
# TestAllIndicators
# ──────────────────────────────────────────────
class TestAllIndicators:
    """Test add_all_indicators."""

    def test_adds_all_columns(self) -> None:
        df = _make_ohlcv(250)
        result = add_all_indicators(df)
        assert "ema_20" in result.columns
        assert "ema_50" in result.columns
        assert "ema_200" in result.columns
        assert "rsi_14" in result.columns
        assert "atr_14" in result.columns

    def test_preserves_original_columns(self) -> None:
        df = _make_ohlcv(50)
        result = add_all_indicators(df)
        for col in ["open", "high", "low", "close"]:
            assert col in result.columns
