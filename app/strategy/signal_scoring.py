# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Signal Scoring.

Chấm điểm chất lượng setup giao dịch trên thang điểm 0-100.
LƯU Ý QUAN TRỌNG:
- Điểm số (Score) KHÔNG PHẢI là xác suất thắng (win probability).
- Điểm số phản ánh mức độ hội tụ các điều kiện kỹ thuật (confluence score).

Thang điểm cấu thành (tổng tối đa 100):
1. Trend Alignment (tối đa 25 điểm):
   - H4 trend đồng thuận: 15 điểm
   - H1 trend đồng thuận: 10 điểm
2. Market Structure (tối đa 25 điểm):
   - BOS / CHoCH xác nhận: 15 điểm
   - Retest vùng S/R hoặc Swing Point: 10 điểm
3. Technical Indicators (tối đa 20 điểm):
   - EMA alignment / bounce: 10 điểm
   - RSI ở vùng thuận lợi (không overbought/oversold bất lợi): 10 điểm
4. Risk / Reward Ratio (tối đa 15 điểm):
   - R:R >= 2.5: 15 điểm
   - R:R >= 2.0: 12 điểm
   - R:R >= 1.5: 8 điểm
5. Volatility Context (tối đa 15 điểm):
   - Volatility Normal / Moderate: 15 điểm
   - Volatility Low: 10 điểm
   - Volatility High: 5 điểm
   - Volatility Extreme: 0 điểm
"""

from dataclasses import dataclass, field
from typing import Optional

from app.market.market_structure import MarketStructureResult, TrendDirection
from app.market.volatility import VolatilityLevel, VolatilityResult
from app.strategy.setup_detector import SetupCandidate
from logger import get_logger

log = get_logger("strategy.scoring")


@dataclass
class ScoreBreakdown:
    """Chi tiết điểm số thành phần."""
    trend_score: float = 0.0          # Max 25
    structure_score: float = 0.0      # Max 25
    indicator_score: float = 0.0      # Max 20
    rr_score: float = 0.0             # Max 15
    volatility_score: float = 0.0     # Max 15
    total_score: float = 0.0          # Max 100
    confidence: str = "LOW"           # LOW / MEDIUM / HIGH
    details: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Score: {self.total_score:.1f}/100 ({self.confidence}) | "
            f"Trend: {self.trend_score:.0f}, Struct: {self.structure_score:.0f}, "
            f"Ind: {self.indicator_score:.0f}, RR: {self.rr_score:.0f}, "
            f"Vol: {self.volatility_score:.0f}"
        )


def calculate_signal_score(
    candidate: SetupCandidate,
    h4_trend: TrendDirection = TrendDirection.NEUTRAL,
    h1_structure: Optional[MarketStructureResult] = None,
    volatility: Optional[VolatilityResult] = None,
) -> ScoreBreakdown:
    """
    Tính điểm confluence cho setup candidate.

    Args:
        candidate: Setup candidate cần chấm điểm.
        h4_trend: Xu hướng khung H4.
        h1_structure: Kết quả cấu trúc khung H1.
        volatility: Kết quả phân tích biến động.

    Returns:
        ScoreBreakdown chứa tổng điểm và chi tiết từng tiêu chí.
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
        indicator_score = min(ema_comp + rsi_comp + pa_comp, 20.0)
        if indicator_score > 0:
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

    total_score = round(
        trend_score + structure_score + indicator_score + rr_score + volatility_score,
        1
    )
    total_score = max(0.0, min(100.0, total_score))

    # Xác định mức độ tự tin (Confidence level)
    if total_score >= 70.0:
        confidence = "HIGH"
    elif total_score >= 50.0:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    breakdown = ScoreBreakdown(
        trend_score=trend_score,
        structure_score=structure_score,
        indicator_score=indicator_score,
        rr_score=rr_score,
        volatility_score=volatility_score,
        total_score=total_score,
        confidence=confidence,
        details=details,
    )

    log.debug("Evaluated signal score: %s", breakdown)
    return breakdown
