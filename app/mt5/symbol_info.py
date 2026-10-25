# -*- coding: utf-8 -*-
"""
VietKey Gold AI — MT5 Symbol Info.

Kiểm tra và lấy thông tin symbol XAUUSD từ MetaTrader 5.
"""

from dataclasses import dataclass
from typing import Optional

import MetaTrader5 as mt5

from logger import get_logger

log = get_logger("mt5.symbol")


@dataclass(frozen=True)
class SymbolInfo:
    """Thông tin symbol từ MT5."""

    name: str
    description: str
    point: float        # Giá trị nhỏ nhất thay đổi được (ví dụ: 0.01)
    digits: int         # Số chữ số thập phân
    spread: int         # Spread hiện tại (points)
    trade_mode: int     # Chế độ giao dịch
    volume_min: float   # Lot tối thiểu
    volume_max: float   # Lot tối đa
    volume_step: float  # Bước lot
    bid: float          # Giá bid hiện tại
    ask: float          # Giá ask hiện tại
    visible: bool       # Symbol có hiển thị trong Market Watch không

    @property
    def spread_value(self) -> float:
        """Spread tính bằng đơn vị giá (không phải points)."""
        return self.spread * self.point

    @property
    def is_tradeable(self) -> bool:
        """Symbol có thể giao dịch không (trade_mode != 0)."""
        return self.trade_mode != 0


def check_symbol(symbol: str) -> bool:
    """
    Kiểm tra symbol có tồn tại và hiển thị trong MT5 không.
    Nếu chưa hiển thị, tự động thêm vào Market Watch.

    Args:
        symbol: Tên symbol (ví dụ: "XAUUSD").

    Returns:
        True nếu symbol sẵn sàng.
    """
    # Kiểm tra symbol tồn tại
    info = mt5.symbol_info(symbol)
    if info is None:
        log.error("Symbol '%s' không tồn tại trên broker này", symbol)
        return False

    # Thêm vào Market Watch nếu chưa hiển thị
    if not info.visible:
        log.info("Symbol '%s' chưa hiển thị. Đang thêm vào Market Watch...", symbol)
        if not mt5.symbol_select(symbol, True):
            log.error("Không thể thêm '%s' vào Market Watch", symbol)
            return False
        log.info("✓ Đã thêm '%s' vào Market Watch", symbol)

    log.info("✓ Symbol '%s' sẵn sàng", symbol)
    return True


def get_symbol_info(symbol: str) -> Optional[SymbolInfo]:
    """
    Lấy thông tin chi tiết của symbol.

    Args:
        symbol: Tên symbol (ví dụ: "XAUUSD").

    Returns:
        SymbolInfo nếu thành công, None nếu lỗi.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        error = mt5.last_error()
        log.error("Không lấy được thông tin '%s': %s", symbol, error)
        return None

    sym = SymbolInfo(
        name=info.name,
        description=info.description,
        point=info.point,
        digits=info.digits,
        spread=info.spread,
        trade_mode=info.trade_mode,
        volume_min=info.volume_min,
        volume_max=info.volume_max,
        volume_step=info.volume_step,
        bid=info.bid,
        ask=info.ask,
        visible=info.visible,
    )

    log.info(
        "Symbol: %s | Bid: %s | Ask: %s | Spread: %d (%.2f) | Digits: %d",
        sym.name,
        f"{sym.bid:.{sym.digits}f}",
        f"{sym.ask:.{sym.digits}f}",
        sym.spread,
        sym.spread_value,
        sym.digits,
    )

    return sym
