# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Signal Scoring.
"""

from datetime import datetime, timezone
import pandas as pd
import pytest

from app.market.market_structure import (
    MarketStructureResult,
    StructureBreak,
    StructureEvent,
    TrendDirection,
)
from app.market.regime import MarketRegime, MarketRegimeResult, RegimeBias, VolatilityState
from app.market.volatility import VolatilityLevel, VolatilityResult
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_models import SignalDirection, TradingSignal
from app.strategy.signal_scoring import (
    ScoreBreakdown,
    calculate_signal_score,
    calculate_volume_factor,
    get_gold_session,
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

    def test_gold_session_timing_scores(self):
        """Kiểm tra điểm cộng/trừ theo từng phiên giao dịch Vàng (UTC)."""
        # Overlap London - New York (14:00 UTC) -> +5.0
        s_overlap, score_overlap, desc_overlap = get_gold_session(datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc))
        assert s_overlap == "LONDON_NY_OVERLAP"
        assert score_overlap == 5.0

        # London Open (09:00 UTC) -> +3.0
        s_london, score_london, _ = get_gold_session(datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc))
        assert s_london == "LONDON_OPEN"
        assert score_london == 3.0

        # NY Afternoon (17:00 UTC) -> +2.0
        s_ny, score_ny, _ = get_gold_session(datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc))
        assert s_ny == "NY_AFTERNOON"
        assert score_ny == 2.0

        # Asian Session (04:00 UTC) -> 0.0
        s_asia, score_asia, _ = get_gold_session(datetime(2026, 10, 26, 4, 0, tzinfo=timezone.utc))
        assert s_asia == "ASIAN_SESSION"
        assert score_asia == 0.0

        # Dead Hours (22:00 UTC) -> -3.0
        s_dead, score_dead, _ = get_gold_session(datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc))
        assert s_dead == "DEAD_HOURS"
        assert score_dead == -3.0

        # Mặc định None -> 0.0
        s_def, score_def, _ = get_gold_session(None)
        assert s_def == "DEFAULT"
        assert score_def == 0.0

    def test_volume_delta_factor(self):
        """Kiểm tra phân tích volume surge và volume dry-up."""
        # Tạo df 25 nến với volume bình thường 100, nến cuối bùng nổ 200 (2.0x MA20)
        vols = [100.0] * 24 + [200.0]
        df_surge = pd.DataFrame({"tick_volume": vols})
        score_surge, desc_surge = calculate_volume_factor(df_surge, setup_type="BOS_RETEST")
        assert score_surge == 4.0
        assert "Volume bùng nổ" in desc_surge

        # Nến cuối 140 (1.4x MA20) -> +2.0
        vols_conf = [100.0] * 24 + [140.0]
        df_conf = pd.DataFrame({"tick_volume": vols_conf})
        score_conf, desc_conf = calculate_volume_factor(df_conf, setup_type="BOS_RETEST")
        assert score_conf == 2.0
        assert "Volume gia tăng" in desc_conf

        # Nến cuối cạn kiệt 50 (0.5x MA20) trên setup BOS -> -2.0
        vols_dry = [100.0] * 24 + [50.0]
        df_dry = pd.DataFrame({"tick_volume": vols_dry})
        score_dry, desc_dry = calculate_volume_factor(df_dry, setup_type="BOS_RETEST")
        assert score_dry == -2.0
        assert "Cảnh báo volume thấp" in desc_dry

    def test_dynamic_weights_by_regime(self):
        """Kiểm tra trọng số động thay đổi theo Market Regime."""
        cand = _create_candidate(direction="BUY", entry=2000.0, sl=1990.0, tp=2025.0)

        from app.market.regime import RegimeMetrics

        metrics_sample = RegimeMetrics(
            adx=30.0,
            plus_di=25.0,
            minus_di=15.0,
            atr_value=3.0,
            atr_percentile=50.0,
            bb_width=10.0,
            bb_width_percentile=50.0,
            is_squeeze=False,
            ema_alignment="BULLISH",
            ema_slope_20=0.05,
        )

        # Regime TRENDING_BULLISH: Trọng số Trend 30%, Structure 25%
        regime_trending = MarketRegimeResult(
            regime=MarketRegime.TRENDING_BULLISH,
            confidence=0.85,
            bias=RegimeBias.BULLISH,
            metrics=metrics_sample,
            min_confluence_score=65.0,
            cushion_multiplier=1.0,
            reasons=["Strong Bullish Trend"],
        )
        score_trend = calculate_signal_score(
            candidate=cand,
            h4_trend=TrendDirection.BULLISH,
            regime=regime_trending,
            current_time=datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc),  # Overlap +5
        )
        assert score_trend.dynamic_weights["trend"] == 0.30
        assert score_trend.dynamic_weights["structure"] == 0.25
        assert score_trend.dynamic_weights["volatility"] == 0.10
        assert score_trend.session_score == 5.0

        # Regime RANGING: Trọng số Structure 35%, Trend 10%
        regime_ranging = MarketRegimeResult(
            regime=MarketRegime.RANGING,
            confidence=0.80,
            bias=RegimeBias.NEUTRAL,
            metrics=metrics_sample,
            min_confluence_score=60.0,
            cushion_multiplier=0.8,
            reasons=["Ranging Market"],
        )
        score_range = calculate_signal_score(
            candidate=cand,
            regime=regime_ranging,
        )
        assert score_range.dynamic_weights["structure"] == 0.35
        assert score_range.dynamic_weights["trend"] == 0.10

    def test_confidence_tiering(self):
        """Kiểm tra phân tầng chất lượng (TIER_1_STRONG, TIER_2_MODERATE, TIER_3_WEAK, REJECT)."""
        # Tier 1 Strong (>= 80.0)
        cand_strong = _create_candidate(direction="BUY", entry=2000.0, sl=1990.0, tp=2025.0)
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
            current_atr=3.0, avg_atr=3.0, atr_ratio=1.0, level=VolatilityLevel.NORMAL,
            current_spread=20.0, avg_spread=20.0, spread_ratio=1.0, is_spread_high=False,
        )
        score_t1 = calculate_signal_score(
            candidate=cand_strong,
            h4_trend=TrendDirection.BULLISH,
            h1_structure=h1_struct,
            volatility=vol,
            current_time=datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc),  # Overlap +5
        )
        assert score_t1.total_score >= 80.0
        assert score_t1.confidence_tier == "TIER_1_STRONG"
        assert score_t1.confidence == "HIGH"

        # Tier Reject (< 50.0)
        cand_weak = _create_candidate(
            direction="BUY", entry=2000.0, sl=1990.0, tp=2005.0,  # RR = 0.5
            score_components={"ema": 0, "rsi": 0},
        )
        score_rej = calculate_signal_score(
            candidate=cand_weak,
            h4_trend=TrendDirection.BEARISH,
            current_time=datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc),  # Dead hours -3
        )
        assert score_rej.total_score < 50.0
        assert score_rej.confidence_tier == "REJECT"
        assert score_rej.confidence == "LOW"

    def test_factor_breakdown_dictionary(self):
        """Kiểm tra tính đầy đủ và minh bạch của dictionary factor_breakdown."""
        cand = _create_candidate()
        score = calculate_signal_score(cand)
        bd = score.factor_breakdown

        assert "trend_score" in bd
        assert "structure_score" in bd
        assert "indicator_score" in bd
        assert "rr_score" in bd
        assert "volatility_score" in bd
        assert "session_score" in bd
        assert "volume_score" in bd
        assert "total_score" in bd
        assert "confidence_tier" in bd
        assert "dynamic_weights" in bd
        assert "details" in bd

    def test_signal_serialization_with_score_breakdown(self):
        """Kiểm tra TradingSignal to_dict và from_dict lưu trữ và khôi phục score_breakdown."""
        cand = _create_candidate()
        score = calculate_signal_score(cand)

        sig = TradingSignal(
            signal_id="sig_test_100",
            direction=SignalDirection.BUY,
            symbol="XAUUSD",
            score=score.total_score,
            confidence=score.confidence,
            score_breakdown=score.factor_breakdown,
        )
        sig_dict = sig.to_dict()
        assert "score_breakdown" in sig_dict
        assert sig_dict["score_breakdown"]["confidence_tier"] == score.confidence_tier

        # Khôi phục từ dict
        restored = TradingSignal.from_dict(sig_dict)
        assert restored.score == sig.score
        assert restored.score_breakdown["confidence_tier"] == score.confidence_tier

