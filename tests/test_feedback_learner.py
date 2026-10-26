# -*- coding: utf-8 -*-
"""
Unit tests for Self-Learning Feedback Engine & Root Cause Analysis (Phase 8).
"""

import json
from unittest.mock import MagicMock
import pytest

from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.database.repository import SignalRepository
from app.market.market_structure import MarketStructureResult, TrendDirection
from app.market.regime import MarketRegime, MarketRegimeResult, RegimeBias, RegimeMetrics, VolatilityState
from app.strategy.feedback_learner import (
    RootCause,
    SelfLearningFeedbackEngine,
    TradeOutcomeAnalysis,
    TradeOutcomeAnalyzer,
)
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_scoring import calculate_signal_score


@pytest.fixture
def memory_db():
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)
    return db


class TestTradeOutcomeAnalyzer:
    """Test suite cho TradeOutcomeAnalyzer (phân loại nguyên nhân TP/SL)."""

    def test_analyze_tp_clean_trend(self):
        sig = TradingSignal(
            signal_id="sig_tp_1",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit_1=2720.0,
            setup_type="BOS_RETEST",
            sl_distance=10.0,
        )
        res = TradeOutcomeAnalyzer.analyze(
            signal=sig,
            final_status="TP_REACHED",
            exit_price=2720.0,
            duration_seconds=3600,
        )
        assert res.root_cause == RootCause.CLEAN_TREND_RUN
        assert res.pnl_points == 20.0
        assert res.pnl_r == 2.0
        assert "mượt mà" in res.explanation

    def test_analyze_tp_momentum_surge(self):
        sig = TradingSignal(
            signal_id="sig_tp_2",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit_1=2715.0,
            setup_type="BOS_RETEST",
            sl_distance=10.0,
        )
        res = TradeOutcomeAnalyzer.analyze(
            signal=sig,
            final_status="TP_REACHED",
            exit_price=2715.0,
            duration_seconds=300,  # 5 phút -> Momentum surge
        )
        assert res.root_cause == RootCause.MOMENTUM_SURGE
        assert "bùng nổ" in res.explanation

    def test_analyze_tp_liquidity_reversal(self):
        sig = TradingSignal(
            signal_id="sig_tp_3",
            direction=SignalDirection.SELL,
            entry_price=2730.0,
            stop_loss=2740.0,
            take_profit_1=2710.0,
            setup_type="SMC_LIQUIDITY_SWEEP",
            sl_distance=10.0,
        )
        res = TradeOutcomeAnalyzer.analyze(
            signal=sig,
            final_status="TP_REACHED",
            exit_price=2710.0,
            duration_seconds=1800,
        )
        assert res.root_cause == RootCause.LIQUIDITY_REVERSAL
        assert res.pnl_points == 20.0

    def test_analyze_sl_news_spike(self):
        sig = TradingSignal(
            signal_id="sig_sl_news",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2692.0,
            sl_distance=8.0,
        )
        res = TradeOutcomeAnalyzer.analyze(
            signal=sig,
            final_status="SL_REACHED",
            exit_price=2692.0,
            is_near_news=True,
            news_title="Non-Farm Payrolls",
        )
        assert res.root_cause == RootCause.NEWS_SPIKE
        assert "Non-Farm Payrolls" in res.explanation

    def test_analyze_sl_candle_range_spike(self):
        sig = TradingSignal(
            signal_id="sig_sl_spike",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2692.0,
            sl_distance=8.0,
        )
        res = TradeOutcomeAnalyzer.analyze(
            signal=sig,
            final_status="SL_REACHED",
            exit_price=2692.0,
            current_candle_range=15.0,
            atr_value=4.0,  # 15.0 > 2.5 * 4.0 = 10.0
        )
        assert res.root_cause == RootCause.NEWS_SPIKE

    def test_analyze_sl_spread_widening(self):
        sig = TradingSignal(
            signal_id="sig_sl_spread",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2697.0,
            sl_distance=3.0,
        )
        res = TradeOutcomeAnalyzer.analyze(
            signal=sig,
            final_status="SL_REACHED",
            exit_price=2697.0,
            current_spread=1.5,  # 1.5 / 3.0 = 0.5 > 0.40
        )
        assert res.root_cause == RootCause.SPREAD_WIDENING


