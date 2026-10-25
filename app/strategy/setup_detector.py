# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Setup Detector.

Phát hiện setup giao dịch BUY/SELL dựa trên:
- Xu hướng (trend alignment).
- Cấu trúc thị trường (BOS/CHoCH).
- Chỉ báo kỹ thuật (EMA, RSI).
- Price action (nến xác nhận).

KHÔNG tự động đặt lệnh.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd
import numpy as np

from app.market.market_structure import (
    TrendDirection,
    SwingPoint,
    SwingType,
    StructureBreak,
    MarketStructureResult,
)
from app.market.volatility import VolatilityResult, VolatilityLevel
from logger import get_logger

log = get_logger("strategy.setup")


class SetupType(Enum):
    """Loại setup giao dịch."""
    TREND_CONTINUATION = "TREND_CONTINUATION"   # Tiếp diễn xu hướng
    BOS_RETEST = "BOS_RETEST"                   # Retest sau BOS
    STRUCTURE_BREAK = "STRUCTURE_BREAK"         # Phá vỡ cấu trúc
    EMA_BOUNCE = "EMA_BOUNCE"                   # Bật từ EMA
    RSI_DIVERGENCE = "RSI_DIVERGENCE"           # Phân kỳ RSI
    NO_SETUP = "NO_SETUP"                       # Không có setup


@dataclass
class SetupCandidate:
    """Một setup candidate (chưa qua filter)."""
    setup_type: SetupType
    direction: str          # "BUY" hoặc "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    reasons: list[str] = field(default_factory=list)
    score_components: dict[str, float] = field(default_factory=dict)
    invalidation: str = ""

    @property
    def sl_distance(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def tp_distance(self) -> float:
        return abs(self.take_profit - self.entry_price)

    @property
    def risk_reward(self) -> float:
        sl = self.sl_distance
        return self.tp_distance / sl if sl > 0 else 0.0


def detect_setups(
    df: pd.DataFrame,
    structure: MarketStructureResult,
    volatility: Optional[VolatilityResult] = None,
    higher_tf_trend: TrendDirection = TrendDirection.NEUTRAL,
    atr_value: float = 0.0,
) -> list[SetupCandidate]:
    """
    Phát hiện setup giao dịch.

    Quy trình:
    1. Kiểm tra trend alignment (H4 trend).
    2. Tìm setup dựa trên structure + indicators.
    3. Tính entry, SL, TP.
    4. Trả về danh sách candidates.

    Args:
        df: DataFrame OHLCV với indicators (EMA, RSI, ATR).
        structure: Kết quả phân tích market structure.
        volatility: Kết quả phân tích volatility.
        higher_tf_trend: Xu hướng timeframe cao hơn (H4).
        atr_value: Giá trị ATR hiện tại (dùng tính SL/TP).

    Returns:
        Danh sách SetupCandidate.
    """
    candidates: list[SetupCandidate] = []

    if df is None or len(df) < 20:
        return candidates

    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(last["close"])

    # Lấy giá trị indicators
    ema_20 = float(last.get("ema_20", 0))
    ema_50 = float(last.get("ema_50", 0))
    rsi = float(last.get("rsi_14", 50))

    if atr_value <= 0:
        atr_value = float(last.get("atr_14", 0))
    if atr_value <= 0:
        log.warning("ATR = 0, không thể tính SL/TP")
        return candidates

    trend = structure.trend

    # ── Setup 1: Trend Continuation (EMA Bounce) ──
    candidate = _check_ema_bounce(
        close, prev, ema_20, ema_50, rsi, trend, higher_tf_trend, atr_value
    )
    if candidate:
        candidates.append(candidate)

    # ── Setup 2: Structure Break (BOS) ──
    candidate = _check_bos_setup(
        close, structure, trend, higher_tf_trend, atr_value, rsi
    )
    if candidate:
        candidates.append(candidate)

    # ── Setup 3: RSI Extreme + Structure ──
    candidate = _check_rsi_extreme(
        close, rsi, trend, higher_tf_trend, atr_value, structure
    )
    if candidate:
        candidates.append(candidate)

    log.debug(
        "Phát hiện %d setup candidates (trend=%s, rsi=%.1f)",
        len(candidates), trend.value, rsi,
    )
    return candidates


def _check_ema_bounce(
    close: float,
    prev: pd.Series,
    ema_20: float,
    ema_50: float,
    rsi: float,
    trend: TrendDirection,
    higher_tf_trend: TrendDirection,
    atr: float,
) -> Optional[SetupCandidate]:
    """Kiểm tra setup EMA Bounce."""
    if ema_20 <= 0 or ema_50 <= 0:
        return None

    prev_close = float(prev["close"])
    reasons: list[str] = []

    # BUY: Trend bullish, giá chạm EMA20 từ trên, RSI không quá bán
    if (trend == TrendDirection.BULLISH
            and higher_tf_trend in (TrendDirection.BULLISH, TrendDirection.NEUTRAL)
            and close > ema_20
            and prev_close <= ema_20 * 1.002  # Vừa bounce
            and ema_20 > ema_50
            and 35 < rsi < 65):
        reasons = [
            "Bullish trend",
            "Giá bounce từ EMA20",
            "EMA20 > EMA50",
            f"RSI={rsi:.1f} (neutral zone)",
        ]
        return SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="BUY",
            entry_price=close,
            stop_loss=close - atr * 1.5,
            take_profit=close + atr * 2.5,
            reasons=reasons,
            score_components={"trend": 20, "ema": 20, "rsi": 15},
            invalidation=f"Close dưới EMA50 ({ema_50:.2f})",
        )

    # SELL: Trend bearish, giá chạm EMA20 từ dưới
    if (trend == TrendDirection.BEARISH
            and higher_tf_trend in (TrendDirection.BEARISH, TrendDirection.NEUTRAL)
            and close < ema_20
            and prev_close >= ema_20 * 0.998
            and ema_20 < ema_50
            and 35 < rsi < 65):
        reasons = [
            "Bearish trend",
            "Giá rejection từ EMA20",
            "EMA20 < EMA50",
            f"RSI={rsi:.1f} (neutral zone)",
        ]
        return SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="SELL",
            entry_price=close,
            stop_loss=close + atr * 1.5,
            take_profit=close - atr * 2.5,
            reasons=reasons,
            score_components={"trend": 20, "ema": 20, "rsi": 15},
            invalidation=f"Close trên EMA50 ({ema_50:.2f})",
        )

    return None


