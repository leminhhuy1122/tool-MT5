# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho Market Structure.

Test thuần logic — không cần MT5.
"""

import numpy as np
import pandas as pd
import pytest

from app.market.market_structure import (
    SwingType,
    SwingPoint,
    TrendDirection,
    StructureBreak,
    detect_swings,
    detect_trend,
    detect_structure_breaks,
    detect_sr_zones,
    analyze_market_structure,
    MarketStructureResult,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _make_uptrend_df() -> pd.DataFrame:
    """Tạo DataFrame mô phỏng uptrend rõ ràng với HH, HL."""
    # Zigzag lên: mỗi đỉnh cao hơn, mỗi đáy cao hơn
    prices = [
        # low, high pattern — uptrend
        100, 102, 105, 103, 101,  # swing high=105 tại index 2
        102, 104, 108, 106, 103,  # swing high=108 tại index 7 (HH)
        104, 106, 112, 110, 106,  # swing high=112 tại index 12 (HH)
        107, 109, 115, 113, 108,  # swing high=115 tại index 17 (HH)
    ]
    n = len(prices)
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": [p - 0.5 for p in prices],
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
    })


def _make_downtrend_df() -> pd.DataFrame:
    """Tạo DataFrame mô phỏng downtrend rõ ràng."""
    prices = [
        115, 113, 110, 112, 114,  # swing low=110 tại index 2
        112, 110, 106, 108, 111,  # swing low=106 tại index 7 (LL)
        109, 107, 103, 105, 108,  # swing low=103 tại index 12 (LL)
        106, 104, 100, 102, 105,  # swing low=100 tại index 17 (LL)
    ]
    n = len(prices)
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": [p + 0.5 for p in prices],
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
    })


def _make_simple_swing_df() -> pd.DataFrame:
    """Tạo DataFrame đơn giản với 1 swing high và 1 swing low rõ ràng."""
    # Pattern: low, rising, PEAK, falling, low, rising...
    highs = [10, 12, 15, 20, 15, 12, 10, 8, 5, 8, 10, 12, 15]
    lows =  [8,  10, 13, 18, 13, 10, 8,  6, 3, 6, 8,  10, 13]
    n = len(highs)
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": [(h + l) / 2 for h, l in zip(highs, lows)],
        "high": highs,
        "low": lows,
        "close": [(h + l) / 2 + 0.5 for h, l in zip(highs, lows)],
    })


# ──────────────────────────────────────────────
# TestSwingDetection
# ──────────────────────────────────────────────
class TestSwingDetection:
    """Test swing point detection."""

    def test_detects_swing_high(self) -> None:
        df = _make_simple_swing_df()
        swings = detect_swings(df, left_bars=2, right_bars=2)
        highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
        assert len(highs) >= 1
        # Swing high nên ở khoảng index 3 (giá 20)
        assert any(s.price == 20.0 for s in highs)

    def test_detects_swing_low(self) -> None:
        df = _make_simple_swing_df()
        swings = detect_swings(df, left_bars=2, right_bars=2)
        lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]
        assert len(lows) >= 1
        # Swing low nên ở khoảng index 8 (giá 3)
        assert any(s.price == 3.0 for s in lows)

    def test_no_look_ahead(self) -> None:
        """Swing points cuối cùng phải cách cuối ít nhất right_bars."""
        df = _make_simple_swing_df()
        right_bars = 3
        swings = detect_swings(df, left_bars=2, right_bars=right_bars)
        for s in swings:
            assert s.index <= len(df) - right_bars - 1

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame({"high": [], "low": [], "close": []})
        swings = detect_swings(df)
        assert swings == []

    def test_insufficient_data(self) -> None:
        df = pd.DataFrame({
            "high": [10, 12, 10],
            "low": [8, 10, 8],
        })
        swings = detect_swings(df, left_bars=3, right_bars=3)
        assert swings == []

    def test_swing_has_time(self) -> None:
        df = _make_simple_swing_df()
        swings = detect_swings(df, left_bars=2, right_bars=2)
        for s in swings:
            assert s.time is not None


# ──────────────────────────────────────────────
# TestTrendDetection
# ──────────────────────────────────────────────
class TestTrendDetection:
    """Test trend detection from swing points."""

    def test_bullish_trend(self) -> None:
        swings = [
            SwingPoint(0, 100, SwingType.SWING_LOW),
            SwingPoint(5, 110, SwingType.SWING_HIGH),
            SwingPoint(10, 105, SwingType.SWING_LOW),   # HL
            SwingPoint(15, 115, SwingType.SWING_HIGH),  # HH
        ]
        assert detect_trend(swings) == TrendDirection.BULLISH

    def test_bearish_trend(self) -> None:
        swings = [
            SwingPoint(0, 115, SwingType.SWING_HIGH),
            SwingPoint(5, 100, SwingType.SWING_LOW),
            SwingPoint(10, 110, SwingType.SWING_HIGH),  # LH
            SwingPoint(15, 95, SwingType.SWING_LOW),    # LL
        ]
        assert detect_trend(swings) == TrendDirection.BEARISH

    def test_neutral_when_mixed(self) -> None:
        swings = [
            SwingPoint(0, 100, SwingType.SWING_LOW),
            SwingPoint(5, 110, SwingType.SWING_HIGH),
            SwingPoint(10, 105, SwingType.SWING_LOW),   # HL
            SwingPoint(15, 108, SwingType.SWING_HIGH),  # LH (mixed)
        ]
        assert detect_trend(swings) == TrendDirection.NEUTRAL

    def test_neutral_when_insufficient(self) -> None:
        swings = [SwingPoint(0, 100, SwingType.SWING_LOW)]
        assert detect_trend(swings) == TrendDirection.NEUTRAL


# ──────────────────────────────────────────────
# TestSRZones
# ──────────────────────────────────────────────
class TestSRZones:
    """Test S/R zone detection."""

    def test_creates_zones(self) -> None:
        swings = [
            SwingPoint(0, 100.0, SwingType.SWING_LOW),
            SwingPoint(5, 110.0, SwingType.SWING_HIGH),
            SwingPoint(10, 100.1, SwingType.SWING_LOW),  # gần 100
        ]
        zones = detect_sr_zones(swings, tolerance_pct=0.2)
        assert len(zones) >= 1

    def test_clusters_nearby_prices(self) -> None:
        swings = [
            SwingPoint(0, 100.00, SwingType.SWING_LOW),
            SwingPoint(10, 100.05, SwingType.SWING_LOW),  # rất gần 100
            SwingPoint(20, 100.08, SwingType.SWING_LOW),  # rất gần 100
        ]
        zones = detect_sr_zones(swings, tolerance_pct=0.1)
        support_zones = [z for z in zones if z.zone_type == "SUPPORT"]
        # Nên gom lại thành 1 zone với strength >= 2
        assert any(z.strength >= 2 for z in support_zones)

    def test_empty_swings(self) -> None:
        zones = detect_sr_zones([])
        assert zones == []

    def test_sorted_by_price(self) -> None:
        swings = [
            SwingPoint(0, 200.0, SwingType.SWING_HIGH),
            SwingPoint(5, 100.0, SwingType.SWING_LOW),
            SwingPoint(10, 150.0, SwingType.SWING_HIGH),
        ]
        zones = detect_sr_zones(swings)
        prices = [z.price for z in zones]
        assert prices == sorted(prices)


# ──────────────────────────────────────────────
# TestAnalyzeMarketStructure
# ──────────────────────────────────────────────
class TestAnalyzeMarketStructure:
    """Test full market structure analysis."""

    def test_returns_result(self) -> None:
        df = _make_uptrend_df()
        result = analyze_market_structure(df, left_bars=2, right_bars=2)
        assert isinstance(result, MarketStructureResult)
        assert len(result.swings) > 0

    def test_result_has_trend(self) -> None:
        df = _make_uptrend_df()
        result = analyze_market_structure(df, left_bars=2, right_bars=2)
        assert isinstance(result.trend, TrendDirection)

    def test_result_has_sr_zones(self) -> None:
        df = _make_simple_swing_df()
        result = analyze_market_structure(df, left_bars=2, right_bars=2)
        assert isinstance(result.sr_zones, list)
