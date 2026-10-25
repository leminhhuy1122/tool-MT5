# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Signal Engine.

Trung tâm điều phối phát sinh tín hiệu giao dịch:
1. Nhận dữ liệu đa khung thời gian (H4, H1, M15).
2. Tự động tính toán indicators & market structure nếu chưa có.
3. Phát hiện setup candidates qua SetupDetector.
4. Lọc qua RiskFilter (R:R, Trend H4, Spread, Volatility, Score).
5. Chấm điểm confluence score (0-100) qua SignalScoring.
6. Chống phát trùng lặp qua SignalTracker.
7. Trả về TradingSignal chuẩn hóa (BUY / SELL / WAIT).

LƯU Ý AN TOÀN:
- TUYỆT ĐỐI KHÔNG TỰ ĐỘNG ĐẶT LỆNH.
- KHÔNG TUYÊN BỐ XÁC SUẤT THẮNG (WIN RATE).
- Luôn kèm theo vùng Entry, Stop Loss, Take Profit và điều kiện Invalidation.
"""

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from app.market.indicators import add_all_indicators
from app.market.market_structure import (
    MarketStructureResult,
    TrendDirection,
    analyze_market_structure,
)
from app.market.volatility import VolatilityResult, analyze_volatility
from app.strategy.risk_filter import FilterConfig, apply_filters
from app.strategy.setup_detector import SetupCandidate, detect_setups
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_scoring import calculate_signal_score
from app.strategy.signal_tracker import SignalTracker, TrackerConfig
from logger import get_logger

log = get_logger("strategy.engine")


class SignalEngine:
    """
    Signal Engine trung tâm cho VietKey Gold AI.
    """

    def __init__(
        self,
        strategy_version: str = "v1.0",
        filter_config: Optional[FilterConfig] = None,
        tracker_config: Optional[TrackerConfig] = None,
        symbol: str = "XAUUSD",
        default_timeframe: str = "H1",
    ):
        self.strategy_version = strategy_version
        self.filter_config = filter_config or FilterConfig()
        self.tracker = SignalTracker(tracker_config)
        self.symbol = symbol
        self.default_timeframe = default_timeframe

        log.info(
            "Đã khởi tạo SignalEngine (%s) cho symbol %s [%s]",
            self.strategy_version, self.symbol, self.default_timeframe,
        )

    def generate_signal(
        self,
        df: pd.DataFrame,
        h4_df: Optional[pd.DataFrame] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        volatility: Optional[VolatilityResult] = None,
        current_spread: Optional[float] = None,
    ) -> TradingSignal:
        """
        Phân tích dữ liệu và sinh tín hiệu giao dịch.

        Args:
            df: DataFrame nến của khung giao dịch chính (vd: H1).
            h4_df: DataFrame nến khung H4 (để xác định trend lớn).
            symbol: Mã giao dịch (mặc định XAUUSD).
            timeframe: Khung thời gian thực thi (mặc định H1).
            volatility: Kết quả phân tích biến động (nếu đã có).
            current_spread: Spread hiện tại của sàn (points).

        Returns:
            TradingSignal (BUY / SELL hoặc WAIT).
        """
        target_symbol = symbol or self.symbol
        target_tf = timeframe or self.default_timeframe

        if df is None or len(df) < 20:
            log.warning("Dữ liệu nến không đủ để phân tích (%s)", len(df) if df is not None else 0)
            return TradingSignal(
                strategy_version=self.strategy_version,
                direction=SignalDirection.WAIT,
                symbol=target_symbol,
                timeframe=target_tf,
                reasons=["Dữ liệu nến không đủ (yêu cầu tối thiểu 20 nến)"],
            )

        # 1. Đảm bảo indicators sẵn sàng
        working_df = df.copy()
        required_cols = {"ema_20", "ema_50", "rsi_14", "atr_14"}
        if not required_cols.issubset(working_df.columns):
            working_df = add_all_indicators(working_df)

        # 2. Xác định Higher Timeframe Trend (H4)
        h4_trend = TrendDirection.NEUTRAL
        if h4_df is not None and len(h4_df) >= 20:
            h4_structure = analyze_market_structure(h4_df)
            h4_trend = h4_structure.trend
            log.debug("H4 Trend: %s", h4_trend.value)

        # 3. Phân tích Market Structure khung chính
        structure = analyze_market_structure(working_df)

        # 4. Phân tích Volatility nếu chưa có
        if volatility is None:
            if current_spread is not None and "spread" not in working_df.columns:
                working_df["spread"] = float(current_spread)
            volatility = analyze_volatility(working_df)

        # 5. Lấy giá trị ATR hiện tại
        last_candle = working_df.iloc[-1]
        atr_value = float(last_candle.get("atr_14", 0.0))
        if atr_value <= 0.0:
            atr_value = volatility.current_atr if volatility else 0.0

        # 6. Phát hiện setup candidates
        candidates = detect_setups(
            df=working_df,
            structure=structure,
            volatility=volatility,
            higher_tf_trend=h4_trend,
            atr_value=atr_value,
        )

        if not candidates:
            log.debug("Không tìm thấy setup nào trên %s %s", target_symbol, target_tf)
            return TradingSignal(
                strategy_version=self.strategy_version,
                direction=SignalDirection.WAIT,
                symbol=target_symbol,
                timeframe=target_tf,
                trend_h4=h4_trend.value,
                trend_h1=structure.trend.value,
                reasons=["Thị trường đang tích lũy hoặc không có setup đạt chuẩn"],
            )

        # 7. Duyệt qua các candidates và áp dụng filters & scoring
        rejection_reasons: list[str] = []
        is_duplicate_detected = False

        for candidate in candidates:
            # 7a. Kiểm tra bộ lọc rủi ro (Risk Filter)
            filter_res = apply_filters(
                candidate=candidate,
                higher_tf_trend=h4_trend,
                volatility=volatility,
                config=self.filter_config,
            )

            if not filter_res.passed:
                rejection_reasons.extend(filter_res.reasons_rejected)
                continue

            # 7b. Kiểm tra trùng lặp
            candidate_direction = SignalDirection(candidate.direction.upper())
            if self.tracker.is_duplicate(target_symbol, candidate_direction):
                is_duplicate_detected = True
                continue

            # 7c. Chấm điểm Confluence Score
            score_res = calculate_signal_score(
                candidate=candidate,
                h4_trend=h4_trend,
                h1_structure=structure,
                volatility=volatility,
            )

            # 7d. Xác định Entry Zone (Cushion bằng 15% ATR)
            cushion = atr_value * 0.15 if atr_value > 0 else 0.5
            if candidate_direction == SignalDirection.BUY:
                entry_zone_low = candidate.entry_price - cushion
                entry_zone_high = candidate.entry_price + (cushion * 0.5)
            else:
                entry_zone_low = candidate.entry_price - (cushion * 0.5)
                entry_zone_high = candidate.entry_price + cushion

            # Cấu trúc TP1 (10-12 giá: tỷ lệ ăn TP cao, kéo BE) và TP2 (20-24 giá: gồng lời tối đa)
            tp1 = candidate.tp1
            tp2 = candidate.take_profit
            tp1_dist = abs(candidate.entry_price - tp1)
            sl_dist = candidate.sl_distance

            # Ghép danh sách lý do
            all_reasons = list(candidate.reasons)
            all_reasons.extend(filter_res.reasons_passed)
            all_reasons.extend(score_res.details)

            # Tạo TradingSignal hoàn chỉnh
            signal = TradingSignal(
                strategy_version=self.strategy_version,
                direction=candidate_direction,
                status=SignalStatus.ACTIVE,
                symbol=target_symbol,
                timeframe=target_tf,
                entry_price=round(candidate.entry_price, 2),
                entry_zone_low=round(entry_zone_low, 2),
                entry_zone_high=round(entry_zone_high, 2),
                stop_loss=round(candidate.stop_loss, 2),
                take_profit_1=round(tp1, 2),
                take_profit_2=round(tp2, 2),
                risk_reward_ratio=round(candidate.risk_reward, 2),
                sl_distance=round(sl_dist, 2),
                tp_distance=round(tp1_dist, 2),
                score=round(score_res.total_score, 1),
                confidence=score_res.confidence,
                trend_h4=h4_trend.value,
                trend_h1=structure.trend.value,
                setup_type=candidate.setup_type.value,
                reasons=all_reasons,
                invalidation=candidate.invalidation,
            )

            # Đăng ký vào tracker
            self.tracker.register_signal(signal)

            log.info("✓ PHÁT TÍN HIỆU THÀNH CÔNG:\n%s", signal.summary())
            return signal

        # Không candidate nào vượt qua bộ lọc hoặc bị trùng lặp
        wait_reasons: list[str] = []
        if is_duplicate_detected:
            wait_reasons.append("Tín hiệu cùng hướng đang hoạt động hoặc trong thời gian cooldown")
        if rejection_reasons:
            wait_reasons.append(f"Setup bị loại bởi bộ lọc: {'; '.join(rejection_reasons)}")
        if not wait_reasons:
            wait_reasons.append("Chưa thỏa mãn đầy đủ các điều kiện vào lệnh an toàn")

        return TradingSignal(
            strategy_version=self.strategy_version,
            direction=SignalDirection.WAIT,
            symbol=target_symbol,
            timeframe=target_tf,
            trend_h4=h4_trend.value,
            trend_h1=structure.trend.value,
            reasons=wait_reasons,
        )

    def update_market_price(
        self,
        current_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        current_time: Optional[datetime] = None,
    ) -> list[TradingSignal]:
        """
        Cập nhật trạng thái tín hiệu theo giá thị trường mới.

        Args:
            current_price: Giá hiện tại.
            high_price: Giá cao nhất (nến).
            low_price: Giá thấp nhất (nến).
            current_time: Thời điểm cập nhật (UTC).

        Returns:
            Danh sách các tín hiệu vừa có sự thay đổi trạng thái.
        """
        return self.tracker.update_price(
            current_price=current_price,
            high_price=high_price,
            low_price=low_price,
            current_time=current_time,
        )

    def get_active_signals(self) -> list[TradingSignal]:
        """Lấy danh sách các tín hiệu đang active."""
        return self.tracker.active_signals

    def get_all_signals(self) -> list[TradingSignal]:
        """Lấy toàn bộ lịch sử tín hiệu."""
        return self.tracker.all_signals
