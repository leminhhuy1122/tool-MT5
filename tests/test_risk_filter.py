# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Risk Filter.
"""

import pytest

from app.market.market_structure import TrendDirection
from app.market.volatility import VolatilityLevel, VolatilityResult
from app.strategy.risk_filter import (
    FilterConfig,
    FilterResult,
    apply_filters,
)
from app.strategy.setup_detector import SetupCandidate, SetupType


def _create_candidate(
    direction: str = "BUY",
    entry: float = 2000.0,
    sl: float = 1990.0,
    tp: float = 2020.0,
    score_components: dict | None = None,
) -> SetupCandidate:
    """Helper tạo SetupCandidate mẫu."""
    return SetupCandidate(
        setup_type=SetupType.EMA_BOUNCE,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        score_components=score_components or {"trend": 20, "ema": 20, "rsi": 15},
    )


def _create_volatility(
    level: VolatilityLevel = VolatilityLevel.NORMAL,
    spread_ratio: float = 1.0,
    is_spread_high: bool = False,
) -> VolatilityResult:
    """Helper tạo VolatilityResult mẫu."""
    return VolatilityResult(
        current_atr=3.0,
        avg_atr=3.0,
        atr_ratio=1.0,
        level=level,
        current_spread=20.0,
        avg_spread=20.0,
        spread_ratio=spread_ratio,
        is_spread_high=is_spread_high,
    )


class TestRiskFilter:
    """Test suite cho Risk Filter."""

    def test_ideal_setup_passes_all_filters(self):
        """Setup chuẩn thỏa mãn mọi điều kiện phải PASS."""
        cand = _create_candidate(direction="BUY", entry=2000.0, sl=1990.0, tp=2020.0)
        vol = _create_volatility()
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
            volatility=vol,
        )
        assert res.passed is True
        assert len(res.reasons_rejected) == 0
        assert "PASSED" in str(res)

    def test_rr_filter_rejection(self):
        """R:R < 1.5 phải bị loại."""
        # Entry 2000, SL 1990 (dist 10), TP 2010 (dist 10) -> R:R = 1.0 < 1.5
        cand = _create_candidate(direction="BUY", entry=2000.0, sl=1990.0, tp=2010.0)
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
        )
        assert res.passed is False
        assert any("R:R quá thấp" in r for r in res.reasons_rejected)
        assert "REJECTED" in str(res)

    def test_trend_alignment_buy_rejected_on_bearish_h4(self):
        """BUY ngược trend H4 (BEARISH) phải bị loại."""
        cand = _create_candidate(direction="BUY")
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BEARISH,
        )
        assert res.passed is False
        assert any("BUY ngược trend H4" in r for r in res.reasons_rejected)

    def test_trend_alignment_sell_rejected_on_bullish_h4(self):
        """SELL ngược trend H4 (BULLISH) phải bị loại."""
        cand = _create_candidate(
            direction="SELL", entry=2000.0, sl=2010.0, tp=1980.0
        )
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
        )
        assert res.passed is False
        assert any("SELL ngược trend H4" in r for r in res.reasons_rejected)

    def test_neutral_h4_trend_allowed(self):
        """Trend H4 NEUTRAL vẫn được phép trade nếu có setup."""
        cand = _create_candidate(direction="BUY")
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.NEUTRAL,
        )
        assert res.passed is True

    def test_spread_filter_rejection(self):
        """Spread cao bất thường (> 3.0x avg) phải bị loại."""
        cand = _create_candidate()
        vol = _create_volatility(spread_ratio=3.5, is_spread_high=True)
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
            volatility=vol,
        )
        assert res.passed is False
        assert any("Spread quá cao" in r for r in res.reasons_rejected)

    def test_extreme_volatility_rejection(self):
        """Volatility EXTREME phải bị loại trừ khi có config cho phép."""
        cand = _create_candidate()
        vol = _create_volatility(level=VolatilityLevel.EXTREME)

        # Mặc định: không cho phép
        res_default = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
            volatility=vol,
        )
        assert res_default.passed is False
        assert any("Volatility EXTREME" in r for r in res_default.reasons_rejected)

        # Config cho phép
        config = FilterConfig(allow_extreme_volatility=True)
        res_allowed = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
            volatility=vol,
            config=config,
        )
        assert res_allowed.passed is True

    def test_low_score_rejection(self):
        """Điểm thành phần < min_score (40) phải bị loại."""
        cand = _create_candidate(
            score_components={"trend": 10, "rsi": 10}  # total 20 < 40
        )
        res = apply_filters(
            candidate=cand,
            higher_tf_trend=TrendDirection.BULLISH,
        )
        assert res.passed is False
        assert any("Score quá thấp" in r for r in res.reasons_rejected)
