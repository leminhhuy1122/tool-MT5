# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Smart Money Concepts (SMC) & Institutional Chart Reading.

Mô-đun tổng hợp kiến thức đọc biểu đồ tài chính chuyên sâu:
1. Fair Value Gap (FVG / Imbalance):
   - Nhận diện khoảng trống thanh khoản do lệnh thị trường lớn của các tổ chức (Institutions/Banks).
   - Bullish FVG: Low của nến 3 cao hơn High của nến 1.
   - Bearish FVG: High của nến 3 thấp hơn Low của nến 1.
   - Theo dõi trạng thái Unmitigated (chưa lấp) để bắt nhịp Retest/Mitigation.

2. Order Block (OB - Khối lệnh của cá mập):
   - Bullish OB: Cây nến giảm cuối cùng trước đợt tăng vọt phá vỡ cấu trúc và tạo FVG.
   - Bearish OB: Cây nến tăng cuối cùng trước đợt giảm mạnh phá vỡ cấu trúc và tạo FVG.
   - Vùng phản ứng giá có độ tin cậy và R:R cao nhất.

3. Liquidity Sweep (Săn thanh khoản / Bẫy giá / Stop Hunt):
   - Buy-Side Liquidity (BSL) Sweep: Quét đỉnh cũ dụ Buy Breakout, quét SL Seller rồi rút râu đảo chiều giảm.
   - Sell-Side Liquidity (SSL) Sweep: Quét đáy cũ dụ Sell Breakdown, quét SL Buyer rồi rút chân nến đảo chiều tăng.

4. Discount vs Premium Zones (Vùng giá rẻ & đắt theo Fibonacci 50%):
   - Equilibrium (50% Range): Mức giá trị hợp lý.
   - Discount Zone (< 50%): Vùng gom mua giá rẻ (Smart Money Buy).
   - Premium Zone (> 50%): Vùng phân phối giá cao (Smart Money Sell).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.market.market_structure import SwingPoint, SwingType
from logger import get_logger

log = get_logger("market.smc")


class FVGType(Enum):
    """Loại Fair Value Gap."""
    BULLISH = "BULLISH_FVG"
    BEARISH = "BEARISH_FVG"


class OBType(Enum):
    """Loại Order Block."""
    BULLISH = "BULLISH_OB"
    BEARISH = "BEARISH_OB"


class SweepType(Enum):
    """Loại bẫy quét thanh khoản."""
    BSL_SWEEP = "BSL_SWEEP"  # Quét đỉnh (Buy-side Liquidity)
    SSL_SWEEP = "SSL_SWEEP"  # Quét đáy (Sell-side Liquidity)


@dataclass
class FairValueGap:
    """Mô hình khoảng trống thanh khoản FVG."""
    index: int                  # Bar index nến giữa (nến bứt phá)
    fvg_type: FVGType
    top: float                  # Biên trên của gap
    bottom: float               # Biên dưới của gap
    size: float                 # Độ rộng gap (giá)
    is_mitigated: bool = False  # Đã bị giá hồi về lấp hay chưa
    mitigated_bar_index: Optional[int] = None
    time: Optional[pd.Timestamp] = None

    @property
    def midpoint(self) -> float:
        """Mức Consequent Encroachment (CE - 50% FVG)."""
        return round((self.top + self.bottom) / 2.0, 2)


@dataclass
class OrderBlock:
    """Khối lệnh tổ chức (Order Block)."""
    index: int                  # Bar index của nến OB
    ob_type: OBType
    high: float                 # Biên trên OB
    low: float                  # Biên dưới OB
    open_price: float
    close_price: float
    volume: float = 0.0
    has_fvg: bool = False       # Có FVG đi kèm đợt bứt phá hay không
    is_mitigated: bool = False  # Đã bị test lại hay chưa
    time: Optional[pd.Timestamp] = None

    @property
    def midpoint(self) -> float:
        """Mức 50% của Order Block."""
        return round((self.high + self.low) / 2.0, 2)


@dataclass
class LiquiditySweep:
    """Sự kiện quét thanh khoản / Stop Hunt."""
    index: int                  # Bar index xảy ra quét
    sweep_type: SweepType
    swept_level: float          # Mức đỉnh/đáy cũ bị quét qua
    extreme_price: float        # Đỉnh cao nhất hoặc đáy thấp nhất của râu nến quét
    close_price: float          # Giá đóng nến xác nhận rút chân
    wick_distance: float        # Độ sâu của nhịp quét (giá)
    time: Optional[pd.Timestamp] = None


