# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Backtest Data Models.

Định nghĩa các cấu trúc dữ liệu cho Backtest Engine:
- BacktestConfig: Cấu hình mô phỏng (spread, slippage, lot, vốn, quy tắc quản lý vốn).
- TradeStatus: Trạng thái lệnh trong quá trình backtest.
- TradeRecord: Nhật ký chi tiết của một lệnh giao dịch đã mô phỏng.
- BacktestResult: Tổng hợp hiệu suất và thống kê toàn diện.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TradeStatus(Enum):
    """Trạng thái lệnh trong backtest."""
    PENDING = "PENDING"               # Đang chờ giá vào Entry Zone
    OPEN = "OPEN"                     # Đã khớp lệnh
    CLOSED_TP1 = "CLOSED_TP1"         # Chốt toàn bộ tại TP1
    CLOSED_TP2 = "CLOSED_TP2"         # Chốt toàn bộ tại TP2
    CLOSED_SL = "CLOSED_SL"           # Chạm Stop Loss
    CLOSED_BE = "CLOSED_BE"           # Thoát tại điểm hòa vốn (Breakeven)
    INVALIDATED = "INVALIDATED"       # Hủy lệnh trước khi khớp Entry
    EXPIRED = "EXPIRED"               # Hết hạn trước khi khớp


@dataclass
class BacktestConfig:
    """Cấu hình cho Backtest Engine."""
    symbol: str = "XAUUSD"
    initial_balance: float = 10000.0        # Vốn ban đầu ($)
    lot_size: float = 0.1                   # Khối lượng vào lệnh chuẩn (lots)
    contract_size: float = 100.0            # 1 lot Gold = 100 oz (1 point = $10 cho 0.1 lot)
    spread_points: float = 1.5              # Spread trung bình (points / giá)
    slippage_points: float = 0.3            # Trượt giá mô phỏng khi khớp lệnh (points)
    
    # Quy tắc quản lý lệnh theo phong cách người dùng:
    # "Lãi 5 giá -> dời SL hòa vốn. Lãi 10 giá -> chốt 1 phần, gồng TP2"
    breakeven_trigger_points: float = 5.0   # Mốc lãi để dời SL về hòa vốn
    partial_tp_ratio: float = 0.5           # Tỷ lệ chốt tại TP1 (50%)
    max_active_trades: int = 1              # Tối đa số lệnh mở cùng lúc


@dataclass
class TradeRecord:
    """Nhật ký một lệnh giao dịch trong backtest."""
    trade_id: str
    signal_id: str
    direction: str                          # "BUY" hoặc "SELL"
    timeframe: str = "M5"
    
    # Giá mục tiêu
    planned_entry: float = 0.0
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    
    # Thực tế khớp lệnh
    actual_entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    actual_exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    
    # Kết quả
    status: TradeStatus = TradeStatus.PENDING
    pnl_points: float = 0.0                 # Lợi nhuận tính bằng giá (points)
    pnl_cash: float = 0.0                   # Lợi nhuận tính bằng USD ($)
    risk_reward_achieved: float = 0.0       # Tỷ lệ R:R thực tế đạt được
    
    # Thống kê biến động trong lệnh
    mfe_points: float = 0.0                 # Max Favorable Excursion (lãi cực đại trong lệnh)
    mae_points: float = 0.0                 # Max Adverse Excursion (lỗ cực đại trong lệnh)
    is_breakeven_triggered: bool = False    # Đã dời SL về BE chưa
    partial_closed: bool = False            # Đã chốt 50% tại TP1 chưa
    
    @property
    def is_win(self) -> bool:
        return self.pnl_points > 0.1

    @property
    def is_loss(self) -> bool:
        return self.pnl_points < -0.1

    @property
    def is_breakeven(self) -> bool:
        return abs(self.pnl_points) <= 0.1


@dataclass
class BacktestResult:
    """Kết quả tổng hợp của toàn bộ quá trình backtest."""
    symbol: str
    timeframe: str
    initial_balance: float
    final_balance: float
    
    # Số lượng lệnh
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    # Tỷ lệ & Hiệu suất
    win_rate: float = 0.0                   # % (0 - 100)
    profit_factor: float = 0.0              # Tổng lãi / Tổng lỗ
    total_pnl_points: float = 0.0           # Tổng giá ăn được (points)
    total_net_profit: float = 0.0           # Lợi nhuận ròng ($)
    return_pct: float = 0.0                 # % Tỷ suất sinh lời
    
    # Rủi ro & Drawdown
    max_drawdown_cash: float = 0.0          # Max Drawdown ($)
    max_drawdown_pct: float = 0.0           # Max Drawdown (%)
    
    # Thống kê lệnh
    avg_trade_points: float = 0.0
    avg_win_points: float = 0.0
    avg_loss_points: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    
    # Danh sách chi tiết
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    
    def summary(self) -> str:
        """Tóm tắt báo cáo kết quả backtest."""
        profit_str = f"+${self.total_net_profit:,.2f}" if self.total_net_profit >= 0 else f"-${abs(self.total_net_profit):,.2f}"
        return (
            f"=====================================================\n"
            f"  VIETKEY GOLD AI — BÁO CÁO HIỆU SUẤT BACKTEST\n"
            f"=====================================================\n"
            f"• Mã: {self.symbol} | Khung: {self.timeframe}\n"
            f"• Vốn ban đầu: ${self.initial_balance:,.2f} ➔ Vốn cuối: ${self.final_balance:,.2f}\n"
            f"• Lợi nhuận ròng: {profit_str} ({self.return_pct:+.2f}%)\n"
            f"• Tổng điểm ăn được: {self.total_pnl_points:+.1f} giá\n"
            f"-----------------------------------------------------\n"
            f"• Tổng số lệnh: {self.total_trades} (Thắng: {self.winning_trades} | Thua: {self.losing_trades} | Hòa: {self.breakeven_trades})\n"
            f"• Tỷ lệ thắng (Win Rate): {self.win_rate:.1f}%\n"
            f"• Hệ số lợi nhuận (Profit Factor): {self.profit_factor:.2f}\n"
            f"• Max Drawdown: ${self.max_drawdown_cash:,.2f} ({self.max_drawdown_pct:.2f}%)\n"
            f"• Trung bình lệnh thắng: +{self.avg_win_points:.1f} giá | Thua: -{self.avg_loss_points:.1f} giá\n"
            f"• Chuỗi thắng dài nhất: {self.max_consecutive_wins} | Thua dài nhất: {self.max_consecutive_losses}\n"
            f"• Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
            f"====================================================="
        )
