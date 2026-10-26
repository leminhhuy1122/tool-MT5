# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Confluence Scoring & Dynamic Weighting Engine (Phase 4).

Chấm điểm chất lượng setup giao dịch trên thang điểm 0-100 với hệ số trọng số động
thích ứng theo Market Regime, phiên giao dịch Vàng (Gold Trading Session) và Volume Delta.

LƯU Ý QUAN TRỌNG:
- Điểm số (Score) KHÔNG PHẢI là xác suất thắng (win probability).
- Điểm số phản ánh mức độ hội tụ các điều kiện kỹ thuật (confluence score).

Thang điểm cấu thành cơ sở (tổng chuẩn hóa 100):
1. Trend Alignment (tối đa 25 điểm):
   - H4 trend đồng thuận: 15 điểm
   - H1 trend đồng thuận: 10 điểm
2. Market Structure (tối đa 25 điểm):
   - BOS / CHoCH xác nhận: 15 điểm
   - Retest vùng S/R hoặc Swing Point: 10 điểm
   - SMC Confluence (Order Block, Liquidity Sweep, FVG): tối đa 25 điểm
3. Technical Indicators (tối đa 20 điểm):
   - EMA alignment / bounce: 10 điểm
   - RSI ở vùng thuận lợi: 10 điểm
   - Price Action / Predictive Anticipation: tối đa 20 điểm
4. Risk / Reward Ratio (tối đa 15 điểm):
   - R:R >= 2.5: 15 điểm
   - R:R >= 2.0: 12 điểm
   - R:R >= 1.5: 8 điểm
   - R:R >= 1.0: 4 điểm
5. Volatility Context (tối đa 15 điểm):
   - Volatility Normal: 15 điểm
   - Volatility Low: 10 điểm
   - Volatility High: 5 điểm
   - Volatility Extreme: 0 điểm

Hệ thống Trọng số Động (Dynamic Weighting Matrix theo Regime):
- TRENDING: Trend (30%), Structure (25%), Indicator (20%), RR (15%), Volatility (10%)
- RANGING: Structure (35%), Indicator (20%), RR (20%), Volatility (15%), Trend (10%)
- HIGH_VOLATILITY: Structure (25%), Volatility (20%), RR (20%), Trend (20%), Indicator (15%)
- COMPRESSION_SQUEEZE: Structure (30%), Indicator (20%), Trend (20%), RR (15%), Volatility (15%)
- DEFAULT: Trend (25%), Structure (25%), Indicator (20%), RR (15%), Volatility (15%)

Yếu tố Bổ sung:
6. Regime Adjustment: Điểm cộng/trừ setup theo đặc thù Regime (-10 đến +10).
7. Session Timing Factor: Khung giờ vàng London - New York (+5, +3, +2, 0, -3).
8. Volume Delta Dynamics: Volume đột biến xác nhận dòng tiền (+4, +2, 0, -2).

Phân tầng Chất lượng Tín hiệu (Confidence Tiering):
- TIER_1_STRONG: Score >= 80.0 (Tín hiệu chất lượng cao, hội tụ đa yếu tố)
- TIER_2_MODERATE: 65.0 <= Score < 80.0 (Tín hiệu trung bình khá)
- TIER_3_WEAK: 50.0 <= Score < 65.0 (Tín hiệu yếu, cần theo dõi thêm)
- REJECT: Score < 50.0 (Không đủ tiêu chuẩn phát tín hiệu)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from app.market.market_structure import MarketStructureResult, TrendDirection
from app.market.volatility import VolatilityLevel, VolatilityResult
from app.strategy.setup_detector import SetupCandidate
from logger import get_logger

if TYPE_CHECKING:
    from app.market.regime import MarketRegimeResult

log = get_logger("strategy.scoring")