@dataclass
class PriceZone:
    """Định giá Discount / Premium."""
    range_high: float
    range_low: float
    equilibrium: float          # 50% mức cân bằng
    current_price: float
    zone: str                   # "DISCOUNT", "PREMIUM", hoặc "EQUILIBRIUM"
    percent_in_range: float     # 0.0% -> 100.0%


@dataclass
class SMCAnalysisResult:
    """Kết quả phân tích toàn diện Smart Money Concepts."""
    fvgs: List[FairValueGap] = field(default_factory=list)
    unmitigated_fvgs: List[FairValueGap] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    unmitigated_obs: List[OrderBlock] = field(default_factory=list)
    liquidity_sweeps: List[LiquiditySweep] = field(default_factory=list)
    price_zone: Optional[PriceZone] = None


# ──────────────────────────────────────────────
# 1. Phát hiện Fair Value Gap (FVG)
# ──────────────────────────────────────────────
def detect_fvgs(df: pd.DataFrame, min_gap_pts: float = 0.6) -> List[FairValueGap]:
    """
    Phát hiện các khoảng trống Fair Value Gap (FVG) trên chuỗi nến.
    Một FVG gồm 3 nến liên tiếp:
    - Bullish FVG: nến 1 có High < nến 3 có Low -> Khoảng trống giữa High[i-1] và Low[i+1].
    - Bearish FVG: nến 1 có Low > nến 3 có High -> Khoảng trống giữa Low[i-1] và High[i+1].
    """
    if df is None or len(df) < 3:
        return []

    highs = df["high"].values
    lows = df["low"].values
    times = df["time"].values if "time" in df.columns else [None] * len(df)
    n = len(df)

    fvgs: List[FairValueGap] = []

    for i in range(1, n - 1):
        # 1. Bullish FVG
        h_prev = float(highs[i - 1])
        l_next = float(lows[i + 1])
        if l_next > h_prev:
            gap_size = round(l_next - h_prev, 2)
            if gap_size >= min_gap_pts:
                # Kiểm tra xem các nến sau có lấp gap này chưa
                mitigated = False
                mitigated_idx = None
                for j in range(i + 2, n):
                    if lows[j] <= h_prev:  # Đã lấp hoàn toàn
                        mitigated = True
                        mitigated_idx = j
                        break

                fvgs.append(FairValueGap(
                    index=i,
                    fvg_type=FVGType.BULLISH,
                    top=round(l_next, 2),
                    bottom=round(h_prev, 2),
                    size=gap_size,
                    is_mitigated=mitigated,
                    mitigated_bar_index=mitigated_idx,
                    time=times[i],
                ))

        # 2. Bearish FVG
        l_prev = float(lows[i - 1])
        h_next = float(highs[i + 1])
        if h_next < l_prev:
            gap_size = round(l_prev - h_next, 2)
            if gap_size >= min_gap_pts:
                mitigated = False
                mitigated_idx = None
                for j in range(i + 2, n):
                    if highs[j] >= l_prev:  # Đã lấp hoàn toàn
                        mitigated = True
                        mitigated_idx = j
                        break

                fvgs.append(FairValueGap(
                    index=i,
                    fvg_type=FVGType.BEARISH,
                    top=round(l_prev, 2),
                    bottom=round(h_next, 2),
                    size=gap_size,
                    is_mitigated=mitigated,
                    mitigated_bar_index=mitigated_idx,
                    time=times[i],
                ))

    return fvgs


