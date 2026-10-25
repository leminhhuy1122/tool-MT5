# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Setup Detector (SMC & Multi-Model Architecture).

Phát hiện setup giao dịch BUY/SELL dựa trên các phương pháp đọc biểu đồ tổ chức:
1. Smart Money Concepts (SMC):
   - Fair Value Gap (FVG / Imbalance Retest).
   - Order Block (OB Retest).
   - Liquidity Sweep (Săn thanh khoản / Stop Hunt / Fakeout).
2. Price Action & Market Structure:
   - Break of Structure (BOS Retest).
   - Change of Character (CHoCH Reversal).
3. Technical Confluence:
   - EMA Alignment & Bounce (EMA20/EMA50).
   - RSI Confluence (Neutral vs Extreme zones).

QUY TẮC QUẢN LÝ VỐN CHUẨN XAUUSD (VÀNG):
- Stop Loss: 10 giá hoặc hơn 1 xíu (10.0 - 12.0 giá) để bảo vệ vốn tối ưu.
- Take Profit 1 (TP1): 10.0 - 12.0 giá (R:R ~ 1:1) đảm bảo tỷ lệ ăn TP cực cao để khóa 50% lợi nhuận và dời SL về hòa vốn.
- Take Profit 2 (TP2): 20.0 - 24.0 giá (R:R ~ 1:2) tối ưu hóa lợi nhuận theo xu hướng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.market.market_structure import (
    MarketStructureResult,
    StructureBreak,
    StructureEvent,
    SwingPoint,
    SwingType,
    TrendDirection,
)
from app.market.smc import (
    FVGType,
    OBType,
    SweepType,
    detect_fvgs,
    detect_liquidity_sweeps,
    detect_order_blocks,
)
from app.market.volatility import VolatilityLevel, VolatilityResult
from logger import get_logger

log = get_logger("strategy.setup")


class SetupType(Enum):
    """Loại setup giao dịch."""
    TREND_CONTINUATION = "TREND_CONTINUATION"     # Tiếp diễn xu hướng
    BOS_RETEST = "BOS_RETEST"                     # Retest sau BOS
    STRUCTURE_BREAK = "STRUCTURE_BREAK"           # Phá vỡ cấu trúc
    EMA_BOUNCE = "EMA_BOUNCE"                     # Bật từ EMA
    RSI_DIVERGENCE = "RSI_DIVERGENCE"             # Phân kỳ RSI
    SMC_FVG_RETEST = "SMC_FVG_RETEST"             # Retest Fair Value Gap (SMC)
    SMC_ORDER_BLOCK = "SMC_ORDER_BLOCK"           # Retest Order Block (SMC)
    SMC_LIQUIDITY_SWEEP = "SMC_LIQUIDITY_SWEEP"   # Bẫy quét thanh khoản (SMC)
    NO_SETUP = "NO_SETUP"                         # Không có setup


@dataclass
class SetupCandidate:
    """Một setup candidate (chưa qua filter)."""
    setup_type: SetupType
    direction: str          # "BUY" hoặc "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    take_profit_1: Optional[float] = None
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
    def tp1(self) -> float:
        if self.take_profit_1 is not None and self.take_profit_1 > 0:
            return self.take_profit_1
        sl = self.sl_distance
        if self.direction.upper() == "BUY":
            return round(self.entry_price + sl, 2)
        return round(self.entry_price - sl, 2)

    @property
    def risk_reward(self) -> float:
        sl = self.sl_distance
        return self.tp_distance / sl if sl > 0 else 0.0


