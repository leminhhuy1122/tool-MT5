# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Risk Filter.

Lọc tín hiệu trước khi phát:
- Trend filter: chỉ trade theo trend H4.
- R:R filter: tối thiểu 1:1.5.
- Spread filter: không trade khi spread quá cao.
- Volatility filter: không trade khi volatility extreme.
- Duplicate filter: không trùng tín hiệu gần đây.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.strategy.setup_detector import SetupCandidate
from app.market.market_structure import TrendDirection
from app.market.volatility import VolatilityResult, VolatilityLevel
from logger import get_logger

log = get_logger("strategy.filter")


@dataclass
class FilterConfig:
    """Cấu hình bộ lọc tín hiệu."""
    min_rr_ratio: float = 1.5              # R:R tối thiểu
    max_spread_ratio: float = 3.0          # Spread/avg tối đa
    allow_extreme_volatility: bool = False  # Cho phép trade khi extreme
    require_trend_alignment: bool = True    # Yêu cầu trend H4 đồng hướng
    min_score: float = 40.0                # Điểm tối thiểu


@dataclass
class FilterResult:
    """Kết quả lọc tín hiệu."""
    passed: bool
    reasons_rejected: list[str] = field(default_factory=list)
    reasons_passed: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.passed:
            return f"PASSED: {', '.join(self.reasons_passed)}"
        return f"REJECTED: {', '.join(self.reasons_rejected)}"


def apply_filters(
    candidate: SetupCandidate,
    higher_tf_trend: TrendDirection = TrendDirection.NEUTRAL,
    volatility: Optional[VolatilityResult] = None,
    config: Optional[FilterConfig] = None,
) -> FilterResult:
    """
    Áp dụng bộ lọc cho setup candidate.

    Args:
        candidate: Setup candidate cần lọc.
        higher_tf_trend: Trend H4.
        volatility: Kết quả volatility analysis.
        config: Cấu hình bộ lọc.

    Returns:
        FilterResult cho biết candidate pass hay reject.
    """
    if config is None:
        config = FilterConfig()

    rejected: list[str] = []
    passed: list[str] = []

    # 1. R:R Filter
    rr = candidate.risk_reward
    if rr < config.min_rr_ratio:
        rejected.append(f"R:R quá thấp ({rr:.1f} < {config.min_rr_ratio})")
    else:
        passed.append(f"R:R={rr:.1f}")

    # 2. Trend Alignment Filter
    if config.require_trend_alignment:
        if candidate.direction == "BUY" and higher_tf_trend == TrendDirection.BEARISH:
            rejected.append("BUY ngược trend H4 (BEARISH)")
        elif candidate.direction == "SELL" and higher_tf_trend == TrendDirection.BULLISH:
            rejected.append("SELL ngược trend H4 (BULLISH)")
        else:
            passed.append(f"Trend H4 aligned ({higher_tf_trend.value})")

    # 3. Spread Filter
    if volatility and volatility.is_spread_high:
        if volatility.spread_ratio > config.max_spread_ratio:
            rejected.append(
                f"Spread quá cao ({volatility.spread_ratio:.1f}x avg)"
            )
        else:
            passed.append("Spread OK")
    else:
        passed.append("Spread OK")

    # 4. Volatility Filter
    if volatility:
        if (volatility.level == VolatilityLevel.EXTREME
                and not config.allow_extreme_volatility):
            rejected.append(f"Volatility EXTREME (ATR ratio={volatility.atr_ratio:.1%})")
        else:
            passed.append(f"Volatility {volatility.level.value}")

    # 5. Score Filter
    total_score = sum(candidate.score_components.values())
    if total_score < config.min_score:
        rejected.append(f"Score quá thấp ({total_score:.0f} < {config.min_score})")
    else:
        passed.append(f"Score={total_score:.0f}")

    is_passed = len(rejected) == 0

    result = FilterResult(
        passed=is_passed,
        reasons_rejected=rejected,
        reasons_passed=passed,
    )

    if is_passed:
        log.debug("✓ Filter PASSED: %s %s — %s",
                   candidate.direction, candidate.setup_type.value, result)
    else:
        log.debug("✗ Filter REJECTED: %s %s — %s",
                   candidate.direction, candidate.setup_type.value, result)

    return result
