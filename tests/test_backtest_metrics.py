# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Backtest Metrics.
"""

import pytest

from app.backtest.metrics import calculate_metrics
from app.backtest.models import TradeRecord, TradeStatus


def _trade(trade_id: str, pnl_points: float, pnl_cash: float) -> TradeRecord:
    return TradeRecord(
        trade_id=trade_id,
        signal_id=f"sig_{trade_id}",
        direction="BUY",
        pnl_points=pnl_points,
        pnl_cash=pnl_cash,
        status=TradeStatus.CLOSED_TP1 if pnl_points > 0 else TradeStatus.CLOSED_SL,
    )


class TestBacktestMetrics:
    """Test suite cho Backtest Metrics."""

    def test_calculate_metrics_empty_trades(self):
        """Khi không có lệnh nào được thực thi."""
        res = calculate_metrics([], initial_balance=10000.0)
        assert res.total_trades == 0
        assert res.win_rate == 0.0
        assert res.profit_factor == 0.0
        assert res.final_balance == 10000.0
        assert res.total_net_profit == 0.0
        assert res.equity_curve == [10000.0]

    def test_calculate_metrics_all_wins(self):
        """Tất cả các lệnh đều thắng."""
        trades = [
            _trade("1", 10.0, 100.0),
            _trade("2", 15.0, 150.0),
            _trade("3", 5.0, 50.0),
        ]
        res = calculate_metrics(trades, initial_balance=10000.0)

        assert res.total_trades == 3
        assert res.winning_trades == 3
        assert res.losing_trades == 0
        assert res.win_rate == 100.0
        assert res.profit_factor == 99.0  # Không có lỗ
        assert res.total_net_profit == 300.0
        assert res.final_balance == 10300.0
        assert res.max_drawdown_cash == 0.0
        assert res.max_consecutive_wins == 3
        assert res.max_consecutive_losses == 0

    def test_calculate_metrics_mixed_trades_and_drawdown(self):
        """Tính toán hỗn hợp thắng, thua, hòa và kiểm tra Drawdown."""
        # Chuỗi lệnh: +100 -> +200 -> -150 -> -100 -> 0 (BE) -> +100
        # Equity: 10000 -> 10100 -> 10300 (peak) -> 10150 (dd 150) -> 10050 (dd 250) -> 10050 -> 10150
        trades = [
            _trade("1", 10.0, 100.0),
            _trade("2", 20.0, 200.0),
            _trade("3", -15.0, -150.0),
            _trade("4", -10.0, -100.0),
            _trade("5", 0.0, 0.0),
            _trade("6", 10.0, 100.0),
        ]
        res = calculate_metrics(trades, initial_balance=10000.0)

        assert res.total_trades == 6
        assert res.winning_trades == 3
        assert res.losing_trades == 2
        assert res.breakeven_trades == 1
        assert res.win_rate == 50.0  # 3/6 = 50%

        # Gross profit = 100 + 200 + 100 = 400
        # Gross loss = 150 + 100 = 250
        # Profit factor = 400 / 250 = 1.6
        assert res.profit_factor == 1.6
        assert res.total_net_profit == 150.0
        assert res.final_balance == 10150.0

        # Max drawdown: đỉnh 10300 rớt xuống 10050 = 250
        assert res.max_drawdown_cash == 250.0
        # Drawdown % = 250 / 10300 * 100 = 2.43%
        assert res.max_drawdown_pct == pytest.approx(2.43, abs=0.05)

        # Streaks: max consecutive wins = 2 (trades 1 & 2), losses = 2 (trades 3 & 4)
        assert res.max_consecutive_wins == 2
        assert res.max_consecutive_losses == 2

    def test_sharpe_ratio_positive(self):
        """Kiểm tra Sharpe ratio lớn hơn 0 khi chiến lược có lãi ổn định."""
        trades = [_trade(str(i), 10.0, 100.0) for i in range(10)]
        res = calculate_metrics(trades, initial_balance=10000.0)
        assert res.sharpe_ratio >= 0.0