# Ma trận trọng số thích ứng theo từng Market Regime
REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    # Trending: Xu hướng và cấu trúc chiếm tỷ trọng lớn nhất (55%)
    "TRENDING_BULLISH": {
        "trend": 0.30,
        "structure": 0.25,
        "indicator": 0.20,
        "rr": 0.15,
        "volatility": 0.10,
    },
    "TRENDING_BEARISH": {
        "trend": 0.30,
        "structure": 0.25,
        "indicator": 0.20,
        "rr": 0.15,
        "volatility": 0.10,
    },
    # Ranging: Cấu trúc biên độ (S/R, Quét thanh khoản) quyết định
    "RANGING": {
        "trend": 0.10,
        "structure": 0.35,
        "indicator": 0.20,
        "rr": 0.20,
        "volatility": 0.15,
    },
    # High Volatility: Quản trị biến động & R:R để tránh quét SL
    "HIGH_VOLATILITY_EXPANSION": {
        "trend": 0.20,
        "structure": 0.25,
        "indicator": 0.15,
        "rr": 0.20,
        "volatility": 0.20,
    },
    # Squeeze / Compression: Cấu trúc nén và các chỉ báo dao động
    "COMPRESSION_SQUEEZE": {
        "trend": 0.20,
        "structure": 0.30,
        "indicator": 0.20,
        "rr": 0.15,
        "volatility": 0.15,
    },
}

# Trọng số mặc định chuẩn hóa theo tỷ lệ điểm gốc: 25/25/20/15/15
DEFAULT_WEIGHTS: dict[str, float] = {
    "trend": 0.25,
    "structure": 0.25,
    "indicator": 0.20,
    "rr": 0.15,
    "volatility": 0.15,
}


@dataclass
class ScoreBreakdown:
    """Chi tiết điểm số thành phần và trọng số động."""
    trend_score: float = 0.0          # Max 25
    structure_score: float = 0.0      # Max 25
    indicator_score: float = 0.0      # Max 20
    rr_score: float = 0.0             # Max 15
    volatility_score: float = 0.0     # Max 15
    regime_score: float = 0.0         # Điểm cộng/trừ thích ứng từ Regime
    session_score: float = 0.0        # Điểm phiên giao dịch Vàng (London/NY/Asian/Dead)
    volume_score: float = 0.0         # Điểm volume surge
    setup_perf_score: float = 0.0     # Điểm cộng/trừ từ hiệu suất lịch sử setup
    total_score: float = 0.0          # Max 100
    confidence: str = "LOW"           # LOW / MEDIUM / HIGH (tương thích ngược)
    confidence_tier: str = "REJECT"   # TIER_1_STRONG / TIER_2_MODERATE / TIER_3_WEAK / REJECT
    dynamic_weights: dict = field(default_factory=dict)
    factor_breakdown: dict = field(default_factory=dict)
    details: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Score: {self.total_score:.1f}/100 [{self.confidence_tier} - {self.confidence}] | "
            f"Trend: {self.trend_score:.0f}, Struct: {self.structure_score:.0f}, "
            f"Ind: {self.indicator_score:.0f}, RR: {self.rr_score:.0f}, "
            f"Vol: {self.volatility_score:.0f}, Regime: {self.regime_score:+.0f}, "
            f"Session: {self.session_score:+.0f}, Volu: {self.volume_score:+.0f}, "
            f"Perf: {self.setup_perf_score:+.0f}"
        )


