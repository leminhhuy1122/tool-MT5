# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho Volatility Analysis.

Test thuần logic — không cần MT5.
"""

import numpy as np
import pandas as pd
import pytest

from app.market.volatility import (
    VolatilityLevel,
    classify_volatility,
    analyze_volatility,
    calc_candle_range,
    calc_body_ratio,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _make_ohlcv(num_bars: int = 50, volatility: float = 2.0) -> pd.DataFrame:
    """Tạo DataFrame OHLCV giả."""
    np.random.seed(42)
    closes = 2650.0 + np.cumsum(np.random.randn(num_bars) * volatility)
    opens = closes + np.random.randn(num_bars) * 0.5
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(num_bars) * volatility)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(num_bars) * volatility)
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
# TestClassifyVolatility
# ──────────────────────────────────────────────
class TestClassifyVolatility:
    """Test volatility classification."""

    def test_low(self) -> None:
        assert classify_volatility(0.3) == VolatilityLevel.LOW

    def test_normal(self) -> None:
        assert classify_volatility(1.0) == VolatilityLevel.NORMAL

    def test_high(self) -> None:
        assert classify_volatility(2.0) == VolatilityLevel.HIGH

    def test_extreme(self) -> None:
        assert classify_volatility(3.0) == VolatilityLevel.EXTREME

    def test_boundary_low_normal(self) -> None:
        assert classify_volatility(0.5) == VolatilityLevel.NORMAL


# ──────────────────────────────────────────────
# TestAnalyzeVolatility
# ──────────────────────────────────────────────
class TestAnalyzeVolatility:
    """Test analyze_volatility function."""

    def test_returns_result(self) -> None:
        df = _make_ohlcv(50)
        result = analyze_volatility(df)
        assert result is not None
        assert result.current_atr > 0

    def test_returns_none_insufficient_data(self) -> None:
        df = _make_ohlcv(5)
        result = analyze_volatility(df, atr_period=14)
        assert result is None

    def test_atr_ratio_positive(self) -> None:
        df = _make_ohlcv(100)
        result = analyze_volatility(df)
        assert result.atr_ratio > 0

    def test_spread_analysis_with_spread_col(self) -> None:
        df = _make_ohlcv(50)
        result = analyze_volatility(df)
        assert result.current_spread > 0
        assert result.avg_spread > 0

    def test_spread_high_flag(self) -> None:
        df = _make_ohlcv(50)
        # Tạo spread bất thường ở nến cuối
        df.loc[df.index[-1], "spread"] = 500
        result = analyze_volatility(df, spread_threshold=2.0)
        assert result.is_spread_high is True

    def test_level_is_volatility_level(self) -> None:
        df = _make_ohlcv(50)
        result = analyze_volatility(df)
        assert isinstance(result.level, VolatilityLevel)


# ──────────────────────────────────────────────
# TestCandleRange
# ──────────────────────────────────────────────
class TestCandleRange:
    """Test candle range calculation."""

    def test_positive_range(self) -> None:
        df = _make_ohlcv(10)
        cr = calc_candle_range(df)
        assert (cr >= 0).all()

    def test_name(self) -> None:
        df = _make_ohlcv(10)
        cr = calc_candle_range(df)
        assert cr.name == "candle_range"


# ──────────────────────────────────────────────
# TestBodyRatio
# ──────────────────────────────────────────────
class TestBodyRatio:
    """Test body ratio calculation."""

    def test_range_0_to_1(self) -> None:
        df = _make_ohlcv(20)
        br = calc_body_ratio(df)
        assert (br >= 0).all()
        assert (br <= 1).all()

    def test_full_body_candle(self) -> None:
        """Nến không có bóng → body_ratio = 1."""
        df = pd.DataFrame({
            "open": [100.0],
            "high": [110.0],
            "low": [100.0],
            "close": [110.0],
        })
        br = calc_body_ratio(df)
        assert br.iloc[0] == pytest.approx(1.0)

    def test_doji_candle(self) -> None:
        """Nến doji (open == close) → body_ratio = 0."""
        df = pd.DataFrame({
            "open": [105.0],
            "high": [110.0],
            "low": [100.0],
            "close": [105.0],
        })
        br = calc_body_ratio(df)
        assert br.iloc[0] == pytest.approx(0.0)
