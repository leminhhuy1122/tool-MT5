# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Backtest Performance Metrics.

Tính toán các chỉ số thống kê hiệu suất giao dịch chuẩn:
- Win Rate, Profit Factor, Total Points, Net Profit ($).
- Max Drawdown ($ và %).
- Average Win / Average Loss, Average Risk:Reward.
- Chuỗi thắng / thua liên tiếp dài nhất.
- Sharpe Ratio.
"""

import math
import numpy as np

from app.backtest.models import BacktestResult, TradeRecord


def calculate_metrics(
    trades: list[TradeRecord],
    initial_balance: float = 10000.0,
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
) -> BacktestResult:
    """
    Tính toán toàn diện hiệu suất từ danh sách nhật ký lệnh.

    Args:
        trades: Danh sách các TradeRecord đã hoàn thành.
        initial_balance: Số dư ban đầu.
        symbol: Mã giao dịch.
        timeframe: Khung thời gian.

    Returns:
        BacktestResult đầy đủ các chỉ số.
    """
    total_trades = len(trades)
    if total_trades == 0:
        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            initial_balance=initial_balance,
            final_balance=initial_balance,
            equity_curve=[initial_balance],
        )

    # 1. Phân loại lệnh
    winning_trades = sum(1 for t in trades if t.is_win)
    losing_trades = sum(1 for t in trades if t.is_loss)
    breakeven_trades = sum(1 for t in trades if t.is_breakeven)

    win_rate = (winning_trades / total_trades) * 100.0

    # 2. Lợi nhuận & Điểm
    total_pnl_points = sum(t.pnl_points for t in trades)
    total_net_profit = sum(t.pnl_cash for t in trades)
    final_balance = initial_balance + total_net_profit
    return_pct = (total_net_profit / initial_balance * 100.0) if initial_balance > 0 else 0.0

    gross_profit = sum(t.pnl_cash for t in trades if t.is_win)
    gross_loss = abs(sum(t.pnl_cash for t in trades if t.is_loss))

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    else:
        profit_factor = 99.0 if gross_profit > 0 else 0.0

    # 3. Trung bình điểm
    avg_trade_points = round(total_pnl_points / total_trades, 2)
    avg_win_points = (
        round(sum(t.pnl_points for t in trades if t.is_win) / winning_trades, 2)
        if winning_trades > 0
        else 0.0
    )
    avg_loss_points = (
        round(abs(sum(t.pnl_points for t in trades if t.is_loss)) / losing_trades, 2)
        if losing_trades > 0
        else 0.0
    )

    # 4. Equity Curve & Drawdown
    equity_curve = [initial_balance]
    current_equity = initial_balance
    peak_equity = initial_balance
    max_dd_cash = 0.0
    max_dd_pct = 0.0

    for t in trades:
        current_equity += t.pnl_cash
        equity_curve.append(round(current_equity, 2))

        if current_equity > peak_equity:
            peak_equity = current_equity

        dd_cash = peak_equity - current_equity
        dd_pct = (dd_cash / peak_equity * 100.0) if peak_equity > 0 else 0.0

        if dd_cash > max_dd_cash:
            max_dd_cash = dd_cash
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    # 5. Chuỗi thắng/thua liên tiếp
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_wins = 0
    current_losses = 0

    for t in trades:
        if t.is_win:
            current_wins += 1
            current_losses = 0
            if current_wins > max_consecutive_wins:
                max_consecutive_wins = current_wins
        elif t.is_loss:
            current_losses += 1
            current_wins = 0
            if current_losses > max_consecutive_losses:
                max_consecutive_losses = current_losses
        else:  # Hòa vốn
            current_wins = 0
            current_losses = 0

    # 6. Sharpe Ratio (dựa trên % pnl mỗi lệnh)
    pnl_returns = [t.pnl_cash / initial_balance for t in trades]
    if len(pnl_returns) > 1:
        mean_ret = float(np.mean(pnl_returns))
        std_ret = float(np.std(pnl_returns))
        sharpe = round((mean_ret / std_ret) * math.sqrt(252), 2) if std_ret > 0 else 0.0
    else:
        sharpe = 0.0

    return BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        initial_balance=round(initial_balance, 2),
        final_balance=round(final_balance, 2),
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=breakeven_trades,
        win_rate=round(win_rate, 1),
        profit_factor=profit_factor,
        total_pnl_points=round(total_pnl_points, 1),
        total_net_profit=round(total_net_profit, 2),
        return_pct=round(return_pct, 2),
        max_drawdown_cash=round(max_dd_cash, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        avg_trade_points=avg_trade_points,
        avg_win_points=avg_win_points,
        avg_loss_points=avg_loss_points,
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
        sharpe_ratio=sharpe,
        trades=trades,
        equity_curve=equity_curve,
    )
