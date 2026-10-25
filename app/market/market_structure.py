# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Market Structure Analysis.

Phân tích cấu trúc thị trường:
- Swing High / Swing Low detection.
- Higher High (HH), Higher Low (HL), Lower High (LH), Lower Low (LL).
- Break of Structure (BOS).
- Change of Character (CHoCH).
- Support / Resistance zones.

Quy tắc:
- Không sử dụng dữ liệu tương lai.
- Chỉ xác nhận swing khi đã có đủ nến sau để confirm.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd
import numpy as np

from logger import get_logger

log = get_logger("market.structure")


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────
class TrendDirection(Enum):
    """Hướng xu hướng."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SwingType(Enum):
    """Loại swing point."""
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"


class StructureBreak(Enum):
    """Loại phá vỡ cấu trúc."""
    BOS_BULLISH = "BOS_BULLISH"      # Break of Structure lên
    BOS_BEARISH = "BOS_BEARISH"      # Break of Structure xuống
    CHOCH_BULLISH = "CHOCH_BULLISH"  # Change of Character lên
    CHOCH_BEARISH = "CHOCH_BEARISH"  # Change of Character xuống


# ──────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────
@dataclass
class SwingPoint:
    """Một swing point (đỉnh/đáy)."""
    index: int              # Vị trí trong DataFrame
    price: float            # Giá tại swing
    swing_type: SwingType   # HIGH hoặc LOW
    time: Optional[pd.Timestamp] = None

    def __str__(self) -> str:
        return f"{self.swing_type.value} @ {self.price:.2f} (bar {self.index})"


@dataclass
class StructureEvent:
    """Sự kiện phá vỡ cấu trúc."""
    event_type: StructureBreak
    index: int              # Bar phá vỡ
    price: float            # Giá phá vỡ
    broken_level: float     # Mức bị phá
    time: Optional[pd.Timestamp] = None

    def __str__(self) -> str:
        return f"{self.event_type.value} @ {self.price:.2f} (broke {self.broken_level:.2f})"


@dataclass
class SRZone:
    """Vùng Support/Resistance."""
    price: float
    zone_type: str  # "SUPPORT" hoặc "RESISTANCE"
    strength: int = 1  # Số lần test
    first_touch_index: int = 0
    last_touch_index: int = 0


# ──────────────────────────────────────────────
# Swing Detection
# ──────────────────────────────────────────────
def detect_swings(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
) -> list[SwingPoint]:
    """
    Phát hiện Swing High và Swing Low.

    Swing High: nến có high cao nhất trong (left_bars + 1 + right_bars) nến.
    Swing Low: nến có low thấp nhất trong (left_bars + 1 + right_bars) nến.

    Chờ right_bars nến SAU để xác nhận → không look-ahead.

    Args:
        df: DataFrame với columns: high, low, time.
        left_bars: Số nến bên trái. Mặc định: 3.
        right_bars: Số nến bên phải để xác nhận. Mặc định: 3.

    Returns:
        Danh sách SwingPoint đã sắp xếp theo thời gian.
    """
    swings: list[SwingPoint] = []
    highs = df["high"].values
    lows = df["low"].values
    times = df["time"].values if "time" in df.columns else [None] * len(df)

    # Không quét các nến cuối (chưa đủ right_bars để confirm)
    for i in range(left_bars, len(df) - right_bars):
        # Check Swing High
        window_highs = highs[i - left_bars: i + right_bars + 1]
        if highs[i] == window_highs.max() and np.sum(window_highs == highs[i]) == 1:
            swings.append(SwingPoint(
                index=i,
                price=float(highs[i]),
                swing_type=SwingType.SWING_HIGH,
                time=times[i],
            ))

        # Check Swing Low
        window_lows = lows[i - left_bars: i + right_bars + 1]
        if lows[i] == window_lows.min() and np.sum(window_lows == lows[i]) == 1:
            swings.append(SwingPoint(
                index=i,
                price=float(lows[i]),
                swing_type=SwingType.SWING_LOW,
                time=times[i],
            ))

    log.debug(
        "Phát hiện %d swing points (left=%d, right=%d) trên %d bars",
        len(swings), left_bars, right_bars, len(df),
    )
    return swings


# ──────────────────────────────────────────────
# Trend Detection (HH/HL/LH/LL)
# ──────────────────────────────────────────────
def detect_trend(swings: list[SwingPoint]) -> TrendDirection:
    """
    Xác định xu hướng dựa trên chuỗi swing points gần nhất.

    BULLISH: Higher High + Higher Low.
    BEARISH: Lower High + Lower Low.
    NEUTRAL: Không rõ ràng.

    Args:
        swings: Danh sách swing points.

    Returns:
        TrendDirection.
    """
    if len(swings) < 4:
        return TrendDirection.NEUTRAL

    # Lấy 2 swing high và 2 swing low gần nhất
    recent_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
    recent_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]

    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return TrendDirection.NEUTRAL

    last_2_highs = recent_highs[-2:]
    last_2_lows = recent_lows[-2:]

    hh = last_2_highs[1].price > last_2_highs[0].price  # Higher High
    hl = last_2_lows[1].price > last_2_lows[0].price    # Higher Low
    lh = last_2_highs[1].price < last_2_highs[0].price  # Lower High
    ll = last_2_lows[1].price < last_2_lows[0].price    # Lower Low

    if hh and hl:
        return TrendDirection.BULLISH
    elif lh and ll:
        return TrendDirection.BEARISH
    else:
        return TrendDirection.NEUTRAL


# ──────────────────────────────────────────────
# Structure Break Detection (BOS / CHoCH)
# ──────────────────────────────────────────────
def detect_structure_breaks(
    df: pd.DataFrame,
    swings: list[SwingPoint],
) -> list[StructureEvent]:
    """
    Phát hiện BOS (Break of Structure) và CHoCH (Change of Character).

    BOS: Giá phá vỡ swing point CÙNG hướng xu hướng.
      - Trong uptrend, close > swing high trước → BOS_BULLISH.
      - Trong downtrend, close < swing low trước → BOS_BEARISH.

    CHoCH: Giá phá vỡ swing point NGƯỢC hướng xu hướng.
      - Trong uptrend, close < swing low trước → CHOCH_BEARISH.
      - Trong downtrend, close > swing high trước → CHOCH_BULLISH.

    Args:
        df: DataFrame với columns: close, high, low.
        swings: Danh sách swing points.

    Returns:
        Danh sách StructureEvent.
    """
    events: list[StructureEvent] = []

    if len(swings) < 4:
        return events

    closes = df["close"].values
    times = df["time"].values if "time" in df.columns else [None] * len(df)

    # Duyệt qua từng swing point
    swing_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
    swing_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]

    current_trend = detect_trend(swings)

    # Kiểm tra BOS/CHoCH sau mỗi swing
    for i in range(1, len(swing_highs)):
        prev_high = swing_highs[i - 1]
        curr_high = swing_highs[i]
        # Tìm bar đầu tiên close > prev swing high (sau curr swing point)
        for bar_idx in range(curr_high.index + 1, len(df)):
            if closes[bar_idx] > prev_high.price:
                if current_trend == TrendDirection.BULLISH:
                    event_type = StructureBreak.BOS_BULLISH
                else:
                    event_type = StructureBreak.CHOCH_BULLISH
                events.append(StructureEvent(
                    event_type=event_type,
                    index=bar_idx,
                    price=float(closes[bar_idx]),
                    broken_level=prev_high.price,
                    time=times[bar_idx],
                ))
                break

    for i in range(1, len(swing_lows)):
        prev_low = swing_lows[i - 1]
        curr_low = swing_lows[i]
        for bar_idx in range(curr_low.index + 1, len(df)):
            if closes[bar_idx] < prev_low.price:
                if current_trend == TrendDirection.BEARISH:
                    event_type = StructureBreak.BOS_BEARISH
                else:
                    event_type = StructureBreak.CHOCH_BEARISH
                events.append(StructureEvent(
                    event_type=event_type,
                    index=bar_idx,
                    price=float(closes[bar_idx]),
                    broken_level=prev_low.price,
                    time=times[bar_idx],
                ))
                break

    # Sắp xếp theo thời gian
    events.sort(key=lambda e: e.index)

    log.debug("Phát hiện %d structure events", len(events))
    return events


# ──────────────────────────────────────────────
# Support / Resistance Detection
# ──────────────────────────────────────────────
def detect_sr_zones(
    swings: list[SwingPoint],
    tolerance_pct: float = 0.1,
) -> list[SRZone]:
    """
    Phát hiện vùng Support/Resistance dựa trên swing points.

    Gom nhóm các swing point gần nhau (trong tolerance_pct %).

    Args:
        swings: Danh sách swing points.
        tolerance_pct: % dung sai để gom nhóm. Mặc định: 0.1%.

    Returns:
        Danh sách SRZone sắp xếp theo giá.
    """
    if not swings:
        return []

    zones: list[SRZone] = []

    for swing in swings:
        merged = False
        for zone in zones:
            # Kiểm tra swing có nằm trong vùng tolerance không
            diff_pct = abs(swing.price - zone.price) / zone.price * 100
            if diff_pct <= tolerance_pct:
                # Gom nhóm: cập nhật giá trung bình, tăng strength
                zone.price = (zone.price * zone.strength + swing.price) / (zone.strength + 1)
                zone.strength += 1
                zone.last_touch_index = max(zone.last_touch_index, swing.index)
                merged = True
                break

        if not merged:
            zone_type = "RESISTANCE" if swing.swing_type == SwingType.SWING_HIGH else "SUPPORT"
            zones.append(SRZone(
                price=swing.price,
                zone_type=zone_type,
                strength=1,
                first_touch_index=swing.index,
                last_touch_index=swing.index,
            ))

    # Sắp xếp theo giá
    zones.sort(key=lambda z: z.price)

    log.debug(
        "Phát hiện %d S/R zones (S=%d, R=%d)",
        len(zones),
        sum(1 for z in zones if z.zone_type == "SUPPORT"),
        sum(1 for z in zones if z.zone_type == "RESISTANCE"),
    )
    return zones


# ──────────────────────────────────────────────
# Convenience: phân tích cấu trúc đầy đủ
# ──────────────────────────────────────────────
@dataclass
class MarketStructureResult:
    """Kết quả phân tích cấu trúc thị trường."""
    swings: list[SwingPoint] = field(default_factory=list)
    trend: TrendDirection = TrendDirection.NEUTRAL
    structure_events: list[StructureEvent] = field(default_factory=list)
    sr_zones: list[SRZone] = field(default_factory=list)

    @property
    def last_bos(self) -> Optional[StructureEvent]:
        """BOS gần nhất."""
        bos = [e for e in self.structure_events
               if e.event_type in (StructureBreak.BOS_BULLISH, StructureBreak.BOS_BEARISH)]
        return bos[-1] if bos else None

    @property
    def last_choch(self) -> Optional[StructureEvent]:
        """CHoCH gần nhất."""
        choch = [e for e in self.structure_events
                 if e.event_type in (StructureBreak.CHOCH_BULLISH, StructureBreak.CHOCH_BEARISH)]
        return choch[-1] if choch else None


def analyze_market_structure(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
    sr_tolerance_pct: float = 0.1,
) -> MarketStructureResult:
    """
    Phân tích cấu trúc thị trường đầy đủ.

    Args:
        df: DataFrame OHLCV.
        left_bars: Nến bên trái cho swing detection.
        right_bars: Nến bên phải cho swing confirmation.
        sr_tolerance_pct: % dung sai cho S/R zones.

    Returns:
        MarketStructureResult chứa toàn bộ kết quả.
    """
    swings = detect_swings(df, left_bars, right_bars)
    trend = detect_trend(swings)
    events = detect_structure_breaks(df, swings)
    zones = detect_sr_zones(swings, sr_tolerance_pct)

    log.info(
        "✓ Market Structure: trend=%s, %d swings, %d events, %d S/R zones",
        trend.value, len(swings), len(events), len(zones),
    )

    return MarketStructureResult(
        swings=swings,
        trend=trend,
        structure_events=events,
        sr_zones=zones,
    )