def compute_gold_sl_tp(
    direction: str,
    entry_price: float,
    structure_level: Optional[float] = None,
    atr: float = 0.0,
    target_sl_pts: float = 10.0,
    max_sl_pts: float = 12.0,
) -> Tuple[float, float, float]:
    """
    Tính Stop Loss và Take Profit chuẩn xác cho Vàng XAUUSD:
    - SL: Luôn duy trì 10 giá hoặc hơn 1 xíu (10.0 - 12.0 giá) để bảo toàn vốn tối ưu.
    - TP1: 10.0 - 12.0 giá (R:R ~ 1:1) đảm bảo tỷ lệ chạm TP cực cao để khóa lợi nhuận và dời SL về hòa vốn.
    - TP2: 20.0 - 24.0 giá (R:R ~ 1:2) tối ưu hóa lợi nhuận theo xu hướng.
    """
    dir_upper = direction.upper()
    if dir_upper == "BUY":
        if structure_level is not None and structure_level < entry_price:
            raw_dist = (entry_price - structure_level) + 1.0  # Đặt dưới đáy + 1 giá đệm
            sl_dist = max(target_sl_pts, min(raw_dist, max_sl_pts))
        else:
            sl_dist = target_sl_pts

        sl = round(entry_price - sl_dist, 2)
        tp1 = round(entry_price + sl_dist, 2)          # TP1 = +10..12 giá
        tp2 = round(entry_price + (sl_dist * 2.0), 2)  # TP2 = +20..24 giá
        return sl, tp1, tp2

    else:  # SELL
        if structure_level is not None and structure_level > entry_price:
            raw_dist = (structure_level - entry_price) + 1.0  # Đặt trên đỉnh + 1 giá đệm
            sl_dist = max(target_sl_pts, min(raw_dist, max_sl_pts))
        else:
            sl_dist = target_sl_pts

        sl = round(entry_price + sl_dist, 2)
        tp1 = round(entry_price - sl_dist, 2)          # TP1 = -10..12 giá
        tp2 = round(entry_price - (sl_dist * 2.0), 2)  # TP2 = -20..24 giá
        return sl, tp1, tp2