# ──────────────────────────────────────────────
# 2. Phát hiện Order Block (OB)
# ──────────────────────────────────────────────
def detect_order_blocks(
    df: pd.DataFrame,
    fvgs: Optional[List[FairValueGap]] = None,
    lookback_bars: int = 50,
) -> List[OrderBlock]:
    """
    Phát hiện các khối Order Block của dòng tiền thông minh:
    - Bullish OB: Nến đỏ (bearish) cuối cùng trước một chuỗi nến tăng mạnh tạo FVG hoặc phá vỡ biên.
    - Bearish OB: Nến xanh (bullish) cuối cùng trước một chuỗi nến giảm mạnh tạo FVG hoặc phá vỡ biên.
    """
    if df is None or len(df) < 5:
        return []

    if fvgs is None:
        fvgs = detect_fvgs(df)

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df["time"].values if "time" in df.columns else [None] * len(df)
    n = len(df)
    start_idx = max(2, n - lookback_bars)

    fvg_indices = {f.index: f for f in fvgs}
    order_blocks: List[OrderBlock] = []

    for i in range(start_idx, n - 2):
        o = float(opens[i])
        c = float(closes[i])
        h = float(highs[i])
        l = float(lows[i])

        # 1. Bullish Order Block (nến giảm trước đợt tăng mạnh)
        if c < o:  # Nến giảm
            # Kiểm tra 2 nến tiếp theo có tạo đợt tăng mạnh và có FVG hay không
            next_close_1 = float(closes[i + 1])
            next_close_2 = float(closes[i + 2])
            has_momentum = (next_close_1 > h) or (next_close_2 > h + (h - l) * 0.8)
            has_fvg = (i + 1 in fvg_indices and fvg_indices[i + 1].fvg_type == FVGType.BULLISH)

            if has_momentum or has_fvg:
                # Kiểm tra nến sau có phá vỡ hay đã test lại
                mitigated = False
                for k in range(i + 2, n):
                    if lows[k] < l:  # Giá đâm xuyên qua đáy OB -> Bị vô hiệu hóa
                        mitigated = True
                        break

                order_blocks.append(OrderBlock(
                    index=i,
                    ob_type=OBType.BULLISH,
                    high=round(h, 2),
                    low=round(l, 2),
                    open_price=round(o, 2),
                    close_price=round(c, 2),
                    has_fvg=has_fvg,
                    is_mitigated=mitigated,
                    time=times[i],
                ))

        # 2. Bearish Order Block (nến tăng trước đợt giảm mạnh)
        elif c > o:  # Nến tăng
            next_close_1 = float(closes[i + 1])
            next_close_2 = float(closes[i + 2])
            has_momentum = (next_close_1 < l) or (next_close_2 < l - (h - l) * 0.8)
            has_fvg = (i + 1 in fvg_indices and fvg_indices[i + 1].fvg_type == FVGType.BEARISH)

            if has_momentum or has_fvg:
                mitigated = False
                for k in range(i + 2, n):
                    if highs[k] > h:  # Giá đâm thủng đỉnh OB -> Bị vô hiệu hóa
                        mitigated = True
                        break

                order_blocks.append(OrderBlock(
                    index=i,
                    ob_type=OBType.BEARISH,
                    high=round(h, 2),
                    low=round(l, 2),
                    open_price=round(o, 2),
                    close_price=round(c, 2),
                    has_fvg=has_fvg,
                    is_mitigated=mitigated,
                    time=times[i],
                ))

    return order_blocks


# ──────────────────────────────────────────────
# 3. Phát hiện Liquidity Sweep (Săn thanh khoản / Bẫy giá)
# ──────────────────────────────────────────────
def detect_liquidity_sweeps(
    df: pd.DataFrame,
    swings: List[SwingPoint],
    lookback_bars: int = 40,
) -> List[LiquiditySweep]:
    """
    Phát hiện các nhịp quét râu thanh khoản (Stop Hunt / Fakeout):
    - BSL Sweep: Râu nến High đâm qua Swing High trước đó, nhưng giá Close đóng cửa trở lại dưới Swing High.
    - SSL Sweep: Râu nến Low đâm qua Swing Low trước đó, nhưng giá Close đóng cửa trở lại trên Swing Low.
    """
    if df is None or len(df) < 10 or not swings:
        return []

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df["time"].values if "time" in df.columns else [None] * len(df)
    n = len(df)

    sweeps: List[LiquiditySweep] = []
    swing_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
    swing_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]

    start_bar = max(0, n - lookback_bars)

    for bar_idx in range(start_bar, n):
        h = float(highs[bar_idx])
        l = float(lows[bar_idx])
        c = float(closes[bar_idx])

        # 1. Kiểm tra quét đỉnh BSL (Buy-Side Liquidity)
        for sh in swing_highs:
            if sh.index < bar_idx and (bar_idx - sh.index) <= 60:
                if h > sh.price and c < sh.price:
                    # Đã quét qua đỉnh nhưng đóng nến rút râu dưới đỉnh
                    wick = round(h - sh.price, 2)
                    if wick >= 0.3:
                        sweeps.append(LiquiditySweep(
                            index=bar_idx,
                            sweep_type=SweepType.BSL_SWEEP,
                            swept_level=round(sh.price, 2),
                            extreme_price=round(h, 2),
                            close_price=round(c, 2),
                            wick_distance=wick,
                            time=times[bar_idx],
                        ))
                        break

        # 2. Kiểm tra quét đáy SSL (Sell-Side Liquidity)
        for sl in swing_lows:
            if sl.index < bar_idx and (bar_idx - sl.index) <= 60:
                if l < sl.price and c > sl.price:
                    # Đã quét qua đáy nhưng đóng nến rút chân trên đáy
                    wick = round(sl.price - l, 2)
                    if wick >= 0.3:
                        sweeps.append(LiquiditySweep(
                            index=bar_idx,
                            sweep_type=SweepType.SSL_SWEEP,
                            swept_level=round(sl.price, 2),
                            extreme_price=round(l, 2),
                            close_price=round(c, 2),
                            wick_distance=wick,
                            time=times[bar_idx],
                        ))
                        break

    return sweeps