def get_gold_session(dt: Optional[datetime] = None) -> tuple[str, float, str]:
    """
    Xác định phiên giao dịch Vàng (XAUUSD) theo giờ UTC và điểm cộng/trừ thanh khoản:
    - LONDON_NY_OVERLAP (12:00 - 16:00 UTC): +5 điểm (Thanh khoản đỉnh cao, spread hẹp, đà di chuyển mạnh)
    - LONDON_OPEN (07:00 - 12:00 UTC): +3 điểm (Phiên London sôi động, thể chế vào lệnh)
    - NY_AFTERNOON (16:00 - 20:00 UTC): +2 điểm (Phiên chiều New York, duy trì xu hướng)
    - ASIAN_SESSION (00:00 - 07:00 UTC): 0 điểm (Phiên Á thường sideway/tích lũy biên độ hẹp)
    - DEAD_HOURS (20:00 - 24:00 UTC): -3 điểm (Giao thoa đóng cửa, giãn spread, thanh khoản mỏng)

    Args:
        dt: Thời điểm kiểm tra (UTC). Nếu None, trả về mặc định trung tính.

    Returns:
        tuple: (session_name, session_score, description)
    """
    if dt is None:
        return "DEFAULT", 0.0, "Thời gian mặc định"

    hour = dt.hour
    if 12 <= hour < 16:
        return "LONDON_NY_OVERLAP", 5.0, "Thanh khoản đỉnh cao (Overlap London - NY)"
    elif 7 <= hour < 12:
        return "LONDON_OPEN", 3.0, "Phiên London thanh khoản dồi dào"
    elif 16 <= hour < 20:
        return "NY_AFTERNOON", 2.0, "Phiên chiều New York duy trì xu hướng"
    elif 0 <= hour < 7:
        return "ASIAN_SESSION", 0.0, "Phiên Châu Á biên độ tích lũy"
    else:  # 20 <= hour < 24
        return "DEAD_HOURS", -3.0, "Giờ thanh khoản mỏng, giãn spread"


def calculate_volume_factor(
    df: Optional[Any] = None,
    setup_type: str = "",
) -> tuple[float, str]:
    """
    Phân tích tỷ lệ volume nến hiện tại so với MA(20) Volume:
    - Volume surge (>= 1.8x MA20): +4 điểm
    - Volume xác nhận (>= 1.3x MA20): +2 điểm
    - Volume cạn kiệt (< 0.6x MA20) trên setup breakout/trend: -2 điểm
    - Khác: 0 điểm

    Args:
        df: DataFrame chứa nến giá và volume.
        setup_type: Tên loại setup giao dịch.

    Returns:
        tuple: (volume_score, description)
    """
    if df is None:
        return 0.0, "Không có dữ liệu volume"

    try:
        vol_col = None
        for col in ("tick_volume", "real_volume", "volume"):
            if col in df.columns:
                vol_col = col
                break

        if not vol_col or len(df) < 20:
            return 0.0, "Dữ liệu volume không đủ 20 nến"

        series = df[vol_col]
        avg_vol = float(series.tail(20).mean())
        if avg_vol <= 0:
            return 0.0, "MA Volume bằng 0"

        cur_vol = float(series.iloc[-1])
        vol_ratio = cur_vol / avg_vol

        st_lower = setup_type.lower()
        if vol_ratio >= 1.8:
            return 4.0, f"Volume bùng nổ ({vol_ratio:.1f}x MA20) (+4)"
        elif vol_ratio >= 1.3:
            return 2.0, f"Volume gia tăng ({vol_ratio:.1f}x MA20) (+2)"
        elif vol_ratio < 0.6 and any(k in st_lower for k in ("bos", "breakout", "trend")):
            return -2.0, f"Cảnh báo volume thấp ({vol_ratio:.1f}x MA20) khi breakout (-2)"
        else:
            return 0.0, f"Volume bình thường ({vol_ratio:.1f}x MA20)"
    except Exception as e:
        log.debug("Lỗi tính volume factor: %s", e)
        return 0.0, "Lỗi tính volume"


