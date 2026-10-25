# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Historical Loader.
"""

from datetime import datetime, timezone
import pandas as pd
import pytest

from app.backtest.historical_loader import HistoricalLoader
from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.database.repository import MarketDataRepository


class TestHistoricalLoader:
    """Test suite cho HistoricalLoader."""

    def test_clean_and_prepare_empty(self):
        """clean_and_prepare trả về DataFrame rỗng khi input None hoặc empty."""
        assert HistoricalLoader.clean_and_prepare(None).empty
        assert HistoricalLoader.clean_and_prepare(pd.DataFrame()).empty

    def test_clean_and_prepare_sort_and_indicators(self):
        """clean_and_prepare sắp xếp tăng dần, xóa trùng lặp và thêm indicators."""
        # Tạo dữ liệu bị đảo ngược thứ tự thời gian và có trùng lặp
        times = pd.date_range("2026-01-01 10:00", periods=25, freq="5min")
        reversed_times = list(times)[::-1]
        # Thêm 1 dòng trùng lặp
        reversed_times.append(times[0])

        df = pd.DataFrame({
            "time": reversed_times,
            "open": [2000.0] * len(reversed_times),
            "high": [2005.0] * len(reversed_times),
            "low": [1995.0] * len(reversed_times),
            "close": [2002.0] * len(reversed_times),
        })

        clean = HistoricalLoader.clean_and_prepare(df)

        assert len(clean) == 25  # Đã loại bỏ trùng lặp
        # Thứ tự tăng dần
        assert clean.iloc[0]["time"] < clean.iloc[-1]["time"]
        # Đã tính indicators
        assert "ema_20" in clean.columns
        assert "rsi_14" in clean.columns
        assert "atr_14" in clean.columns

    def test_align_multi_timeframe_no_lookahead(self):
        """Kiểm tra việc đồng bộ khung thời gian tuyệt đối không có look-ahead bias."""
        times_m5 = pd.date_range("2026-01-01 00:00", periods=12, freq="5min")
        df_m5 = pd.DataFrame({
            "time": times_m5,
            "open": [2000.0] * 12,
            "high": [2002.0] * 12,
            "low": [1998.0] * 12,
            "close": [2001.0] * 12,
        })

        times_h1 = pd.date_range("2026-01-01 00:00", periods=3, freq="h")
        df_h1 = pd.DataFrame({
            "time": times_h1,
            "open": [2000.0] * 3,
            "high": [2010.0] * 3,
            "low": [1990.0] * 3,
            "close": [2005.0] * 3,
        })

        alignment = HistoricalLoader.align_multi_timeframe(df_m5, df_h1)

        for m5_idx, macro_slice in alignment.items():
            current_m5_time = df_m5.iloc[m5_idx]["time"]
            if not macro_slice.empty:
                # Mọi nến H1 được nhìn thấy phải có thời gian nhỏ hơn thời gian nến M5 hiện tại
                assert (macro_slice["time"] < current_m5_time).all()

    def test_load_from_db(self):
        """Nạp dữ liệu từ SQLite Database qua HistoricalLoader."""
        db = DatabaseManager(db_path=":memory:")
        run_migrations(db)
        repo = MarketDataRepository(db)

        # Lưu 15 nến
        times = pd.date_range("2026-01-01 00:00", periods=15, freq="5min")
        df_raw = pd.DataFrame({
            "time": times,
            "open": [2000.0] * 15,
            "high": [2005.0] * 15,
            "low": [1995.0] * 15,
            "close": [2002.0] * 15,
        })
        repo.save_candles("XAUUSD", "M5", df_raw)

        loader = HistoricalLoader(db)
        df_loaded = loader.load_from_db("XAUUSD", "M5", limit=10)

        assert len(df_loaded) == 10
        assert df_loaded.iloc[0]["time"] < df_loaded.iloc[-1]["time"]