class TestSelfLearningFeedbackEngine:
    """Test suite cho SelfLearningFeedbackEngine."""

    def test_feedback_engine_empty_fallback(self):
        engine = SelfLearningFeedbackEngine(repository=None)
        adj = engine.get_feedback_adjustment(setup_type="BOS_RETEST", regime="TRENDING_BULLISH")
        assert adj["score_adjustment"] == 0.0
        assert adj["cushion_multiplier"] == 1.0

    def test_feedback_engine_learning_and_penalties(self):
        mock_repo = MagicMock()
        # Tạo mock 10 lệnh: 8 thua, 2 thắng cho SMC_ORDER_BLOCK trong HIGH_VOLATILITY (WR = 20%)
        outcomes = []
        for i in range(8):
            outcomes.append({
                "setup_type": "SMC_ORDER_BLOCK",
                "market_regime": "HIGH_VOLATILITY",
                "final_status": "SL_REACHED",
                "pnl_points": -10.0,
                "notes": json.dumps({"root_cause": RootCause.STRUCTURAL_FAILURE.value}),
            })
        for i in range(2):
            outcomes.append({
                "setup_type": "SMC_ORDER_BLOCK",
                "market_regime": "HIGH_VOLATILITY",
                "final_status": "TP_REACHED",
                "pnl_points": 15.0,
                "notes": json.dumps({"root_cause": RootCause.CLEAN_TREND_RUN.value}),
            })

        mock_repo.get_historical_outcomes.return_value = outcomes
        engine = SelfLearningFeedbackEngine(repository=mock_repo, min_samples_for_learning=5)

        adj = engine.get_feedback_adjustment(setup_type="SMC_ORDER_BLOCK", regime="HIGH_VOLATILITY")
        assert adj["score_adjustment"] == -10.0
        assert "Phạt -10 điểm" in adj["reason"]

    def test_feedback_engine_spread_cushion_adaptation(self):
        mock_repo = MagicMock()
        # Giả lập 6 lệnh thua, trong đó 3 lệnh do SPREAD_WIDENING (tỷ lệ 50% > 25%)
        outcomes = []
        for i in range(3):
            outcomes.append({
                "setup_type": "EMA_BOUNCE",
                "market_regime": "RANGING",
                "final_status": "SL_REACHED",
                "pnl_points": -5.0,
                "notes": json.dumps({"root_cause": RootCause.SPREAD_WIDENING.value}),
            })
        for i in range(3):
            outcomes.append({
                "setup_type": "EMA_BOUNCE",
                "market_regime": "RANGING",
                "final_status": "SL_REACHED",
                "pnl_points": -5.0,
                "notes": json.dumps({"root_cause": RootCause.NORMAL_LOSS.value}),
            })

        mock_repo.get_historical_outcomes.return_value = outcomes
        engine = SelfLearningFeedbackEngine(repository=mock_repo, min_samples_for_learning=5)

        report = engine.refresh()
        assert report["recommended_cushion_multiplier"] == 1.15
        assert report["spread_sl_ratio"] == 50.0

        adj = engine.get_feedback_adjustment(setup_type="EMA_BOUNCE", regime="RANGING")
        assert adj["cushion_multiplier"] == 1.15


class TestSignalScoringFeedbackIntegration:
    """Test suite tích hợp feedback_engine vào calculate_signal_score."""

    def test_scoring_with_feedback_penalty(self):
        candidate = SetupCandidate(
            setup_type=SetupType.SMC_ORDER_BLOCK,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2725.0,
            take_profit_1=2715.0,
            reasons=["OB Bullish"],
        )
        h1_structure = MarketStructureResult(
            trend=TrendDirection.BULLISH,
        )
        regime = MarketRegimeResult(
            regime=MarketRegime.HIGH_VOLATILITY_EXPANSION,
            confidence=0.85,
            bias=RegimeBias.BULLISH,
            reasons=["High Volatility"],
            cushion_multiplier=1.2,
            min_confluence_score=75.0,
            allowed_setups=[SetupType.SMC_ORDER_BLOCK],
            metrics=RegimeMetrics(
                adx=32.0,
                plus_di=25.0,
                minus_di=15.0,
                atr_value=6.5,
                atr_percentile=85.0,
                bb_width=15.0,
                bb_width_percentile=80.0,
                is_squeeze=False,
                ema_alignment="BULLISH",
                ema_slope_20=0.5,
            ),
        )

        mock_feedback = MagicMock()
        mock_feedback.get_feedback_adjustment.return_value = {
            "score_adjustment": -15.0,
            "cushion_multiplier": 1.0,
            "reason": "Self-Learning: Phạt -15 điểm do chuỗi thua trong High Volatility",
        }

        score_res = calculate_signal_score(
            candidate=candidate,
            h4_trend=TrendDirection.BULLISH,
            h1_structure=h1_structure,
            regime=regime,
            feedback_engine=mock_feedback,
        )

        assert score_res.factor_breakdown.get("feedback_score") == -15.0
        assert any("Self-Learning" in r for r in score_res.details)


class TestSignalRepositoryFeaturesPersistence:
    """Test suite cho SignalRepository lưu và đọc lại 21 đặc trưng kỹ thuật."""

    def test_save_and_retrieve_signal_features(self, memory_db):
        repo = SignalRepository(memory_db)
        sig = TradingSignal(
            signal_id="sig_test_feat",
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit_1=2720.0,
        )
        features = {
            "rsi_14": 58.5,
            "ema_20": 2695.0,
            "ema_50": 2685.0,
            "ema_200": 2650.0,
            "atr_14": 3.2,
            "spread": 0.25,
            "adx_14": 28.0,
            "bb_width_ratio": 1.15,
            "regime_encoded": 1.0,
            "session_liquidity_score": 1.0,
            "volume_surge_ratio": 1.8,
            "risk_reward_ratio": 2.0,
            "setup_historical_wr": 0.65,
        }

        saved = repo.save_signal(sig, features=features)
        assert saved is True

        retrieved = repo.get_signal_features("sig_test_feat")
        assert retrieved is not None
        assert retrieved["rsi_14"] == 58.5
        assert retrieved["atr_14"] == 3.2
        assert "full_features" in retrieved
        assert retrieved["full_features"]["adx_14"] == 28.0
        assert retrieved["full_features"]["volume_surge_ratio"] == 1.8