def detect_setups(
    df: pd.DataFrame,
    structure: MarketStructureResult,
    volatility: Optional[VolatilityResult] = None,
    higher_tf_trend: TrendDirection = TrendDirection.NEUTRAL,
    atr_value: float = 0.0,
) -> list[SetupCandidate]:
    """
    Phát hiện toàn diện các setup giao dịch theo chuẩn SMC & Price Action.

    Quy trình:
    1. Kiểm tra đủ dữ liệu tối thiểu.
    2. Quét các setup Smart Money: Liquidity Sweep, FVG Retest, Order Block.
    3. Quét các setup Cấu trúc & Kỹ thuật: BOS Retest, EMA Bounce, RSI Extreme.
    4. Chuẩn hóa SL 10 giá hoặc hơn 1 xíu (10.0 - 12.0 giá) và TP đa tầng.
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

    # ── 1. SMC Setup: Liquidity Sweep (Ưu tiên số 1 - Tỷ lệ thắng cao nhất) ──
    cand_sweep = _check_smc_liquidity_sweep(close, df, structure, higher_tf_trend, atr_value)
    if cand_sweep:
        candidates.append(cand_sweep)

    # ── 2. SMC Setup: Fair Value Gap (FVG / Imbalance Retest) ──
    cand_fvg = _check_smc_fvg_retest(close, df, structure, higher_tf_trend, atr_value, rsi)
    if cand_fvg:
        candidates.append(cand_fvg)

    # ── 3. SMC Setup: Order Block (OB Retest) ──
    cand_ob = _check_smc_order_block(close, df, structure, higher_tf_trend, atr_value, rsi)
    if cand_ob:
        candidates.append(cand_ob)

    # ── 4. Structure Setup: Break of Structure (BOS Retest) ──
    cand_bos = _check_bos_setup(close, structure, trend, higher_tf_trend, atr_value, rsi)
    if cand_bos:
        candidates.append(cand_bos)

    # ── 5. Trend Setup: EMA Bounce (Tiếp diễn xu hướng) ──
    cand_ema = _check_ema_bounce(close, prev, ema_20, ema_50, rsi, trend, higher_tf_trend, atr_value)
    if cand_ema:
        candidates.append(cand_ema)

    # ── 6. Reversal Setup: RSI Extreme + Structure ──
    cand_rsi = _check_rsi_extreme(close, rsi, trend, higher_tf_trend, atr_value, structure)
    if cand_rsi:
        candidates.append(cand_rsi)

    log.debug(
        "Phát hiện %d setup candidates (trend=%s, rsi=%.1f)",
        len(candidates), trend.value, rsi,
    )
    return candidates


# ──────────────────────────────────────────────
# Chi tiết các bộ phát hiện Setup
# ──────────────────────────────────────────────
def _check_smc_liquidity_sweep(
    close: float,
    df: pd.DataFrame,
    structure: MarketStructureResult,
    higher_tf_trend: TrendDirection,
    atr: float,
) -> Optional[SetupCandidate]:
    """SMC Setup: Săn thanh khoản / Bẫy giá (Liquidity Sweep)."""
    if len(df) < 5 or not structure.swings:
        return None

    sweeps = detect_liquidity_sweeps(df, structure.swings, lookback_bars=3)
    if not sweeps:
        return None

    recent_sweep = sweeps[-1]

    # BSL Sweep (Quét đỉnh) -> SELL
    if recent_sweep.sweep_type == SweepType.BSL_SWEEP:
        if higher_tf_trend != TrendDirection.BULLISH or recent_sweep.wick_distance >= 0.6:
            sl, tp1, tp2 = compute_gold_sl_tp("SELL", close, structure_level=recent_sweep.extreme_price, atr=atr)
            reasons = [
                f"SMC: Quét thanh khoản đỉnh (BSL Sweep) mức {recent_sweep.swept_level:.2f}",
                f"Râu nến từ chối giá {recent_sweep.extreme_price:.2f} (wick={recent_sweep.wick_distance:.1f} giá)",
                "Bẫy thanh khoản hoàn tất -> Kỳ vọng đảo chiều giảm",
            ]
            return SetupCandidate(
                setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
                direction="SELL",
                entry_price=close,
                stop_loss=sl,
                take_profit=tp2,
                take_profit_1=tp1,
                reasons=reasons,
                score_components={"liquidity_sweep": 30, "price_action": 20, "trend": 15},
                invalidation=f"Close vượt đỉnh quét {recent_sweep.extreme_price:.2f}",
            )

    # SSL Sweep (Quét đáy) -> BUY
    elif recent_sweep.sweep_type == SweepType.SSL_SWEEP:
        if higher_tf_trend != TrendDirection.BEARISH or recent_sweep.wick_distance >= 0.6:
            sl, tp1, tp2 = compute_gold_sl_tp("BUY", close, structure_level=recent_sweep.extreme_price, atr=atr)
            reasons = [
                f"SMC: Quét thanh khoản đáy (SSL Sweep) mức {recent_sweep.swept_level:.2f}",
                f"Râu nến rút chân từ {recent_sweep.extreme_price:.2f} (wick={recent_sweep.wick_distance:.1f} giá)",
                "Bẫy thanh khoản hoàn tất -> Kỳ vọng đảo chiều tăng",
            ]
            return SetupCandidate(
                setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
                direction="BUY",
                entry_price=close,
                stop_loss=sl,
                take_profit=tp2,
                take_profit_1=tp1,
                reasons=reasons,
                score_components={"liquidity_sweep": 30, "price_action": 20, "trend": 15},
                invalidation=f"Close thủng đáy quét {recent_sweep.extreme_price:.2f}",
            )

    return None


def _check_smc_fvg_retest(
    close: float,
    df: pd.DataFrame,
    structure: MarketStructureResult,
    higher_tf_trend: TrendDirection,
    atr: float,
    rsi: float,
) -> Optional[SetupCandidate]:
    """SMC Setup: Retest Fair Value Gap (Khoảng trống giá)."""
    fvgs = detect_fvgs(df)
    active_fvgs = [f for f in fvgs if not f.is_mitigated and (len(df) - 1 - f.index) <= 25]
    if not active_fvgs:
        return None

    active_fvgs.sort(key=lambda x: x.index, reverse=True)

    # 1. Bullish FVG
    bull_fvgs = [f for f in active_fvgs if f.fvg_type == FVGType.BULLISH]
    for fvg in bull_fvgs:
        if (fvg.bottom * 0.999 <= close <= fvg.top * 1.002
                and structure.trend != TrendDirection.BEARISH
                and higher_tf_trend != TrendDirection.BEARISH
                and rsi < 65):
            sl, tp1, tp2 = compute_gold_sl_tp("BUY", close, structure_level=fvg.bottom, atr=atr)
            reasons = [
                f"SMC: Retest Bullish FVG [{fvg.bottom:.2f} - {fvg.top:.2f}]",
                f"Độ rộng Imbalance={fvg.size:.1f} giá | Mức CE={fvg.midpoint:.2f}",
                f"Hợp lưu xu hướng ({structure.trend.value}) & RSI={rsi:.1f}",
            ]
            return SetupCandidate(
                setup_type=SetupType.SMC_FVG_RETEST,
                direction="BUY",
                entry_price=close,
                stop_loss=sl,
                take_profit=tp2,
                take_profit_1=tp1,
                reasons=reasons,
                score_components={"fvg": 30, "trend": 20, "confluence": 15},
                invalidation=f"Close thủng đáy FVG {fvg.bottom:.2f}",
            )

    # 2. Bearish FVG
    bear_fvgs = [f for f in active_fvgs if f.fvg_type == FVGType.BEARISH]
    for fvg in bear_fvgs:
        if (fvg.bottom * 0.998 <= close <= fvg.top * 1.001
                and structure.trend != TrendDirection.BULLISH
                and higher_tf_trend != TrendDirection.BULLISH
                and rsi > 35):
            sl, tp1, tp2 = compute_gold_sl_tp("SELL", close, structure_level=fvg.top, atr=atr)
            reasons = [
                f"SMC: Retest Bearish FVG [{fvg.bottom:.2f} - {fvg.top:.2f}]",
                f"Độ rộng Imbalance={fvg.size:.1f} giá | Mức CE={fvg.midpoint:.2f}",
                f"Hợp lưu xu hướng ({structure.trend.value}) & RSI={rsi:.1f}",
            ]
            return SetupCandidate(
                setup_type=SetupType.SMC_FVG_RETEST,
                direction="SELL",
                entry_price=close,
                stop_loss=sl,
                take_profit=tp2,
                take_profit_1=tp1,
                reasons=reasons,
                score_components={"fvg": 30, "trend": 20, "confluence": 15},
                invalidation=f"Close vượt đỉnh FVG {fvg.top:.2f}",
            )

    return None


def _check_smc_order_block(
    close: float,
    df: pd.DataFrame,
    structure: MarketStructureResult,
    higher_tf_trend: TrendDirection,
    atr: float,
    rsi: float,
) -> Optional[SetupCandidate]:
    """SMC Setup: Retest Order Block (Khối lệnh tổ chức)."""
    obs = detect_order_blocks(df, lookback_bars=40)
    active_obs = [ob for ob in obs if not ob.is_mitigated and (len(df) - 1 - ob.index) <= 30]
    if not active_obs:
        return None

    active_obs.sort(key=lambda x: x.index, reverse=True)

    # Bullish Order Block
    for ob in [o for o in active_obs if o.ob_type == OBType.BULLISH]:
        if (ob.low * 0.999 <= close <= ob.high * 1.002
                and structure.trend != TrendDirection.BEARISH
                and higher_tf_trend != TrendDirection.BEARISH
                and rsi < 65):
            sl, tp1, tp2 = compute_gold_sl_tp("BUY", close, structure_level=ob.low, atr=atr)
            reasons = [
                f"SMC: Chạm vùng Bullish Order Block [{ob.low:.2f} - {ob.high:.2f}]",
                "Khối lệnh tổ chức mua phòng thủ",
                f"RSI={rsi:.1f}",
            ]
            return SetupCandidate(
                setup_type=SetupType.SMC_ORDER_BLOCK,
                direction="BUY",
                entry_price=close,
                stop_loss=sl,
                take_profit=tp2,
                take_profit_1=tp1,
                reasons=reasons,
                score_components={"order_block": 30, "structure": 20, "trend": 15},
                invalidation=f"Close thủng đáy Order Block {ob.low:.2f}",
            )

    # Bearish Order Block
    for ob in [o for o in active_obs if o.ob_type == OBType.BEARISH]:
        if (ob.low * 0.998 <= close <= ob.high * 1.001
                and structure.trend != TrendDirection.BULLISH
                and higher_tf_trend != TrendDirection.BULLISH
                and rsi > 35):
            sl, tp1, tp2 = compute_gold_sl_tp("SELL", close, structure_level=ob.high, atr=atr)
            reasons = [
                f"SMC: Chạm vùng Bearish Order Block [{ob.low:.2f} - {ob.high:.2f}]",
                "Khối lệnh tổ chức bán phân phối",
                f"RSI={rsi:.1f}",
            ]
            return SetupCandidate(
                setup_type=SetupType.SMC_ORDER_BLOCK,
                direction="SELL",
                entry_price=close,
                stop_loss=sl,
                take_profit=tp2,
                take_profit_1=tp1,
                reasons=reasons,
                score_components={"order_block": 30, "structure": 20, "trend": 15},
                invalidation=f"Close vượt đỉnh Order Block {ob.high:.2f}",
            )

    return None


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
    """Kiểm tra setup EMA Bounce chuẩn hóa SL 10-12 giá."""
    if ema_20 <= 0 or ema_50 <= 0:
        return None

    prev_close = float(prev["close"])

    # BUY: Trend bullish, giá chạm EMA20 từ trên
    if (trend == TrendDirection.BULLISH
            and higher_tf_trend in (TrendDirection.BULLISH, TrendDirection.NEUTRAL)
            and close > ema_20
            and prev_close <= ema_20 * 1.002
            and ema_20 > ema_50
            and 35 < rsi < 65):
        sl, tp1, tp2 = compute_gold_sl_tp("BUY", close, structure_level=ema_50, atr=atr)
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
            stop_loss=sl,
            take_profit=tp2,
            take_profit_1=tp1,
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
        sl, tp1, tp2 = compute_gold_sl_tp("SELL", close, structure_level=ema_50, atr=atr)
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
            stop_loss=sl,
            take_profit=tp2,
            take_profit_1=tp1,
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
    """Kiểm tra setup sau Break of Structure chuẩn hóa SL 10-12 giá."""
    last_bos = structure.last_bos
    if last_bos is None:
        return None

    # BOS Bullish → tìm BUY retest
    if (last_bos.event_type == StructureBreak.BOS_BULLISH
            and higher_tf_trend in (TrendDirection.BULLISH, TrendDirection.NEUTRAL)
            and close >= last_bos.broken_level * 0.998
            and close <= last_bos.broken_level * 1.005
            and rsi < 70):
        recent_lows = [s for s in structure.swings if s.swing_type == SwingType.SWING_LOW]
        ref_low = recent_lows[-1].price if recent_lows else last_bos.broken_level - 5.0
        sl, tp1, tp2 = compute_gold_sl_tp("BUY", close, structure_level=ref_low, atr=atr)
        reasons = [
            "BOS Bullish",
            f"Retest mức {last_bos.broken_level:.2f}",
            f"RSI={rsi:.1f}",
        ]
        return SetupCandidate(
            setup_type=SetupType.BOS_RETEST,
            direction="BUY",
            entry_price=close,
            stop_loss=sl,
            take_profit=tp2,
            take_profit_1=tp1,
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
        recent_highs = [s for s in structure.swings if s.swing_type == SwingType.SWING_HIGH]
        ref_high = recent_highs[-1].price if recent_highs else last_bos.broken_level + 5.0
        sl, tp1, tp2 = compute_gold_sl_tp("SELL", close, structure_level=ref_high, atr=atr)
        reasons = [
            "BOS Bearish",
            f"Retest mức {last_bos.broken_level:.2f}",
            f"RSI={rsi:.1f}",
        ]
        return SetupCandidate(
            setup_type=SetupType.BOS_RETEST,
            direction="SELL",
            entry_price=close,
            stop_loss=sl,
            take_profit=tp2,
            take_profit_1=tp1,
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
    """Kiểm tra setup RSI extreme + structure support/resistance."""
    # BUY khi RSI oversold + bullish structure
    if (rsi < 30
            and trend != TrendDirection.BEARISH
            and higher_tf_trend != TrendDirection.BEARISH):
        supports = [z for z in structure.sr_zones if z.zone_type == "SUPPORT" and z.price < close]
        ref_support = supports[-1].price if supports else None
        sl, tp1, tp2 = compute_gold_sl_tp("BUY", close, structure_level=ref_support, atr=atr)
        return SetupCandidate(
            setup_type=SetupType.RSI_DIVERGENCE,
            direction="BUY",
            entry_price=close,
            stop_loss=sl,
            take_profit=tp2,
            take_profit_1=tp1,
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
        resistances = [z for z in structure.sr_zones if z.zone_type == "RESISTANCE" and z.price > close]
        ref_resistance = resistances[0].price if resistances else None
        sl, tp1, tp2 = compute_gold_sl_tp("SELL", close, structure_level=ref_resistance, atr=atr)
        return SetupCandidate(
            setup_type=SetupType.RSI_DIVERGENCE,
            direction="SELL",
            entry_price=close,
            stop_loss=sl,
            take_profit=tp2,
            take_profit_1=tp1,
            reasons=[
                f"RSI overbought ({rsi:.1f})",
                "Gần vùng resistance",
                "Trend không bullish",
            ],
            score_components={"rsi": 25, "resistance": 15, "trend": 10},
            invalidation=f"RSI tiếp tục tăng trên 80 + close trên {sl:.2f}",
        )

    return None
