# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Signal Scoring.
"""

import pytest

from app.market.market_structure import (
    MarketStructureResult,
    StructureBreak,
    StructureEvent,
    TrendDirection,
)
from app.market.volatility import VolatilityLevel, VolatilityResult
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_scoring import (
    ScoreBreakdown,
    calculate_signal_score,
)


def _create_candidate(
    direction: str = "BUY",
    entry: float = 2000.0,
    sl: float = 1990.0,
    tp: float = 2025.0,  # RR = 2.5
    score_components: dict | None = None,
) -> SetupCandidate:
    return SetupCandidate(
        setup_type=SetupType.BOS_RETEST,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        score_components=score_components or {"ema": 10, "rsi": 10},
    )


class TestSignalScoring:
    """Test suite cho Signal Scoring."""

    def test_high_confluence_scoring_buy(self):
        """Setup BUY hội tụ đầy đủ yếu tố đạt điểm cao (HIGH confidence)."""
        cand = _create_candidate(direction="BUY", entry=2000.0, sl=1990.0, tp=2025.0)

        bos_event = StructureEvent(
            event_type=StructureBreak.BOS_BULLISH,
            index=10,
            price=2005.0,
            broken_level=2000.0,
        )
        h1_struct = MarketStructureResult(
            trend=TrendDirection.BULLISH,
            structure_events=[bos_event],
        )
        vol = VolatilityResult(
            current_atr=3.0,
            avg_atr=3.0,
            atr_ratio=1.0,
            level=VolatilityLevel.NORMAL,
            current_spread=20.0,
            avg_spread=20.0,
            spread_ratio=1.0,
            is_spread_high=False,
        )

        score = calculate_signal_score(
            candidate=cand,
            h4_trend=TrendDirection.BULLISH,
            h1_structure=h1_struct,
            volatility=vol,
        )

        assert score.total_score >= 70.0
        assert score.confidence == "HIGH"
        assert score.trend_score == 25.0  # 15 (H4) + 10 (H1)
        assert score.structure_score >= 15.0  # BOS Bullish
        assert score.indicator_score == 20.0  # EMA + RSI
        assert score.rr_score == 15.0         # RR >= 2.5
        assert score.volatility_score == 15.0  # NORMAL
        assert "Score:" in str(score)

    def test_sell_scoring_bearish_confluence(self):
        """Setup SELL với H4 Bearish và H1 Bearish đạt điểm cao."""
        cand = _create_candidate(
            direction="SELL", entry=2000.0, sl=2010.0, tp=1975.0  # RR = 2.5
        )
        bos_event = StructureEvent(
            event_type=StructureBreak.BOS_BEARISH,
            index=10,
            price=1995.0,
            broken_level=2000.0,
        )
        h1_struct = MarketStructureResult(
            trend=TrendDirection.BEARISH,
            structure_events=[bos_event],
        )

        score = calculate_signal_score(
            candidate=cand,
            h4_trend=TrendDirection.BEARISH,
            h1_structure=h1_struct,
        )

        assert score.trend_score == 25.0
        assert score.structure_score >= 15.0
        assert score.confidence in ("MEDIUM", "HIGH")

    def test_low_confluence_scoring(self):
        """Setup ngược xu hướng và R:R thấp bị chấm điểm LOW."""
        cand = _create_candidate(
            direction="BUY", entry=2000.0, sl=1990.0, tp=2005.0,  # RR = 0.5
            score_components={"ema": 0, "rsi": 0},
        )
        # H4 Bearish vs BUY candidate -> 0 trend score
        score = calculate_signal_score(
            candidate=cand,
            h4_trend=TrendDirection.BEARISH,
            h1_structure=MarketStructureResult(trend=TrendDirection.BEARISH),
        )

        assert score.trend_score == 0.0
        assert score.rr_score == 0.0
        assert score.total_score < 50.0
        assert score.confidence == "LOW"

    def test_volatility_score_levels(self):
        """Kiểm tra điểm số theo từng mức volatility."""
        cand = _create_candidate()

        def _get_vol(level: VolatilityLevel):
            return VolatilityResult(
                current_atr=3.0, avg_atr=3.0, atr_ratio=1.0, level=level,
                current_spread=20.0, avg_spread=20.0, spread_ratio=1.0, is_spread_high=False,
            )

        # NORMAL -> 15
        s_normal = calculate_signal_score(cand, volatility=_get_vol(VolatilityLevel.NORMAL))
        assert s_normal.volatility_score == 15.0

        # LOW -> 10
        s_low = calculate_signal_score(cand, volatility=_get_vol(VolatilityLevel.LOW))
        assert s_low.volatility_score == 10.0

        # HIGH -> 5
        s_high = calculate_signal_score(cand, volatility=_get_vol(VolatilityLevel.HIGH))
        assert s_high.volatility_score == 5.0

        # EXTREME -> 0
        s_extreme = calculate_signal_score(cand, volatility=_get_vol(VolatilityLevel.EXTREME))
        assert s_extreme.volatility_score == 0.0

    def test_score_never_exceeds_100(self):
        """Tổng điểm không bao giờ vượt quá 100."""
        cand = _create_candidate(
            score_components={"ema": 50, "rsi": 50, "bos": 50, "retest": 50}
        )
        score = calculate_signal_score(
            candidate=cand,
            h4_trend=TrendDirection.BULLISH,
            h1_structure=MarketStructureResult(trend=TrendDirection.BULLISH),
        )
        assert score.total_score <= 100.0
