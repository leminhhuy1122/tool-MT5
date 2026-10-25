# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Technical Indicators.

Tính toán các chỉ báo kỹ thuật cơ bản:
- EMA (Exponential Moving Average): 20, 50, 200.
- RSI (Relative Strength Index).
- ATR (Average True Range).

Quy tắc:
- Không sử dụng dữ liệu tương lai (look-ahead bias).
- Tính trên nến ĐÃ ĐÓNG.
- Tất cả hàm nhận DataFrame và trả DataFrame mới (không mutate input).
- Các tham số có thể cấu hình.
"""

import pandas as pd
import numpy as np
from typing import Optional

from logger import get_logger

log = get_logger("market.indicators")


# ──────────────────────────────────────────────
# EMA — Exponential Moving Average
# ──────────────────────────────────────────────
def calc_ema(
    series: pd.Series,
    period: int,
    column_name: Optional[str] = None,
) -> pd.Series:
    """
    Tính EMA (Exponential Moving Average).

    Args:
        series: Chuỗi giá (thường là close).
        period: Số chu kỳ.
        column_name: Tên column kết quả. Mặc định: 'ema_{period}'.

    Returns:
        Series chứa giá trị EMA.
    """
    if len(series) < period:
        log.warning("Không đủ dữ liệu cho EMA(%d): chỉ có %d bars", period, len(series))
        return pd.Series(np.nan, index=series.index, name=column_name or f"ema_{period}")

    ema = series.ewm(span=period, adjust=False).mean()
    ema.name = column_name or f"ema_{period}"
    return ema


def add_ema(
    df: pd.DataFrame,
    periods: list[int] | None = None,
    source_col: str = "close",
) -> pd.DataFrame:
    """
    Thêm các cột EMA vào DataFrame.

    Args:
        df: DataFrame với cột giá.
        periods: Danh sách period. Mặc định: [20, 50, 200].
        source_col: Cột nguồn. Mặc định: 'close'.

    Returns:
        DataFrame mới với các cột EMA thêm vào.
    """
    if periods is None:
        periods = [20, 50, 200]

    result = df.copy()
    for period in periods:
        result[f"ema_{period}"] = calc_ema(result[source_col], period)

    log.debug("Đã tính EMA %s trên %d bars", periods, len(df))
    return result


# ──────────────────────────────────────────────
# RSI — Relative Strength Index
# ──────────────────────────────────────────────
def calc_rsi(
    series: pd.Series,
    period: int = 14,
    column_name: Optional[str] = None,
) -> pd.Series:
    """
    Tính RSI (Relative Strength Index) theo phương pháp Wilder.

    Args:
        series: Chuỗi giá (thường là close).
        period: Số chu kỳ. Mặc định: 14.
        column_name: Tên column kết quả.

    Returns:
        Series chứa giá trị RSI (0-100).
    """
    name = column_name or f"rsi_{period}"

    if len(series) < period + 1:
        log.warning("Không đủ dữ liệu cho RSI(%d): chỉ có %d bars", period, len(series))
        return pd.Series(np.nan, index=series.index, name=name)

    # Tính delta (thay đổi giá)
    delta = series.diff()

    # Tách gain và loss
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing (EMA với alpha = 1/period)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Tính RS và RSI
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Xử lý trường hợp avg_loss = 0 (tất cả gain)
    rsi = rsi.where(avg_loss > 0, 100.0)

    rsi.name = name
    return rsi


def add_rsi(
    df: pd.DataFrame,
    period: int = 14,
    source_col: str = "close",
) -> pd.DataFrame:
    """
    Thêm cột RSI vào DataFrame.

    Args:
        df: DataFrame với cột giá.
        period: Số chu kỳ RSI. Mặc định: 14.
        source_col: Cột nguồn.

    Returns:
        DataFrame mới với cột RSI thêm vào.
    """
    result = df.copy()
    result[f"rsi_{period}"] = calc_rsi(result[source_col], period)
    log.debug("Đã tính RSI(%d) trên %d bars", period, len(df))
    return result


# ──────────────────────────────────────────────
# ATR — Average True Range
# ──────────────────────────────────────────────
def calc_true_range(df: pd.DataFrame) -> pd.Series:
    """
    Tính True Range.

    TR = max(
        high - low,
        abs(high - previous_close),
        abs(low - previous_close)
    )

    Args:
        df: DataFrame với columns: high, low, close.

    Returns:
        Series chứa True Range.
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr.name = "true_range"
    return tr


def calc_atr(
    df: pd.DataFrame,
    period: int = 14,
    column_name: Optional[str] = None,
) -> pd.Series:
    """
    Tính ATR (Average True Range) theo phương pháp Wilder.

    Args:
        df: DataFrame với columns: high, low, close.
        period: Số chu kỳ. Mặc định: 14.
        column_name: Tên column kết quả.

    Returns:
        Series chứa giá trị ATR.
    """
    name = column_name or f"atr_{period}"

    if len(df) < period + 1:
        log.warning("Không đủ dữ liệu cho ATR(%d): chỉ có %d bars", period, len(df))
        return pd.Series(np.nan, index=df.index, name=name)

    tr = calc_true_range(df)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    atr.name = name
    return atr


def add_atr(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.DataFrame:
    """
    Thêm cột ATR vào DataFrame.

    Args:
        df: DataFrame với columns: high, low, close.
        period: Số chu kỳ ATR. Mặc định: 14.

    Returns:
        DataFrame mới với cột ATR thêm vào.
    """
    result = df.copy()
    result[f"atr_{period}"] = calc_atr(result, period)
    log.debug("Đã tính ATR(%d) trên %d bars", period, len(df))
    return result


# ──────────────────────────────────────────────
# Convenience: thêm tất cả indicators cơ bản
# ──────────────────────────────────────────────
def add_all_indicators(
    df: pd.DataFrame,
    ema_periods: list[int] | None = None,
    rsi_period: int = 14,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Thêm tất cả indicators cơ bản vào DataFrame.

    Args:
        df: DataFrame gốc (OHLCV).
        ema_periods: Danh sách EMA periods. Mặc định: [20, 50, 200].
        rsi_period: RSI period. Mặc định: 14.
        atr_period: ATR period. Mặc định: 14.

    Returns:
        DataFrame mới với các indicators.
    """
    result = add_ema(df, periods=ema_periods)
    result = add_rsi(result, period=rsi_period)
    result = add_atr(result, period=atr_period)

    log.info(
        "✓ Đã tính tất cả indicators trên %d bars (EMA %s, RSI(%d), ATR(%d))",
        len(df), ema_periods or [20, 50, 200], rsi_period, atr_period,
    )
    return result
