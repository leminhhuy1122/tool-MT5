# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho Timeframe Manager.

Không cần MT5 — test logic thuần.
"""

import pytest

from app.market.timeframe_manager import (
    Timeframe,
    DEFAULT_TIMEFRAMES,
    DEFAULT_BAR_COUNTS,
    get_timeframe_by_label,
)


class TestTimeframe:
    """Test Timeframe enum."""

    def test_m5_attributes(self) -> None:
        assert Timeframe.M5.label == "M5"
        assert Timeframe.M5.minutes == 5

    def test_h1_attributes(self) -> None:
        assert Timeframe.H1.label == "H1"
        assert Timeframe.H1.minutes == 60

    def test_h4_attributes(self) -> None:
        assert Timeframe.H4.label == "H4"
        assert Timeframe.H4.minutes == 240

    def test_d1_attributes(self) -> None:
        assert Timeframe.D1.label == "D1"
        assert Timeframe.D1.minutes == 1440

    def test_str(self) -> None:
        assert str(Timeframe.H1) == "H1"

    def test_mt5_const_is_int(self) -> None:
        for tf in Timeframe:
            assert isinstance(tf.mt5_const, int)


class TestDefaultTimeframes:
    """Test default configuration."""

    def test_default_timeframes_count(self) -> None:
        assert len(DEFAULT_TIMEFRAMES) == 4

    def test_default_timeframes_order(self) -> None:
        labels = [tf.label for tf in DEFAULT_TIMEFRAMES]
        assert labels == ["H4", "H1", "M15", "M5"]

    def test_all_timeframes_have_bar_count(self) -> None:
        for tf in Timeframe:
            assert tf in DEFAULT_BAR_COUNTS


class TestGetTimeframeByLabel:
    """Test get_timeframe_by_label function."""

    def test_found(self) -> None:
        assert get_timeframe_by_label("H1") == Timeframe.H1

    def test_case_insensitive(self) -> None:
        assert get_timeframe_by_label("h4") == Timeframe.H4
        assert get_timeframe_by_label("m15") == Timeframe.M15

    def test_not_found(self) -> None:
        assert get_timeframe_by_label("W1") is None

    def test_empty_string(self) -> None:
        assert get_timeframe_by_label("") is None