def _check_bos_setup(
    close: float,
    structure: MarketStructureResult,
    trend: TrendDirection,
    higher_tf_trend: TrendDirection,
    atr: float,
    rsi: float,
) -> Optional[SetupCandidate]:
    """Kiểm tra setup sau Break of Structure."""
    last_bos = structure.last_bos
    if last_bos is None:
        return None

    reasons: list[str] = []

    # BOS Bullish → tìm BUY retest
    if (last_bos.event_type == StructureBreak.BOS_BULLISH
            and higher_tf_trend in (TrendDirection.BULLISH, TrendDirection.NEUTRAL)
            and close >= last_bos.broken_level * 0.998  # Gần vùng phá vỡ
            and close <= last_bos.broken_level * 1.005
            and rsi < 70):
        reasons = [
            "BOS Bullish",
            f"Retest mức {last_bos.broken_level:.2f}",
            f"RSI={rsi:.1f}",
        ]
        # Tìm swing low gần nhất cho SL
        recent_lows = [s for s in structure.swings
                       if s.swing_type == SwingType.SWING_LOW]
        sl = recent_lows[-1].price - atr * 0.5 if recent_lows else close - atr * 2
        return SetupCandidate(
            setup_type=SetupType.BOS_RETEST,
            direction="BUY",
            entry_price=close,
            stop_loss=sl,
            take_profit=close + abs(close - sl) * 2,  # R:R = 1:2
            reasons=reasons,
            score_components={"bos": 25, "retest": 20, "trend": 15},
            invalidation=f"Close dưới {sl:.2f}",
        )

    # BOS Bearish → tìm SELL retest
    if (last_bos.event_type == StructureBreak.BOS_BEARISH
            and higher_tf_trend in (TrendDirection.BEARISH, TrendDirection.NEUTRAL)
            and close <= last_bos.broken_level * 1.002
            and close >= last_bos.broken_level * 0.995
            and rsi > 30):
        reasons = [
            "BOS Bearish",
            f"Retest mức {last_bos.broken_level:.2f}",
            f"RSI={rsi:.1f}",
        ]
        recent_highs = [s for s in structure.swings
                        if s.swing_type == SwingType.SWING_HIGH]
        sl = recent_highs[-1].price + atr * 0.5 if recent_highs else close + atr * 2
        return SetupCandidate(
            setup_type=SetupType.BOS_RETEST,
            direction="SELL",
            entry_price=close,
            stop_loss=sl,
            take_profit=close - abs(sl - close) * 2,
            reasons=reasons,
            score_components={"bos": 25, "retest": 20, "trend": 15},
            invalidation=f"Close trên {sl:.2f}",
        )

    return None


def _check_rsi_extreme(
    close: float,
    rsi: float,
    trend: TrendDirection,
    higher_tf_trend: TrendDirection,
    atr: float,
    structure: MarketStructureResult,
) -> Optional[SetupCandidate]:
    """Kiểm tra setup RSI extreme + structure support."""
    # BUY khi RSI oversold + bullish structure
    if (rsi < 30
            and trend != TrendDirection.BEARISH
            and higher_tf_trend != TrendDirection.BEARISH):
        # Tìm support gần nhất
        supports = [z for z in structure.sr_zones
                    if z.zone_type == "SUPPORT" and z.price < close]
        sl = supports[-1].price - atr * 0.3 if supports else close - atr * 2
        return SetupCandidate(
            setup_type=SetupType.RSI_DIVERGENCE,
            direction="BUY",
            entry_price=close,
            stop_loss=sl,
            take_profit=close + abs(close - sl) * 2,
            reasons=[
                f"RSI oversold ({rsi:.1f})",
                "Gần vùng support",
                "Trend không bearish",
            ],
            score_components={"rsi": 25, "support": 15, "trend": 10},
            invalidation=f"RSI tiếp tục giảm dưới 20 + close dưới {sl:.2f}",
        )

    # SELL khi RSI overbought + bearish structure
    if (rsi > 70
            and trend != TrendDirection.BULLISH
            and higher_tf_trend != TrendDirection.BULLISH):
        resistances = [z for z in structure.sr_zones
                       if z.zone_type == "RESISTANCE" and z.price > close]
        sl = resistances[0].price + atr * 0.3 if resistances else close + atr * 2
        return SetupCandidate(
            setup_type=SetupType.RSI_DIVERGENCE,
            direction="SELL",
            entry_price=close,
            stop_loss=sl,
            take_profit=close - abs(sl - close) * 2,
            reasons=[
                f"RSI overbought ({rsi:.1f})",
                "Gần vùng resistance",
                "Trend không bullish",
            ],
            score_components={"rsi": 25, "resistance": 15, "trend": 10},
            invalidation=f"RSI tiếp tục tăng trên 80 + close trên {sl:.2f}",
        )

    return None
