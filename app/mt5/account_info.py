# -*- coding: utf-8 -*-
"""
VietKey Gold AI — MT5 Account Info.

Lấy thông tin tài khoản từ MetaTrader 5 (chỉ đọc).
KHÔNG có chức năng giao dịch.
"""

from dataclasses import dataclass
from typing import Optional

import MetaTrader5 as mt5

from app.mt5.lock import mt5_lock
from logger import get_logger

log = get_logger("mt5.account")


@dataclass(frozen=True)
class AccountInfo:
    """Thông tin tài khoản MT5 (chỉ đọc)."""

    login: int
    server: str
    name: str
    currency: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    leverage: int
    trade_mode: int  # 0=demo, 1=contest, 2=real

    @property
    def is_demo(self) -> bool:
        """Kiểm tra có phải tài khoản demo không."""
        return self.trade_mode == 0

    @property
    def trade_mode_name(self) -> str:
        """Tên chế độ tài khoản."""
        modes = {0: "DEMO", 1: "CONTEST", 2: "REAL"}
        return modes.get(self.trade_mode, "UNKNOWN")


def get_account_info() -> Optional[AccountInfo]:
    """
    Lấy thông tin tài khoản hiện tại từ MT5.

    Returns:
        AccountInfo nếu thành công, None nếu lỗi.

    Lưu ý:
        Cần kết nối MT5 trước (qua MT5Connector).
    """
    with mt5_lock:
        info = mt5.account_info()
        if info is None:
            error = mt5.last_error()
            log.error("Không lấy được account info: %s", error)
            return None

    account = AccountInfo(
        login=info.login,
        server=info.server,
        name=info.name,
        currency=info.currency,
        balance=info.balance,
        equity=info.equity,
        margin=info.margin,
        margin_free=info.margin_free,
        leverage=info.leverage,
        trade_mode=info.trade_mode,
    )

    log.info(
        "Account: %d | %s | %s | Balance: %.2f %s | Leverage: 1:%d",
        account.login,
        account.trade_mode_name,
        account.server,
        account.balance,
        account.currency,
        account.leverage,
    )

    if not account.is_demo:
        log.warning(
            "⚠ CẢNH BÁO: Đây là tài khoản %s. "
            "VietKey Gold AI chỉ phát tín hiệu, KHÔNG đặt lệnh.",
            account.trade_mode_name,
        )

    return account