def calculate_signal_score(
    candidate: SetupCandidate,
    h4_trend: TrendDirection = TrendDirection.NEUTRAL,
    h1_structure: Optional[MarketStructureResult] = None,
    volatility: Optional[VolatilityResult] = None,
    regime: Optional["MarketRegimeResult"] = None,
    df: Optional[Any] = None,
    current_time: Optional[datetime] = None,
    setup_evaluator: Optional[Any] = None,
    setup_perf_modifier: float = 0.0,
    feedback_engine: Optional[Any] = None,
) -> ScoreBreakdown:
    """
    Tính điểm confluence cho setup candidate với Dynamic Weighting Engine.

    Args:
        candidate: Setup candidate cần chấm điểm.
        h4_trend: Xu hướng khung H4.
        h1_structure: Kết quả cấu trúc khung H1.
        volatility: Kết quả phân tích biến động.
        regime: Kết quả phân tích Market Regime (tùy chọn).
        df: DataFrame nến giá để tính Volume Delta Dynamics (tùy chọn).
        current_time: Thời gian hiện tại để tính Session Timing Factor (tùy chọn).
        setup_evaluator: Động cơ SetupPerformanceEvaluator đánh giá lịch sử (tùy chọn).
        setup_perf_modifier: Điểm cộng/trừ hiệu suất setup truyền trực tiếp (tùy chọn).
        feedback_engine: Động cơ SelfLearningFeedbackEngine thích ứng từ closed trades (tùy chọn).

    Returns:
        ScoreBreakdown chứa tổng điểm, trọng số động và chi tiết từng tiêu chí.
    """
    details: list[str] = []
    direction = candidate.direction.upper()

    # 1. Trend Alignment (Max 25)
    trend_score = 0.0
    if direction == "BUY":
        if h4_trend == TrendDirection.BULLISH:
            trend_score += 15.0
            details.append("H4 Trend Bullish (+15)")
        elif h4_trend == TrendDirection.NEUTRAL:
            trend_score += 5.0
            details.append("H4 Trend Neutral (+5)")

        if h1_structure and h1_structure.trend == TrendDirection.BULLISH:
            trend_score += 10.0
            details.append("H1 Trend Bullish (+10)")
        elif h1_structure and h1_structure.trend == TrendDirection.NEUTRAL:
            trend_score += 3.0
            details.append("H1 Trend Neutral (+3)")

    elif direction == "SELL":
        if h4_trend == TrendDirection.BEARISH:
            trend_score += 15.0
            details.append("H4 Trend Bearish (+15)")
        elif h4_trend == TrendDirection.NEUTRAL:
            trend_score += 5.0
            details.append("H4 Trend Neutral (+5)")

        if h1_structure and h1_structure.trend == TrendDirection.BEARISH:
            trend_score += 10.0
            details.append("H1 Trend Bearish (+10)")
        elif h1_structure and h1_structure.trend == TrendDirection.NEUTRAL:
            trend_score += 3.0
            details.append("H1 Trend Neutral (+3)")

    trend_score = min(trend_score, 25.0)

    # 2. Market Structure (Max 25)
    structure_score = 0.0
    if h1_structure:
        # Check BOS
        if h1_structure.last_bos is not None:
            bos_type = h1_structure.last_bos.event_type.value
            if (direction == "BUY" and "BULLISH" in bos_type) or \
               (direction == "SELL" and "BEARISH" in bos_type):
                structure_score += 15.0
                details.append(f"Structure {bos_type} (+15)")

        # Check CHoCH
        if h1_structure.last_choch is not None:
            choch_type = h1_structure.last_choch.event_type.value
            if (direction == "BUY" and "BULLISH" in choch_type) or \
               (direction == "SELL" and "BEARISH" in choch_type):
                structure_score = max(structure_score, 12.0)
                details.append(f"Structure {choch_type} (+12)")

        # Check S/R zone confluence
        entry = candidate.entry_price
        near_sr = any(abs(z.price - entry) / entry <= 0.003 for z in h1_structure.sr_zones)
        if near_sr:
            structure_score += 10.0
            details.append("Retest Support/Resistance Zone (+10)")

    # Check SMC & Candidate Structure Confluence
    if candidate.score_components:
        smc_score = (
            candidate.score_components.get("bos", 0.0) +
            candidate.score_components.get("retest", 0.0) +
            candidate.score_components.get("support", 0.0) +
            candidate.score_components.get("resistance", 0.0) +
            candidate.score_components.get("fvg", 0.0) +
            candidate.score_components.get("order_block", 0.0) +
            candidate.score_components.get("liquidity_sweep", 0.0)
        )
        if smc_score > 0:
            if structure_score == 0.0 or any(k in candidate.score_components for k in ("liquidity_sweep", "fvg", "order_block")):
                structure_score = max(structure_score, min(smc_score, 25.0))
                if any(k in candidate.score_components for k in ("liquidity_sweep", "fvg", "order_block")):
                    details.append(f"SMC Structural Confluence (+{structure_score:.0f})")
                else:
                    details.append(f"Setup Structure Components (+{structure_score:.0f})")

    structure_score = min(structure_score, 25.0)

    # 3. Technical Indicators & Price Action (Max 20)
    indicator_score = 0.0
    if candidate.score_components:
        ema_comp = candidate.score_components.get("ema", 0.0)
        rsi_comp = candidate.score_components.get("rsi", 0.0)
        pa_comp = candidate.score_components.get("price_action", 0.0)
        antic_comp = candidate.score_components.get("anticipation", 0.0)
        indicator_score = min(ema_comp + rsi_comp + pa_comp + antic_comp, 20.0)
        if indicator_score > 0:
            if antic_comp > 0:
                details.append(f"Predictive Limit Anticipation (+{indicator_score:.0f})")
            else:
                details.append(f"Indicators/Price Action Confluence (+{indicator_score:.0f})")
    else:
        indicator_score = 10.0

    indicator_score = min(indicator_score, 20.0)

    # 4. Risk / Reward Ratio (Max 15)
    rr = candidate.risk_reward
    rr_score = 0.0
    if rr >= 2.5:
        rr_score = 15.0
        details.append(f"R:R cao (1:{rr:.1f}) (+15)")
    elif rr >= 2.0:
        rr_score = 12.0
        details.append(f"R:R tốt (1:{rr:.1f}) (+12)")
    elif rr >= 1.5:
        rr_score = 8.0
        details.append(f"R:R chuẩn (1:{rr:.1f}) (+8)")
    elif rr >= 1.0:
        rr_score = 4.0
        details.append(f"R:R thấp (1:{rr:.1f}) (+4)")
    else:
        rr_score = 0.0
        details.append(f"R:R không đạt (1:{rr:.1f}) (+0)")

    # 5. Volatility Context (Max 15)
    volatility_score = 0.0
    if volatility is not None:
        if volatility.level == VolatilityLevel.NORMAL:
            volatility_score = 15.0
            details.append(f"Volatility {volatility.level.value} (+15)")
        elif volatility.level == VolatilityLevel.LOW:
            volatility_score = 10.0
            details.append("Volatility Low (+10)")
        elif volatility.level == VolatilityLevel.HIGH:
            volatility_score = 5.0
            details.append("Volatility High (+5)")
        elif volatility.level == VolatilityLevel.EXTREME:
            volatility_score = 0.0
            details.append("Volatility Extreme (+0)")
    else:
        volatility_score = 10.0
        details.append("Volatility Default (+10)")

    # 6. Chọn bảng trọng số động theo Regime & tính điểm cơ sở
    weights = DEFAULT_WEIGHTS.copy()
    regime_name = "DEFAULT"
    regime_score = 0.0

    if regime is not None:
        regime_val = regime.regime.value if hasattr(regime.regime, "value") else str(regime.regime)
        regime_name = regime_val
        if regime_val in REGIME_WEIGHTS:
            weights = REGIME_WEIGHTS[regime_val].copy()

        regime_score = regime.get_score_adjustment(candidate.setup_type)
        if regime_score != 0.0:
            sign = "+" if regime_score > 0 else ""
            details.append(f"Regime {regime_val} ({sign}{regime_score:.0f})")

    # Chuẩn hóa từng thành phần (0.0 - 1.0)
    trend_norm = (trend_score / 25.0) if trend_score > 0 else 0.0
    struct_norm = (structure_score / 25.0) if structure_score > 0 else 0.0
    ind_norm = (indicator_score / 20.0) if indicator_score > 0 else 0.0
    rr_norm = (rr_score / 15.0) if rr_score > 0 else 0.0
    vol_norm = (volatility_score / 15.0) if volatility_score > 0 else 0.0

    weighted_base = (
        weights["trend"] * trend_norm +
        weights["structure"] * struct_norm +
        weights["indicator"] * ind_norm +
        weights["rr"] * rr_norm +
        weights["volatility"] * vol_norm
    ) * 100.0

    # 7. Session Timing Factor
    session_name, session_score, session_desc = get_gold_session(current_time)
    if session_score != 0.0:
        sign = "+" if session_score > 0 else ""
        details.append(f"Session {session_name} ({sign}{session_score:.0f}): {session_desc}")
    elif current_time is not None:
        details.append(f"Session {session_name}: {session_desc}")

    # 8. Volume Delta Dynamics Factor
    st_val = candidate.setup_type.value if hasattr(candidate.setup_type, "value") else str(candidate.setup_type)
    volume_score, vol_desc = calculate_volume_factor(df, setup_type=st_val)
    if volume_score != 0.0:
        details.append(vol_desc)

    # 9. Historical Setup Performance Factor
    setup_perf_score = 0.0
    if setup_evaluator is not None:
        try:
            setup_perf_score = float(setup_evaluator.get_score_modifier(candidate.setup_type))
        except Exception as e:
            log.debug("Lỗi lấy setup performance modifier: %s", e)
            setup_perf_score = 0.0
    else:
        setup_perf_score = float(setup_perf_modifier)

    if setup_perf_score != 0.0:
        sign = "+" if setup_perf_score > 0 else ""
        details.append(f"Setup Performance ({sign}{setup_perf_score:.0f})")

    # 9b. Self-Learning Feedback Adjustment (Phase 8)
    feedback_score = 0.0
    if feedback_engine is not None:
        try:
            feedback_adj = feedback_engine.get_feedback_adjustment(
                setup_type=st_val,
                regime=regime_name,
            )
            feedback_score = float(feedback_adj.get("score_adjustment", 0.0))
            if feedback_score != 0.0:
                details.append(feedback_adj.get("reason", f"Self-Learning: {feedback_score:+.0f}"))
        except Exception as e:
            log.debug("Lỗi tính feedback adjustment: %s", e)
            feedback_score = 0.0

    # 10. Tổng điểm Confluence cuối cùng
    total_score = round(
        weighted_base + regime_score + session_score + volume_score + setup_perf_score + feedback_score,
        1
    )
    total_score = max(0.0, min(100.0, total_score))

    # 11. Phân tầng chất lượng (Confidence Tiering)
    if total_score >= 80.0:
        confidence_tier = "TIER_1_STRONG"
    elif total_score >= 65.0:
        confidence_tier = "TIER_2_MODERATE"
    elif total_score >= 50.0:
        confidence_tier = "TIER_3_WEAK"
    else:
        confidence_tier = "REJECT"

    # Mức độ tự tin (Confidence level tương thích ngược)
    if total_score >= 70.0:
        confidence = "HIGH"
    elif total_score >= 50.0:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    factor_breakdown = {
        "trend_score": trend_score,
        "structure_score": structure_score,
        "indicator_score": indicator_score,
        "rr_score": rr_score,
        "volatility_score": volatility_score,
        "regime_score": regime_score,
        "session_score": session_score,
        "volume_score": volume_score,
        "setup_perf_score": setup_perf_score,
        "feedback_score": feedback_score,
        "weighted_base": round(weighted_base, 1),
        "total_score": total_score,
        "confidence_tier": confidence_tier,
        "confidence": confidence,
        "session_name": session_name,
        "regime_name": regime_name,
        "dynamic_weights": weights,
        "details": details,
    }

    breakdown = ScoreBreakdown(
        trend_score=trend_score,
        structure_score=structure_score,
        indicator_score=indicator_score,
        rr_score=rr_score,
        volatility_score=volatility_score,
        regime_score=regime_score,
        session_score=session_score,
        volume_score=volume_score,
        setup_perf_score=setup_perf_score,
        total_score=total_score,
        confidence=confidence,
        confidence_tier=confidence_tier,
        dynamic_weights=weights,
        factor_breakdown=factor_breakdown,
        details=details,
    )

    log.debug("Evaluated signal score: %s", breakdown)
    return breakdown
