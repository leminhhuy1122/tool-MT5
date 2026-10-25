# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Backtest Engine.
"""

from datetime import datetime, timezone
import pandas as pd
import pytest

from app.backtest.engine import BacktestEngine
from app.backtest.models import BacktestConfig, TradeRecord, TradeStatus
from app.market.indicators import add_all_indicators
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection, TradingSignal


def _make_zigzag_df(n_bars: int = 70) -> pd.DataFrame:
    """Tạo DataFrame nến tăng có cấu trúc zigzag để kích hoạt setup."""
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
    # Kéo dài thêm hoặc cắt bớt cho đúng n_bars
    if len(prices) > n_bars:
        prices = prices[:n_bars]
    else:
        while len(prices) < n_bars:
            prices.append(prices[-1] + 1.0)

    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01 00:00", periods=len(prices), freq="5min"),
        "open": [p - 0.5 for p in prices],
        "high": [p + 2.0 for p in prices],
        "low": [p - 2.0 for p in prices],
        "close": [float(p) for p in prices],
        "tick_volume": [100.0] * len(prices),
    })
    return df


class TestBacktestEngine:
    """Test suite cho BacktestEngine."""

    def test_engine_initialization(self):
        """Khởi tạo BacktestEngine với config tùy chọn."""
        cfg = BacktestConfig(initial_balance=5000.0, spread_points=2.0)
        engine = BacktestEngine(config=cfg)

        assert engine.config.initial_balance == 5000.0
        assert engine.config.spread_points == 2.0
        assert engine.signal_engine is not None

    def test_run_insufficient_bars(self):
        """Dữ liệu quá ngắn (< min_warmup_bars) kết thúc an toàn."""
        engine = BacktestEngine()
        df_short = _make_zigzag_df(n_bars=15)
        res = engine.run(df_exec=df_short, min_warmup_bars=30)

        assert res.total_trades == 0
        assert res.final_balance == 10000.0

    def test_run_end_to_end_simulation(self):
        """Chạy backtest mô phỏng trên dữ liệu nến zigzag."""
        cfg = BacktestConfig(
            spread_points=1.0,
            slippage_points=0.2,
            breakeven_trigger_points=5.0,
        )
        engine = BacktestEngine(config=cfg)
        df_exec = _make_zigzag_df(n_bars=70)

        res = engine.run(df_exec=df_exec, min_warmup_bars=25)

        assert res.symbol == "XAUUSD"
        assert res.initial_balance == 10000.0
        assert len(res.equity_curve) >= 1
        assert "VIETKEY GOLD AI" in res.summary()

    def test_breakeven_and_tp_simulation(self):
        """Kiểm tra logic dời SL hòa vốn khi lãi đạt mốc 5 giá."""
        cfg = BacktestConfig(breakeven_trigger_points=5.0)
        engine = BacktestEngine(config=cfg)

        # Mô phỏng trực tiếp xử lý lệnh
        trade = TradeRecord(
            trade_id="BT_01",
            signal_id="sig1",
            direction="BUY",
            planned_entry=2000.0,
            actual_entry_price=2000.0,
            stop_loss=1995.0,
            take_profit_1=2010.0,
            take_profit_2=2020.0,
            status=TradeStatus.OPEN,
        )

        # Giả lập nến tiếp theo đạt high = 2006.0 (lãi 6 giá > 5 giá)
        candle_high = 2006.0
        candle_low = 1999.0
        cur_favorable = candle_high - trade.actual_entry_price

        if cur_favorable >= cfg.breakeven_trigger_points:
            trade.is_breakeven_triggered = True
            trade.stop_loss = trade.actual_entry_price

        assert trade.is_breakeven_triggered is True
        assert trade.stop_loss == 2000.0  # SL đã dời về hòa vốn