# ──────────────────────────────────────────────
# 4. Định giá Vùng Discount & Premium (Equilibrium 50%)
# ──────────────────────────────────────────────
def calculate_discount_premium(
    df: pd.DataFrame,
    swings: Optional[List[SwingPoint]] = None,
    lookback_bars: int = 50,
) -> Optional[PriceZone]:
    """
    Xác định vùng giá hiện tại là DISCOUNT (<50%) hay PREMIUM (>50%):
    - Dựa trên biên dao động Swing High - Swing Low gần nhất (hoặc Min/Max nến gần nhất).
    - Quy tắc SMC: Chỉ BUY ở Discount, Chỉ SELL ở Premium.
    """
    if df is None or len(df) < 10:
        return None

    recent_df = df.iloc[-lookback_bars:] if len(df) > lookback_bars else df
    current_price = float(df["close"].iloc[-1])

    if swings and len(swings) >= 2:
        recent_sh = [s.price for s in swings if s.swing_type == SwingType.SWING_HIGH][-3:]
        recent_sl = [s.price for s in swings if s.swing_type == SwingType.SWING_LOW][-3:]
        range_high = max(recent_sh) if recent_sh else float(recent_df["high"].max())
        range_low = min(recent_sl) if recent_sl else float(recent_df["low"].min())
    else:
        range_high = float(recent_df["high"].max())
        range_low = float(recent_df["low"].min())

    if range_high <= range_low:
        return None

    range_span = range_high - range_low
    equilibrium = round((range_high + range_low) / 2.0, 2)
    pct = round(((current_price - range_low) / range_span) * 100.0, 1)

    if pct < 45.0:
        zone = "DISCOUNT"
    elif pct > 55.0:
        zone = "PREMIUM"
    else:
        zone = "EQUILIBRIUM"

    return PriceZone(
        range_high=round(range_high, 2),
        range_low=round(range_low, 2),
        equilibrium=equilibrium,
        current_price=round(current_price, 2),
        zone=zone,
        percent_in_range=pct,
    )


# ──────────────────────────────────────────────
# 5. Phân tích SMC tổng hợp (Facade)
# ──────────────────────────────────────────────
def analyze_smc(
    df: pd.DataFrame,
    swings: Optional[List[SwingPoint]] = None,
) -> SMCAnalysisResult:
    """Thực hiện trọn gói phân tích Smart Money Concepts cho DataFrame nến."""
    fvgs = detect_fvgs(df)
    unmitigated_fvgs = [f for f in fvgs if not f.is_mitigated]

    obs = detect_order_blocks(df, fvgs=fvgs)
    unmitigated_obs = [ob for ob in obs if not ob.is_mitigated]

    sweeps = detect_liquidity_sweeps(df, swings=swings or []) if swings else []
    zone = calculate_discount_premium(df, swings=swings)

    log.debug(
        "✓ SMC: %d FVGs (%d active), %d OBs (%d active), %d Sweeps, Zone=%s",
        len(fvgs), len(unmitigated_fvgs),
        len(obs), len(unmitigated_obs),
        len(sweeps), zone.zone if zone else "None"
    )

    return SMCAnalysisResult(
        fvgs=fvgs,
        unmitigated_fvgs=unmitigated_fvgs,
        order_blocks=obs,
        unmitigated_obs=unmitigated_obs,
        liquidity_sweeps=sweeps,
        price_zone=zone,
    )
