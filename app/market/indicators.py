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
# ADX — Average Directional Index (Wilder)
# ──────────────────────────────────────────────
def calc_adx(
    df: pd.DataFrame,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Tính ADX (Average Directional Index) và +DI, -DI theo phương pháp Wilder.

    Args:
        df: DataFrame với columns: high, low, close.
        period: Chu kỳ (mặc định 14).

    Returns:
        tuple (adx, plus_di, minus_di) dưới dạng Series.
    """
    if len(df) < period * 2:
        log.warning("Không đủ dữ liệu cho ADX(%d): chỉ có %d bars", period, len(df))
        empty = pd.Series(np.nan, index=df.index)
        return empty.rename(f"adx_{period}"), empty.rename(f"plus_di_{period}"), empty.rename(f"minus_di_{period}")

    high = df["high"]
    low = df["low"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_series = pd.Series(plus_dm, index=df.index)
    minus_dm_series = pd.Series(minus_dm, index=df.index)

    tr = calc_true_range(df)

    # Wilder smoothing (alpha = 1 / period)
    smoothed_tr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    smoothed_plus_dm = plus_dm_series.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    smoothed_minus_dm = minus_dm_series.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    plus_di = 100.0 * (smoothed_plus_dm / smoothed_tr.replace(0, np.nan))
    minus_di = 100.0 * (smoothed_minus_dm / smoothed_tr.replace(0, np.nan))

    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100.0 * (di_diff / di_sum.replace(0, np.nan))
    dx = dx.fillna(0.0)

    adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    adx.name = f"adx_{period}"
    plus_di.name = f"plus_di_{period}"
    minus_di.name = f"minus_di_{period}"

    return adx, plus_di, minus_di


def add_adx(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.DataFrame:
    """Thêm các cột ADX, +DI, -DI vào DataFrame."""
    result = df.copy()
    adx, plus_di, minus_di = calc_adx(result, period=period)
    result[f"adx_{period}"] = adx
    result[f"plus_di_{period}"] = plus_di
    result[f"minus_di_{period}"] = minus_di
    return result


# ──────────────────────────────────────────────
# Bollinger Bands & Bandwidth
# ──────────────────────────────────────────────
def calc_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    source_col: str = "close",
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Tính dải Bollinger Bands và Bandwidth.

    Bandwidth = (Upper - Lower) / Middle * 100

    Args:
        df: DataFrame chứa giá.
        period: Số chu kỳ SMA (mặc định 20).
        std_dev: Độ lệch chuẩn (mặc định 2.0).
        source_col: Cột nguồn (mặc định 'close').

    Returns:
        tuple (upper, middle, lower, bandwidth)
    """
    series = df[source_col]
    if len(series) < period:
        empty = pd.Series(np.nan, index=series.index)
        return (
            empty.rename("bb_upper"),
            empty.rename("bb_middle"),
            empty.rename("bb_lower"),
            empty.rename("bb_width"),
        )

    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    bandwidth = ((upper - lower) / middle.replace(0, np.nan)) * 100.0

    upper.name = "bb_upper"
    middle.name = "bb_middle"
    lower.name = "bb_lower"
    bandwidth.name = "bb_width"

    return upper, middle, lower, bandwidth


def add_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    source_col: str = "close",
) -> pd.DataFrame:
    """Thêm các cột Bollinger Bands vào DataFrame."""
    result = df.copy()
    upper, middle, lower, bandwidth = calc_bollinger_bands(
        result, period=period, std_dev=std_dev, source_col=source_col,
    )
    result["bb_upper"] = upper
    result["bb_middle"] = middle
    result["bb_lower"] = lower
    result["bb_width"] = bandwidth
    return result


# ──────────────────────────────────────────────
# Keltner Channels & Squeeze Detection
# ──────────────────────────────────────────────
def calc_keltner_channels(
    df: pd.DataFrame,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 1.5,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Tính Keltner Channels để phát hiện Squeeze khi kết hợp với Bollinger Bands.
    """
    close = df["close"]
    ema = close.ewm(span=ema_period, adjust=False).mean()
    atr = calc_atr(df, period=atr_period)

    upper = ema + (atr * multiplier)
    lower = ema - (atr * multiplier)

    upper.name = "keltner_upper"
    ema.name = "keltner_middle"
    lower.name = "keltner_lower"
    return upper, ema, lower


# ──────────────────────────────────────────────
# Convenience: thêm tất cả indicators cơ bản
# ──────────────────────────────────────────────
def add_all_indicators(
    df: pd.DataFrame,
    ema_periods: list[int] | None = None,
    rsi_period: int = 14,
    atr_period: int = 14,
    include_regime_indicators: bool = True,
) -> pd.DataFrame:
    """
    Thêm tất cả indicators cơ bản và regime indicators vào DataFrame.

    Args:
        df: DataFrame gốc (OHLCV).
        ema_periods: Danh sách EMA periods. Mặc định: [20, 50, 200].
        rsi_period: RSI period. Mặc định: 14.
        atr_period: ATR period. Mặc định: 14.
        include_regime_indicators: Tính kèm ADX và Bollinger Bands.

    Returns:
        DataFrame mới với các indicators.
    """
    result = add_ema(df, periods=ema_periods)
    result = add_rsi(result, period=rsi_period)
    result = add_atr(result, period=atr_period)

    if include_regime_indicators and len(result) >= 20:
        result = add_adx(result, period=14)
        result = add_bollinger_bands(result, period=20, std_dev=2.0)

    log.info(
        "✓ Đã tính tất cả indicators trên %d bars (EMA %s, RSI(%d), ATR(%d), ADX/BB=%s)",
        len(df), ema_periods or [20, 50, 200], rsi_period, atr_period, include_regime_indicators,
    )
    return result
