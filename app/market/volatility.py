# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Volatility Analysis.

Phân tích biến động thị trường:
- ATR-based volatility classification.
- Spread monitoring.
- Biên độ nến (candle range analysis).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd
import numpy as np

from app.market.indicators import calc_atr
from logger import get_logger

log = get_logger("market.volatility")


class VolatilityLevel(Enum):
    """Mức biến động."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass(frozen=True)
class VolatilityResult:
    """Kết quả phân tích biến động."""
    current_atr: float
    avg_atr: float
    atr_ratio: float            # current / avg
    level: VolatilityLevel
    current_spread: float
    avg_spread: float
    spread_ratio: float         # current / avg
    is_spread_high: bool        # spread bất thường

    def __str__(self) -> str:
        return (
            f"Volatility: {self.level.value} | "
            f"ATR: {self.current_atr:.2f} ({self.atr_ratio:.1%} of avg) | "
            f"Spread: {self.current_spread:.2f} ({self.spread_ratio:.1%} of avg)"
        )


def classify_volatility(atr_ratio: float) -> VolatilityLevel:
    """
    Phân loại mức biến động dựa trên ATR ratio.

    Args:
        atr_ratio: Tỷ lệ ATR hiện tại / ATR trung bình.

    Returns:
        VolatilityLevel.
    """
    if atr_ratio < 0.5:
        return VolatilityLevel.LOW
    elif atr_ratio < 1.5:
        return VolatilityLevel.NORMAL
    elif atr_ratio < 2.5:
        return VolatilityLevel.HIGH
    else:
        return VolatilityLevel.EXTREME


def analyze_volatility(
    df: pd.DataFrame,
    atr_period: int = 14,
    lookback: int = 50,
    spread_threshold: float = 2.0,
) -> Optional[VolatilityResult]:
    """
    Phân tích biến động thị trường.

    Args:
        df: DataFrame OHLCV + spread.
        atr_period: Period cho ATR.
        lookback: Số nến lookback cho trung bình.
        spread_threshold: Ngưỡng spread/avg_spread để coi là bất thường.

    Returns:
        VolatilityResult hoặc None nếu thiếu dữ liệu.
    """
    if len(df) < atr_period + 1:
        log.warning("Không đủ dữ liệu cho volatility analysis")
        return None

    atr = calc_atr(df, period=atr_period)
    current_atr = float(atr.iloc[-1])

    # ATR trung bình trong lookback
    atr_window = atr.iloc[-lookback:] if len(atr) >= lookback else atr
    avg_atr = float(atr_window.mean())
    atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

    level = classify_volatility(atr_ratio)

    # Spread analysis
    current_spread = 0.0
    avg_spread = 0.0
    spread_ratio = 1.0
    is_spread_high = False

    if "spread" in df.columns:
        spreads = df["spread"].iloc[-lookback:] if len(df) >= lookback else df["spread"]
        current_spread = float(df["spread"].iloc[-1])
        avg_spread = float(spreads.mean())
        spread_ratio = current_spread / avg_spread if avg_spread > 0 else 1.0
        is_spread_high = spread_ratio > spread_threshold

    result = VolatilityResult(
        current_atr=current_atr,
        avg_atr=avg_atr,
        atr_ratio=atr_ratio,
        level=level,
        current_spread=current_spread,
        avg_spread=avg_spread,
        spread_ratio=spread_ratio,
        is_spread_high=is_spread_high,
    )

    log.debug("Volatility: %s", result)
    return result


def calc_candle_range(df: pd.DataFrame) -> pd.Series:
    """
    Tính biên độ nến (high - low).

    Args:
        df: DataFrame với columns: high, low.

    Returns:
        Series biên độ nến.
    """
    candle_range = df["high"] - df["low"]
    candle_range.name = "candle_range"
    return candle_range


def calc_body_ratio(df: pd.DataFrame) -> pd.Series:
    """
    Tính tỷ lệ thân nến / biên độ nến.

    Body ratio cao → nến mạnh (momentum).
    Body ratio thấp → nến doji/indecision.

    Args:
        df: DataFrame với columns: open, high, low, close.

    Returns:
        Series tỷ lệ thân nến (0 đến 1).
    """
    body = (df["close"] - df["open"]).abs()
    full_range = df["high"] - df["low"]

    # Tránh chia cho 0
    ratio = body / full_range.replace(0, np.nan)
    ratio = ratio.fillna(0)
    ratio.name = "body_ratio"
    return ratio
