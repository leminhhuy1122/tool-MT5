# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho Market Data Manager.

Mock tests — không cần MT5 terminal thật.
Kiểm tra:
- Lấy dữ liệu candles.
- Loại bỏ nến chưa đóng.
- Data validation.
- Cache.
- Latest price.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from collections import namedtuple

import numpy as np
import pandas as pd
import pytest

from app.market.timeframe_manager import Timeframe
from app.market.data_manager import MarketDataManager, DataQuality


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _make_rates(
    num_bars: int = 10,
    timeframe_minutes: int = 60,
    start_time: int = 1700000000,
    base_price: float = 2650.0,
) -> np.ndarray:
    """Tạo mock rates data giống MT5 trả về."""
    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "i8"),
        ("spread", "i4"),
        ("real_volume", "i8"),
    ]
    data = np.zeros(num_bars, dtype=dtype)
    for i in range(num_bars):
        t = start_time + i * timeframe_minutes * 60
        o = base_price + i * 0.5
        h = o + 2.0
        l = o - 1.0
        c = o + 1.0
        data[i] = (t, o, h, l, c, 1000 + i * 10, 25, 0)
    return data


def _make_invalid_ohlc_rates() -> np.ndarray:
    """Tạo rates với OHLC không hợp lệ (high < low)."""
    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "i8"),
        ("spread", "i4"),
        ("real_volume", "i8"),
    ]
    data = np.zeros(3, dtype=dtype)
    # Nến bình thường
    data[0] = (1700000000, 2650, 2655, 2648, 2652, 100, 25, 0)
    # Nến lỗi: high < low
    data[1] = (1700003600, 2652, 2640, 2660, 2645, 100, 25, 0)
    # Nến bình thường
    data[2] = (1700007200, 2645, 2650, 2643, 2648, 100, 25, 0)
    return data


# ──────────────────────────────────────────────
# TestDataQuality
# ──────────────────────────────────────────────
class TestDataQuality:
    """Test DataQuality dataclass."""

    def test_valid_when_clean(self) -> None:
        q = DataQuality(total_bars=100)
        assert q.is_valid is True
        assert q.issues == []

    def test_invalid_when_empty(self) -> None:
        q = DataQuality(total_bars=0)
        assert q.is_valid is False
        assert "Không có dữ liệu" in q.issues

    def test_invalid_when_duplicates(self) -> None:
        q = DataQuality(total_bars=100, duplicate_timestamps=3)
        assert q.is_valid is False

    def test_invalid_when_future_bars(self) -> None:
        q = DataQuality(total_bars=100, future_bars=1)
        assert q.is_valid is False

    def test_valid_with_missing_bars(self) -> None:
        # Missing bars là warning, không fail validation
        q = DataQuality(total_bars=100, missing_bars=5)
        assert q.is_valid is True
        assert len(q.issues) == 1


