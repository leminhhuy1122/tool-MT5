# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Timeframe Manager.

Quản lý timeframes cho phân tích đa khung thời gian.
Định nghĩa mapping giữa tên timeframe và MT5 constant.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import MetaTrader5 as mt5


class Timeframe(Enum):
    """
    Các timeframe được hỗ trợ.

    Theo kế hoạch:
    - H4: xu hướng tổng thể.
    - H1: cấu trúc thị trường.
    - M15: setup giao dịch.
    - M5: xác nhận entry.
    """

    M5 = ("M5", mt5.TIMEFRAME_M5, 5)
    M15 = ("M15", mt5.TIMEFRAME_M15, 15)
    H1 = ("H1", mt5.TIMEFRAME_H1, 60)
    H4 = ("H4", mt5.TIMEFRAME_H4, 240)
    D1 = ("D1", mt5.TIMEFRAME_D1, 1440)

    def __init__(self, label: str, mt5_const: int, minutes: int) -> None:
        self.label = label
        self.mt5_const = mt5_const
        self.minutes = minutes

    def __str__(self) -> str:
        return self.label


# Timeframes mặc định cho phân tích (theo kế hoạch)
DEFAULT_TIMEFRAMES: list[Timeframe] = [
    Timeframe.H4,   # xu hướng tổng thể
    Timeframe.H1,   # cấu trúc thị trường
    Timeframe.M15,  # setup giao dịch
    Timeframe.M5,   # xác nhận entry
]

# Số nến mặc định cần lấy cho mỗi timeframe
# Giữ thấp để tiết kiệm RAM (theo Resource Optimization)
DEFAULT_BAR_COUNTS: dict[Timeframe, int] = {
    Timeframe.M5: 200,
    Timeframe.M15: 200,
    Timeframe.H1: 200,
    Timeframe.H4: 200,
    Timeframe.D1: 100,
}


def get_timeframe_by_label(label: str) -> Optional[Timeframe]:
    """
    Tìm Timeframe theo label (ví dụ: "H1", "M15").

    Args:
        label: Label của timeframe.

    Returns:
        Timeframe nếu tìm thấy, None nếu không.
    """
    label_upper = label.upper()
    for tf in Timeframe:
        if tf.label == label_upper:
            return tf
    return None
