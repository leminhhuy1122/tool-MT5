# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Walk-Forward Analysis.
"""

import pandas as pd
import pytest

from app.backtest.engine import BacktestEngine
from app.backtest.walk_forward import WalkForwardAnalyzer, WalkForwardReport


def _make_sample_df(n_bars: int = 150) -> pd.DataFrame:
    """Tạo DataFrame chuỗi nến dài phục vụ chia fold."""
    prices = [2000.0 + (i % 20) * 0.5 for i in range(n_bars)]
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01 00:00", periods=n_bars, freq="5min"),
        "open": prices,
        "high": [p + 2.0 for p in prices],
        "low": [p - 2.0 for p in prices],
        "close": prices,
        "tick_volume": [100.0] * n_bars,
    })


class TestWalkForwardAnalysis:
    """Test suite cho WalkForwardAnalyzer."""

    def test_walk_forward_insufficient_data(self):
        """Khi dữ liệu quá ngắn không đủ chia fold."""
        engine = BacktestEngine()
        analyzer = WalkForwardAnalyzer(engine, num_folds=3)
        df_short = _make_sample_df(n_bars=30)  # 30 / 3 = 10 bars < 40 bars

        report = analyzer.run(df_exec=df_short)
        assert report.total_folds == 0
        assert report.consistency_rate == 0.0

    def test_walk_forward_successful_run(self):
        """Chạy phân tích Walk-Forward thành công qua các chu kỳ."""
        engine = BacktestEngine()
        analyzer = WalkForwardAnalyzer(engine, num_folds=3)
        df = _make_sample_df(n_bars=150)

        report = analyzer.run(df_exec=df)

        assert report.symbol == "XAUUSD"
        assert report.total_folds == 3
        assert len(report.folds) == 3
        assert 0.0 <= report.consistency_rate <= 100.0
        assert "WALK-FORWARD" in report.summary()