# ──────────────────────────────────────────────
# TestMarketDataManager
# ──────────────────────────────────────────────
class TestMarketDataManager:
    """Test MarketDataManager class."""

    def test_init(self) -> None:
        mgr = MarketDataManager(symbol="XAUUSD")
        assert mgr.symbol == "XAUUSD"

    @patch("app.market.data_manager.mt5")
    def test_get_candles_success(self, mock_mt5: MagicMock) -> None:
        rates = _make_rates(num_bars=11, timeframe_minutes=60)
        mock_mt5.copy_rates_from_pos.return_value = rates

        mgr = MarketDataManager("XAUUSD")
        df = mgr.get_candles(Timeframe.H1, num_bars=10)

        assert df is not None
        assert len(df) == 10  # 11 - 1 (loại nến chưa đóng)
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "tick_volume" in df.columns

    @patch("app.market.data_manager.mt5")
    def test_get_candles_removes_unclosed(self, mock_mt5: MagicMock) -> None:
        rates = _make_rates(num_bars=6, timeframe_minutes=60)
        mock_mt5.copy_rates_from_pos.return_value = rates

        mgr = MarketDataManager("XAUUSD")
        df = mgr.get_candles(Timeframe.H1, num_bars=5, include_unclosed=False)

        assert df is not None
        assert len(df) == 5  # Loại bỏ nến cuối

    @patch("app.market.data_manager.mt5")
    def test_get_candles_include_unclosed(self, mock_mt5: MagicMock) -> None:
        rates = _make_rates(num_bars=5, timeframe_minutes=60)
        mock_mt5.copy_rates_from_pos.return_value = rates

        mgr = MarketDataManager("XAUUSD")
        df = mgr.get_candles(Timeframe.H1, num_bars=5, include_unclosed=True)

        assert df is not None
        assert len(df) == 5

    @patch("app.market.data_manager.mt5")
    def test_get_candles_returns_none_on_error(self, mock_mt5: MagicMock) -> None:
        mock_mt5.copy_rates_from_pos.return_value = None
        mock_mt5.last_error.return_value = (-1, "No data")

        mgr = MarketDataManager("XAUUSD")
        df = mgr.get_candles(Timeframe.H1)

        assert df is None

    @patch("app.market.data_manager.mt5")
    def test_get_candles_time_is_utc(self, mock_mt5: MagicMock) -> None:
        rates = _make_rates(num_bars=3, timeframe_minutes=60)
        mock_mt5.copy_rates_from_pos.return_value = rates

        mgr = MarketDataManager("XAUUSD")
        df = mgr.get_candles(Timeframe.H1, num_bars=2)

        assert df is not None
        assert df["time"].dt.tz is not None  # Có timezone

    @patch("app.market.data_manager.mt5")
    def test_cache_stores_data(self, mock_mt5: MagicMock) -> None:
        rates = _make_rates(num_bars=6)
        mock_mt5.copy_rates_from_pos.return_value = rates

        mgr = MarketDataManager("XAUUSD")
        mgr.get_candles(Timeframe.H1, num_bars=5)

        cached = mgr.get_cached(Timeframe.H1)
        assert cached is not None
        assert len(cached) == 5

    def test_clear_cache(self) -> None:
        mgr = MarketDataManager("XAUUSD")
        mgr._cache[Timeframe.H1] = pd.DataFrame({"a": [1]})

        mgr.clear_cache()

        assert mgr.get_cached(Timeframe.H1) is None

    @patch("app.market.data_manager.mt5")
    def test_get_latest_price_success(self, mock_mt5: MagicMock) -> None:
        TickInfo = namedtuple("TickInfo", ["bid", "ask", "last", "volume", "time"])
        mock_mt5.symbol_info_tick.return_value = TickInfo(
            bid=2650.50, ask=2650.80, last=2650.65, volume=100,
            time=1700000000,
        )

        mgr = MarketDataManager("XAUUSD")
        price = mgr.get_latest_price()

        assert price is not None
        assert price["bid"] == 2650.50
        assert price["ask"] == 2650.80
        assert price["spread"] == pytest.approx(0.30)

    @patch("app.market.data_manager.mt5")
    def test_get_latest_price_none_on_error(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info_tick.return_value = None

        mgr = MarketDataManager("XAUUSD")
        price = mgr.get_latest_price()

        assert price is None


# ──────────────────────────────────────────────
# TestValidation
# ──────────────────────────────────────────────
class TestValidation:
    """Test data validation."""

    def test_validate_clean_data(self) -> None:
        now = datetime.now(timezone.utc)
        times = [now - timedelta(hours=i) for i in range(10, 0, -1)]
        df = pd.DataFrame({
            "time": times,
            "open": [2650 + i for i in range(10)],
            "high": [2655 + i for i in range(10)],
            "low": [2648 + i for i in range(10)],
            "close": [2652 + i for i in range(10)],
        })

        mgr = MarketDataManager("XAUUSD")
        q = mgr.validate(df, Timeframe.H1)

        assert q.is_valid is True
        assert q.total_bars == 10
        assert q.duplicate_timestamps == 0
        assert q.future_bars == 0
        assert q.invalid_ohlc == 0

    def test_validate_duplicate_timestamps(self) -> None:
        now = datetime.now(timezone.utc)
        times = [now - timedelta(hours=1)] * 5  # 5 lần cùng timestamp
        df = pd.DataFrame({
            "time": times,
            "open": [2650] * 5,
            "high": [2655] * 5,
            "low": [2648] * 5,
            "close": [2652] * 5,
        })

        mgr = MarketDataManager("XAUUSD")
        q = mgr.validate(df, Timeframe.H1)

        assert q.duplicate_timestamps == 4  # 4 duplicates

    def test_validate_future_bars(self) -> None:
        now = datetime.now(timezone.utc)
        times = [
            now - timedelta(hours=2),
            now - timedelta(hours=1),
            now + timedelta(hours=10),  # tương lai
        ]
        df = pd.DataFrame({
            "time": times,
            "open": [2650, 2651, 2652],
            "high": [2655, 2656, 2657],
            "low": [2648, 2649, 2650],
            "close": [2652, 2653, 2654],
        })

        mgr = MarketDataManager("XAUUSD")
        q = mgr.validate(df, Timeframe.H1)

        assert q.future_bars == 1

    def test_validate_invalid_ohlc(self) -> None:
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "time": [now - timedelta(hours=i) for i in range(3, 0, -1)],
            "open": [2650, 2652, 2645],
            "high": [2655, 2640, 2650],  # Nến 2: high < open (lỗi)
            "low": [2648, 2660, 2643],   # Nến 2: low > open (lỗi)
            "close": [2652, 2645, 2648],
        })

        mgr = MarketDataManager("XAUUSD")
        q = mgr.validate(df, Timeframe.H1)

        assert q.invalid_ohlc >= 1

    def test_validate_empty_dataframe(self) -> None:
        df = pd.DataFrame()

        mgr = MarketDataManager("XAUUSD")
        q = mgr.validate(df, Timeframe.H1)

        assert q.is_valid is False
        assert q.total_bars == 0

    def test_validate_none(self) -> None:
        mgr = MarketDataManager("XAUUSD")
        q = mgr.validate(None, Timeframe.H1)

        assert q.is_valid is False
