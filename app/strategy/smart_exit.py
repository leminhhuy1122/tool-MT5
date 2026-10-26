# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Smart Exit & Adaptive Profit Protection Engine (Phase 12).

Chịu trách nhiệm:
1. Dynamic ATR Breakeven: Tự động dời Stop Loss về mức hòa vốn bù spread dựa trên ATR và Market Regime.
2. Regime-Adaptive & Swing Structure Trailing Stop:
   - Tự động co giãn khoảng cách trailing Stop theo ATR của từng chế độ thị trường (Ranging, Trending, High Volatility).
   - Trailing bám sát đáy nến Swing Low (BUY) hoặc đỉnh nến Swing High (SELL) trên khung thời gian M5.
3. Multi-Tier Scaled Exits (Quy tắc chốt lời từng phần 50/30/20):
   - Tier 1 (+1.0R): Khuyến nghị chốt 50% khối lượng, khóa BE bảo vệ vốn.
   - Tier 2 (+2.0R): Khuyến nghị chốt thêm 30% khối lượng, kích hoạt Trailing Stop.
   - Tier 3 (Runner 20%): Thả trôi bắt trọn xu hướng lớn dài hạn.
4. Cảnh báo suy yếu động lượng (Momentum Exhaustion) & Lệnh ứ đọng (Time Stagnation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple
import numpy as np
import pandas as pd

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from config import SmartExitConfig
from logger import get_logger

log = get_logger("strategy.smart_exit")


class ExitActionType(str, Enum):
    """Phân loại hành động quản trị rủi ro & thoát lệnh."""
    NONE = "NONE"
    MOVE_BREAKEVEN = "MOVE_BREAKEVEN"
    TRAILING_UPDATE = "TRAILING_UPDATE"
    SCALED_EXIT_TIER1 = "SCALED_EXIT_TIER1"
    SCALED_EXIT_TIER2 = "SCALED_EXIT_TIER2"
    MOMENTUM_EXHAUSTION = "MOMENTUM_EXHAUSTION"
    TIME_STAGNATION = "TIME_STAGNATION"


@dataclass
class ExitDecision:
    """Quyết định điều chỉnh lệnh hoặc cảnh báo thoát vị thế."""
    action_type: ExitActionType
    signal_id: str
    new_sl: Optional[float] = None
    old_sl: Optional[float] = None
    pnl_points: float = 0.0
    pnl_r: float = 0.0
    locked_points: float = 0.0
    close_ratio: float = 0.0          # Tỷ lệ đóng lệnh khuyến nghị (0.5 cho 50%, 0.3 cho 30%)
    tier_name: str = ""               # "TIER_1 (50%)", "TIER_2 (30%)"
    reason: str = ""
    trailing_mode: str = "NONE"       # "ATR_DYNAMIC", "SWING_STRUCTURE", "BREAKEVEN"


class SmartExitEngine:
    """
    Động cơ tính toán mức thoát lệnh, chốt lời từng phần và dời Stop Loss thích ứng.
    """

    def __init__(self, config: Optional[SmartExitConfig] = None):
        self.config = config or SmartExitConfig()

    def evaluate_signal(
        self,
        signal: TradingSignal,
        current_price: float,
        df_m5: Optional[pd.DataFrame] = None,
        market_regime: str = "UNKNOWN",
        current_spread: float = 0.3,
        now_utc: Optional[datetime] = None,
    ) -> list[ExitDecision]:
        """
        Đánh giá trạng thái lợi nhuận hiện tại của tín hiệu để đưa ra các quyết định:
        1. Chốt lời từng phần Tier 1 (50%) & Tier 2 (30%).
        2. Dời Stop Loss về Breakeven (Hòa vốn thích ứng).
        3. Dời Stop Loss theo Trailing Stop (ATR-Dynamic hoặc Swing Structure).
        """
        if not self.config.enabled:
            return []

        if signal.status != SignalStatus.ENTRY_REACHED or signal.entry_price <= 0:
            return []

        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        elif now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        decisions: list[ExitDecision] = []

        # 1. Tính toán PnL điểm và PnL theo R
        pnl_points = (current_price - signal.entry_price) if signal.is_buy else (signal.entry_price - current_price)
        signal.max_favorable_pnl = max(signal.max_favorable_pnl, pnl_points)

        sl_dist = signal.sl_distance if signal.sl_distance > 0 else 5.0
        pnl_r = round(pnl_points / sl_dist, 2) if sl_dist > 0 else 0.0

        # Lấy ATR(14) từ nến M5 nếu có
        atr_14 = 2.5
        if df_m5 is not None and len(df_m5) > 0:
            for col in ("atr_14", "atr", "ATR"):
                if col in df_m5.columns:
                    val = float(df_m5[col].iloc[-1])
                    if not np.isnan(val) and val > 0:
                        atr_14 = val
                        break

        # Khoảng đệm hòa vốn an toàn (bù spread thực tế + commission)
        be_cushion = max(self.config.be_cushion_min_pts, current_spread + 0.2)

        # ── 2. Xử lý Chốt Lời Từng Bậc (Scaled Exits 50/30/20) ──
        if self.config.enable_scaled_exits:
            # Tier 1: Chạm >= +1.0R (Khuyến nghị chốt 50% volume + dời SL về BE)
            if pnl_r >= self.config.tier1_r_threshold and signal.tier_reached < 1:
                signal.tier_reached = 1
                be_sl = round(signal.entry_price + be_cushion, 2) if signal.is_buy else round(signal.entry_price - be_cushion, 2)

                need_move_be = (signal.is_buy and signal.stop_loss < be_sl) or (signal.is_sell and signal.stop_loss > be_sl)
                target_sl = be_sl if need_move_be else signal.stop_loss
                old_sl = signal.stop_loss
                if need_move_be:
                    signal.stop_loss = target_sl

                decisions.append(
                    ExitDecision(
                        action_type=ExitActionType.SCALED_EXIT_TIER1,
                        signal_id=signal.signal_id,
                        new_sl=target_sl if need_move_be else None,
                        old_sl=old_sl,
                        pnl_points=pnl_points,
                        pnl_r=pnl_r,
                        locked_points=be_cushion if need_move_be else 0.0,
                        close_ratio=0.5,
                        tier_name="TIER_1 (50%)",
                        reason=f"Đạt mục tiêu Tier 1 (+{pnl_r:.1f}R / +{pnl_points:.1f} giá), chốt 50% khối lượng và khóa hòa vốn.",
                        trailing_mode="BREAKEVEN",
                    )
                )

            # Tier 2: Chạm >= +2.0R (Khuyến nghị chốt thêm 30% volume)
            elif pnl_r >= self.config.tier2_r_threshold and signal.tier_reached < 2:
                signal.tier_reached = 2
                decisions.append(
                    ExitDecision(
                        action_type=ExitActionType.SCALED_EXIT_TIER2,
                        signal_id=signal.signal_id,
                        new_sl=None,
                        old_sl=signal.stop_loss,
                        pnl_points=pnl_points,
                        pnl_r=pnl_r,
                        close_ratio=0.3,
                        tier_name="TIER_2 (30%)",
                        reason=f"Đạt mục tiêu Tier 2 (+{pnl_r:.1f}R / +{pnl_points:.1f} giá), chốt tiếp 30% khối lượng.",
                        trailing_mode="RUNNER",
                    )
                )

        # ── 3. Dời Stop Loss về Hòa Vốn (Dynamic Breakeven) ──
        # Trong thị trường RANGING hoặc COMPRESSION: Ngưỡng BE kích hoạt sớm hơn (0.8R hoặc 1.2x ATR)
        regime_upper = market_regime.upper()
        if "RANGING" in regime_upper or "COMPRESSION" in regime_upper or "SQUEEZE" in regime_upper:
            be_trigger_pts = min(self.config.be_trigger_r * sl_dist, 1.2 * atr_14, 4.0)
        else:
            be_trigger_pts = min(5.0, max(3.5, self.config.be_trigger_r * sl_dist))

        if pnl_points >= be_trigger_pts:
            if signal.is_buy:
                target_be = round(signal.entry_price + be_cushion, 2)
                if signal.stop_loss < target_be:
                    old_sl = signal.stop_loss
                    signal.stop_loss = target_be
                    signal.trailing_mode = "BREAKEVEN"
                    # Nếu chưa phát sinh decision BE qua Tier 1
                    if not any(d.action_type in (ExitActionType.MOVE_BREAKEVEN, ExitActionType.SCALED_EXIT_TIER1) for d in decisions):
                        decisions.append(
                            ExitDecision(
                                action_type=ExitActionType.MOVE_BREAKEVEN,
                                signal_id=signal.signal_id,
                                new_sl=target_be,
                                old_sl=old_sl,
                                pnl_points=pnl_points,
                                pnl_r=pnl_r,
                                locked_points=be_cushion,
                                reason=f"Lãi đạt +{pnl_points:.1f} giá (ngưỡng BE {be_trigger_pts:.1f} giá), dời SL về hòa vốn bù spread.",
                                trailing_mode="BREAKEVEN",
                            )
                        )
            elif signal.is_sell:
                target_be = round(signal.entry_price - be_cushion, 2)
                if signal.stop_loss > target_be:
                    old_sl = signal.stop_loss
                    signal.stop_loss = target_be
                    signal.trailing_mode = "BREAKEVEN"
                    if not any(d.action_type in (ExitActionType.MOVE_BREAKEVEN, ExitActionType.SCALED_EXIT_TIER1) for d in decisions):
                        decisions.append(
                            ExitDecision(
                                action_type=ExitActionType.MOVE_BREAKEVEN,
                                signal_id=signal.signal_id,
                                new_sl=target_be,
                                old_sl=old_sl,
                                pnl_points=pnl_points,
                                pnl_r=pnl_r,
                                locked_points=be_cushion,
                                reason=f"Lãi đạt +{pnl_points:.1f} giá (ngưỡng BE {be_trigger_pts:.1f} giá), dời SL về hòa vốn bù spread.",
                                trailing_mode="BREAKEVEN",
                            )
                        )

        # ── 4. Dynamic Trailing Stop (ATR-Adaptive & Swing Structure) ──
        trailing_trigger_pts = min(8.0, max(5.0, self.config.trailing_trigger_r * sl_dist))
        if pnl_points >= trailing_trigger_pts:
            trail_sl, trail_mode, locked = self.calculate_adaptive_trailing_sl(
                signal=signal,
                current_price=current_price,
                df_m5=df_m5,
                market_regime=market_regime,
                atr_14=atr_14,
                be_cushion=be_cushion,
            )

            if trail_sl is not None:
                is_valid_update = False
                if signal.is_buy and trail_sl >= signal.stop_loss + 0.3:
                    is_valid_update = True
                elif signal.is_sell and trail_sl <= signal.stop_loss - 0.3:
                    is_valid_update = True

                if is_valid_update:
                    old_sl = signal.stop_loss
                    signal.stop_loss = trail_sl
                    signal.trailing_mode = trail_mode
                    decisions.append(
                        ExitDecision(
                            action_type=ExitActionType.TRAILING_UPDATE,
                            signal_id=signal.signal_id,
                            new_sl=trail_sl,
                            old_sl=old_sl,
                            pnl_points=pnl_points,
                            pnl_r=pnl_r,
                            locked_points=locked,
                            reason=f"Kích hoạt Trailing Stop ({trail_mode}) dời SL đến {trail_sl:.2f}, khóa chặt +{locked:.2f} giá lãi.",
                            trailing_mode=trail_mode,
                        )
                    )

        return decisions

    def calculate_adaptive_trailing_sl(
        self,
        signal: TradingSignal,
        current_price: float,
        df_m5: Optional[pd.DataFrame],
        market_regime: str,
        atr_14: float,
        be_cushion: float,
    ) -> Tuple[Optional[float], str, float]:
        """
        Tính toán mức SL Trailing tối ưu kết hợp giữa ATR và Cấu trúc đáy/đỉnh nến M5:
        - HIGH_VOLATILITY: Hệ số ATR k = 2.0 (tránh bị quét non bởi râu nến).
        - TRENDING: Hệ số ATR k = 1.6 hoặc bám sát Swing Low/High.
        - RANGING / COMPRESSION: Hệ số ATR k = 1.0 (bảo toàn lãi nhanh chóng).
        """
        r_str = str(market_regime).upper()
        if "HIGH_VOLATILITY" in r_str:
            k = 2.0
        elif "TRENDING" in r_str or "STRONG" in r_str:
            k = 1.6
        elif "RANGING" in r_str or "COMPRESSION" in r_str or "SQUEEZE" in r_str:
            k = 1.0
        else:
            k = self.config.trailing_atr_multiplier

        if df_m5 is None:
            atr_dist = 3.5
        else:
            atr_dist = round(max(2.5, k * atr_14), 2)

        if signal.is_buy:
            candidate_atr_sl = round(max(current_price - atr_dist, signal.entry_price + 4.0), 2)
            candidate_sl = candidate_atr_sl
            chosen_mode = "ATR_DYNAMIC"

            # Kiểm tra Swing Low gần nhất (đáy 3 cây nến M5 trước)
            if self.config.enable_swing_trailing and df_m5 is not None and "low" in df_m5.columns and len(df_m5) >= 5:
                swing_low = float(df_m5["low"].iloc[-4:-1].min())
                swing_candidate = round(swing_low - 0.3, 2)
                # Ưu tiên mức SL bảo vệ an toàn cao hơn nhưng không vượt quá giá hiện tại
                if swing_candidate > candidate_atr_sl and swing_candidate < current_price - 1.0:
                    candidate_sl = swing_candidate
                    chosen_mode = "SWING_STRUCTURE"

            # Đảm bảo mức SL trailing tối thiểu phải ở trên điểm hòa vốn
            min_allowed_sl = round(signal.entry_price + be_cushion, 2)
            candidate_sl = max(candidate_sl, min_allowed_sl)
            locked_pts = round(candidate_sl - signal.entry_price, 2)
            return candidate_sl, chosen_mode, max(0.0, locked_pts)

        elif signal.is_sell:
            candidate_atr_sl = round(min(current_price + atr_dist, signal.entry_price - 4.0), 2)
            candidate_sl = candidate_atr_sl
            chosen_mode = "ATR_DYNAMIC"

            if self.config.enable_swing_trailing and df_m5 is not None and "high" in df_m5.columns and len(df_m5) >= 5:
                swing_high = float(df_m5["high"].iloc[-4:-1].max())
                swing_candidate = round(swing_high + 0.3, 2)
                if swing_candidate < candidate_atr_sl and swing_candidate > current_price + 1.0:
                    candidate_sl = swing_candidate
                    chosen_mode = "SWING_STRUCTURE"

            min_allowed_sl = round(signal.entry_price - be_cushion, 2)
            candidate_sl = min(candidate_sl, min_allowed_sl)
            locked_pts = round(signal.entry_price - candidate_sl, 2)
            return candidate_sl, chosen_mode, max(0.0, locked_pts)

        return None, "NONE", 0.0

    def evaluate_candle_exhaustion(
        self,
        signal: TradingSignal,
        df_m5: pd.DataFrame,
        current_price: float,
        now_utc: Optional[datetime] = None,
    ) -> Optional[ExitDecision]:
        """
        Kiểm tra Cảnh báo Suy yếu Động lượng (Rejection Wick >= 50%) và Lệnh Ứ đọng (Time Decay > 60 phút).
        """
        if signal.status != SignalStatus.ENTRY_REACHED or signal.entry_price <= 0:
            return None

        if df_m5 is None or len(df_m5) < 2:
            return None

        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        elif now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        pnl_points = (current_price - signal.entry_price) if signal.is_buy else (signal.entry_price - current_price)
        sl_dist = signal.sl_distance if signal.sl_distance > 0 else 5.0
        pnl_r = round(pnl_points / sl_dist, 2) if sl_dist > 0 else 0.0

        last_bar = df_m5.iloc[-1]
        o = float(last_bar["open"])
        h = float(last_bar["high"])
        l = float(last_bar["low"])
        c = float(last_bar["close"])
        c_range = h - l

        # 1. Cảnh báo Động lượng suy yếu (Rejection Wick >= 50%) khi đang lãi >= 3.0 giá
        if pnl_points >= 3.0 and c_range >= 1.0:
            if signal.is_buy:
                upper_wick = h - max(o, c)
                wick_ratio = upper_wick / c_range
                if wick_ratio >= 0.50 or (c < o and upper_wick >= 1.2):
                    return ExitDecision(
                        action_type=ExitActionType.MOMENTUM_EXHAUSTION,
                        signal_id=signal.signal_id,
                        pnl_points=pnl_points,
                        pnl_r=pnl_r,
                        reason=f"Nến M5 xuất hiện râu từ chối bán mạnh ({wick_ratio*100:.0f}%) tại đỉnh {h:.2f}.",
                    )
            elif signal.is_sell:
                lower_wick = min(o, c) - l
                wick_ratio = lower_wick / c_range
                if wick_ratio >= 0.50 or (c > o and lower_wick >= 1.2):
                    return ExitDecision(
                        action_type=ExitActionType.MOMENTUM_EXHAUSTION,
                        signal_id=signal.signal_id,
                        pnl_points=pnl_points,
                        pnl_r=pnl_r,
                        reason=f"Nến M5 xuất hiện râu từ chối mua mạnh ({wick_ratio*100:.0f}%) tại đáy {l:.2f}.",
                    )

        # 2. Cảnh báo Lệnh ứ đọng (Time Decay > 60 phút) khi lãi >= 2.0 giá
        if pnl_points >= 2.0 and signal.created_at:
            c_time = signal.created_at if signal.created_at.tzinfo else signal.created_at.replace(tzinfo=timezone.utc)
            diff_minutes = int((now_utc - c_time).total_seconds() / 60.0)
            if diff_minutes >= 60:
                return ExitDecision(
                    action_type=ExitActionType.TIME_STAGNATION,
                    signal_id=signal.signal_id,
                    pnl_points=pnl_points,
                    pnl_r=pnl_r,
                    reason=f"Lệnh ngâm {diff_minutes} phút quanh mức lãi +{pnl_points:.1f} giá, rủi ro đảo chiều phiên.",
                )

        return None
