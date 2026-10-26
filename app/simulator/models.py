# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Paper Trading Models.

Định nghĩa cấu trúc dữ liệu cho Ví Đầu Tư Ảo (Paper Wallet),
Vị thế đang mở (Paper Position) và Lịch sử giao dịch (Paper Trade History).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class PaperWallet:
    """Mô hình dữ liệu Ví Đầu Tư Ảo."""

    wallet_id: str = "default"
    name: str = "Ví Demo 0.01 Lot"
    initial_balance: float = 50.0
    balance: float = 50.0
    equity: float = 50.0
    currency: str = "USD"
    leverage: int = 500
    default_lot: float = 0.01
    is_auto_trading: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Thuộc tính động tính toán thời gian thực
    used_margin: float = 0.0
    free_margin: float = 50.0
    margin_level: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    @property
    def floating_pnl(self) -> float:
        """Lợi nhuận thả nổi tức thời = Equity - Balance."""
        return round(self.equity - self.balance, 2)

    @property
    def net_profit_usd(self) -> float:
        """Lợi nhuận ròng tích lũy = Balance - Initial Balance."""
        return round(self.balance - self.initial_balance, 2)

    @property
    def roi_percent(self) -> float:
        """Tỷ suất lợi nhuận đầu tư trên vốn ban đầu (ROI %)."""
        if self.initial_balance <= 0:
            return 0.0
        return round((self.net_profit_usd / self.initial_balance) * 100.0, 2)

    def to_dict(self) -> dict:
        """Chuyển đổi thành từ điển JSON phục vụ API và UI."""
        data = asdict(self)
        data["floating_pnl"] = self.floating_pnl
        data["net_profit_usd"] = self.net_profit_usd
        data["roi_percent"] = self.roi_percent
        return data


@dataclass
class PaperPosition:
    """Mô hình dữ liệu lệnh ảo đang chạy trên thị trường."""

    position_id: str
    wallet_id: str = "default"
    signal_id: Optional[str] = None
    symbol: str = "XAUUSD"
    direction: str = "BUY"  # BUY / SELL
    volume: float = 0.01
    open_price: float = 0.0
    current_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: Optional[float] = None
    floating_pnl: float = 0.0
    floating_pnl_percent: float = 0.0
    status: str = "OPEN"
    open_time: Optional[str] = None
    last_update: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PaperTradeHistory:
    """Mô hình dữ liệu lịch sử các lệnh đã đóng hoàn tất."""

    trade_id: str
    wallet_id: str = "default"
    signal_id: Optional[str] = None
    symbol: str = "XAUUSD"
    direction: str = "BUY"
    volume: float = 0.01
    open_price: float = 0.0
    close_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl_usd: float = 0.0
    pnl_percent: float = 0.0
    pnl_pips: float = 0.0
    close_reason: str = "MANUAL"  # TAKE_PROFIT, STOP_LOSS, TRAILING_STOP, BREAKEVEN, MOMENTUM_EXHAUSTION, MANUAL
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    duration_seconds: int = 0

    def to_dict(self) -> dict:
        return asdict(self)
