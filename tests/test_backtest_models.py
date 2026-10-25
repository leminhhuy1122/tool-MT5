# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Backtest Models.
"""

import pytest

from app.backtest.models import (
    BacktestConfig,
    BacktestResult,
    TradeRecord,
    TradeStatus,
)


class TestBacktestModels:
    """Test suite cho Backtest Data Models."""

    def test_backtest_config_defaults(self):
        """Kiểm tra giá trị mặc định của BacktestConfig."""
        cfg = BacktestConfig()
        assert cfg.symbol == "XAUUSD"
        assert cfg.initial_balance == 10000.0
        assert cfg.lot_size == 0.1
        assert cfg.contract_size == 100.0
        assert cfg.spread_points == 1.5
        assert cfg.slippage_points == 0.3
        assert cfg.breakeven_trigger_points == 5.0
        assert cfg.partial_tp_ratio == 0.5

    def test_trade_status_enums(self):
        """Kiểm tra các giá trị của TradeStatus."""
        assert TradeStatus.PENDING.value == "PENDING"
        assert TradeStatus.OPEN.value == "OPEN"
        assert TradeStatus.CLOSED_TP1.value == "CLOSED_TP1"
        assert TradeStatus.CLOSED_TP2.value == "CLOSED_TP2"
        assert TradeStatus.CLOSED_SL.value == "CLOSED_SL"
        assert TradeStatus.CLOSED_BE.value == "CLOSED_BE"
        assert TradeStatus.INVALIDATED.value == "INVALIDATED"
        assert TradeStatus.EXPIRED.value == "EXPIRED"

    def test_trade_record_properties(self):
        """Kiểm tra các thuộc tính is_win, is_loss, is_breakeven của TradeRecord."""
        win_trade = TradeRecord(trade_id="1", signal_id="s1", direction="BUY", pnl_points=10.0)
        assert win_trade.is_win is True
        assert win_trade.is_loss is False
        assert win_trade.is_breakeven is False

        loss_trade = TradeRecord(trade_id="2", signal_id="s2", direction="SELL", pnl_points=-5.0)
        assert loss_trade.is_win is False
        assert loss_trade.is_loss is True
        assert loss_trade.is_breakeven is False

        be_trade = TradeRecord(trade_id="3", signal_id="s3", direction="BUY", pnl_points=0.0)
        assert be_trade.is_win is False
        assert be_trade.is_loss is False
        assert be_trade.is_breakeven is True

    def test_backtest_result_summary(self):
        """Kiểm tra hàm summary của BacktestResult."""
        res = BacktestResult(
            symbol="XAUUSD",
            timeframe="M5",
            initial_balance=10000.0,
            final_balance=11500.0,
            total_trades=10,
            winning_trades=7,
            losing_trades=2,
            breakeven_trades=1,
            win_rate=70.0,
            profit_factor=2.5,
            total_net_profit=1500.0,
            total_pnl_points=150.0,
            return_pct=15.0,
        )
        summary = res.summary()
        assert "VIETKEY GOLD AI" in summary
        assert "XAUUSD" in summary
        assert "70.0%" in summary
        assert "2.50" in summary
        assert "+$1,500.00" in summary
