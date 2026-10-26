# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Comprehensive Verification Suite (Phase 11).

Kiểm thử hợp nhất 20 kịch bản định lượng & an toàn bắt buộc:
1. Signal conflict
2. Duplicate signal
3. Setup expiry
4. Setup invalidation
5. Market regime
6. Feature snapshot
7. Outcome calculation
8. R-Multiple
9. MFE/MAE
10. Data leakage
11. Chronological split
12. Performance aggregation
13. Model evaluation
14. Model versioning
15. Promotion rules
16. Rollback
17. Missing market data
18. Stale candles
19. Spread spike
20. Unknown regime
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.database.repository import SignalRepository
from app.market.data_manager import MarketDataManager
from app.market.market_structure import MarketStructureResult, TrendDirection
from app.market.regime import MarketRegime, MarketRegimeDetector, MarketRegimeResult, RegimeBias, RegimeMetrics
from app.market.timeframe_manager import Timeframe
from app.ml.features import FeatureExtractor
from app.ml.model import ModelMetrics, SignalQualityClassifier
from app.ml.registry import ModelRegistry, ModelStatus
from app.ml.walk_forward import MLFoldResult, MLWalkForwardEvaluator, MLWalkForwardReport
from app.strategy.conflict_resolver import ConflictDecision, ConflictResolver, ConflictType
from app.strategy.feedback_learner import RootCause, SelfLearningFeedbackEngine, TradeOutcomeAnalysis, TradeOutcomeAnalyzer
from app.strategy.performance_evaluator import SetupPerformanceEvaluator
from app.strategy.risk_filter import FilterConfig, apply_filters
from app.strategy.setup_adapter import SetupAdapterEngine
from app.strategy.setup_detector import SetupCandidate, SetupType, detect_setups
from app.strategy.signal_models import SetupLifecycleStatus, SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_tracker import SignalTracker, TrackerConfig


@pytest.fixture
def memory_db():
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)
    return db


@pytest.fixture
def synthetic_candles():
    data = []
    base_price = 2700.0
    for i in range(40):
        t = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=5 * i)
        o = base_price + i * 0.5
        h = o + 2.0
        l = o - 1.0
        c = o + 1.0
        data.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "tick_volume": 1200 + i * 10,
            "spread": 0.3,
            "atr_14": 2.5,
            "ema_20": o + 0.2,
            "ema_50": o - 1.0,
            "ema_200": o - 5.0,
            "rsi_14": 55.0,
            "adx_14": 28.0,
            "plus_di_14": 26.0,
            "minus_di_14": 14.0,
            "bb_width": 10.0,
        })
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


class TestPhase11ComprehensiveVerification:
    """Bộ kiểm thử hợp nhất 20 kịch bản định lượng cho Phase 11."""

    # 1. Signal conflict
    def test_01_signal_conflict(self):
        resolver = ConflictResolver()
        cand_buy = SetupCandidate(
            setup_type=SetupType.SMC_ORDER_BLOCK,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
            take_profit_1=2710.0,
        )
        cand_sell = SetupCandidate(
            setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
            direction="SELL",
            entry_price=2705.0,
            stop_loss=2715.0,
            take_profit=2685.0,
            take_profit_1=2695.0,
        )
        resolved, reason = resolver.resolve_candidate_conflicts(
            candidates=[cand_buy, cand_sell],
            h4_trend=TrendDirection.BULLISH,
            structure=MarketStructureResult(trend=TrendDirection.BULLISH),
        )
        assert len(resolved) == 1
        assert resolved[0].direction == "BUY"
        assert "xung đột" in reason.lower()
        assert "Bullish" in reason

    # 2. Duplicate signal
    def test_02_duplicate_signal(self):
        tracker = SignalTracker(config=TrackerConfig(cooldown_minutes=30))
        sig1 = TradingSignal(
            signal_id="sig_active_1",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            entry_zone_low=2699.0,
            entry_zone_high=2701.0,
            stop_loss=2690.0,
            take_profit_1=2715.0,
            status=SignalStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )
        tracker.register_signal(sig1)

        candidate = SetupCandidate(
            setup_type=SetupType.SMC_ORDER_BLOCK,
            direction="BUY",
            entry_price=2701.0,
            stop_loss=2691.0,
            take_profit=2721.0,
        )
        decision = tracker.check_conflict(
            candidate=candidate,
            h4_trend=TrendDirection.BULLISH,
            structure=MarketStructureResult(trend=TrendDirection.BULLISH),
            current_price=2701.0,
        )
        assert decision.should_emit is False
        assert decision.conflict_type == ConflictType.DUPLICATE_ACTIVE

    # 3. Setup expiry
    def test_03_setup_expiry(self):
        tracker = SignalTracker(config=TrackerConfig(max_active_signals=5))
        past_time = datetime.now(timezone.utc) - timedelta(hours=3)
        expiry_time = past_time + timedelta(hours=1)
        sig = TradingSignal(
            signal_id="sig_expiring",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            entry_zone_low=2699.0,
            entry_zone_high=2701.0,
            stop_loss=2690.0,
            take_profit_1=2715.0,
            status=SignalStatus.ACTIVE,
            created_at=past_time,
            expires_at=expiry_time,
        )
        tracker.register_signal(sig)
        changed = tracker.update_price(current_price=2695.0, current_time=datetime.now(timezone.utc))
        assert sig.status == SignalStatus.EXPIRED
        assert any(s.signal_id == "sig_expiring" for s in changed)

    # 4. Setup invalidation
    def test_04_setup_invalidation(self):
        tracker = SignalTracker()
        sig = TradingSignal(
            signal_id="sig_invalid",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            entry_zone_low=2699.0,
            entry_zone_high=2701.0,
            stop_loss=2690.0,
            invalidation_level=2688.0,
            status=SignalStatus.ACTIVE,
        )
        tracker.register_signal(sig)
        changed = tracker.update_price(current_price=2687.0)
        assert sig.status == SignalStatus.INVALIDATED

    # 5. Market regime
    def test_05_market_regime(self, synthetic_candles):
        detector = MarketRegimeDetector(adx_trend_threshold=22.0)
        res = detector.detect_regime(synthetic_candles)
        assert isinstance(res, MarketRegimeResult)
        assert res.regime in (
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
            MarketRegime.RANGING,
            MarketRegime.HIGH_VOLATILITY_EXPANSION,
            MarketRegime.COMPRESSION_SQUEEZE,
        )
        assert res.confidence > 0.5
        assert res.metrics.adx > 0

    # 6. Feature snapshot
    def test_06_feature_snapshot(self, memory_db, synthetic_candles):
        repo = SignalRepository(memory_db)
        features = FeatureExtractor.extract_features(synthetic_candles, spread=0.25)
        assert len(features) >= 15

        sig = TradingSignal(
            signal_id="sig_feat_snapshot",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit_1=2720.0,
        )
        repo.save_signal(sig, features=features)
        saved_feat = repo.get_signal_features("sig_feat_snapshot")
        assert saved_feat is not None
        assert "full_features" in saved_feat
        assert saved_feat["full_features"]["rsi_14"] == features["rsi_14"]
        assert saved_feat["full_features"]["spread_atr_ratio"] == features["spread_atr_ratio"]

    # 7. Outcome calculation
    def test_07_outcome_calculation(self):
        tracker = SignalTracker()
        sig = TradingSignal(
            signal_id="sig_outcome_test",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            entry_zone_low=2699.0,
            entry_zone_high=2701.0,
            stop_loss=2690.0,
            take_profit_1=2715.0,
            status=SignalStatus.ACTIVE,
        )
        tracker.register_signal(sig)
        # 1. Chạm entry -> ENTRY_REACHED
        tracker.update_price(current_price=2700.0)
        assert sig.status == SignalStatus.ENTRY_REACHED

        # 2. Chạm TP -> TP_REACHED
        tracker.update_price(current_price=2716.0)
        assert sig.status == SignalStatus.TP_REACHED

    # 8. R-Multiple
    def test_08_r_multiple(self):
        sig = TradingSignal(
            signal_id="sig_r_mult",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit_1=2720.0,
            sl_distance=10.0,
        )
        # Chạm TP2 (+20 giá với SL 10 giá -> +2.0R)
        analysis_win = TradeOutcomeAnalyzer.analyze(sig, "TP_REACHED", exit_price=2720.0, duration_seconds=600)
        assert analysis_win.pnl_r == 2.0
        assert analysis_win.pnl_points == 20.0

        # Chạm SL (-10 giá với SL 10 giá -> -1.0R)
        analysis_loss = TradeOutcomeAnalyzer.analyze(sig, "SL_REACHED", exit_price=2690.0, duration_seconds=300)
        assert analysis_loss.pnl_r == -1.0
        assert analysis_loss.pnl_points == -10.0

    # 9. MFE/MAE
    def test_09_mfe_mae(self, memory_db):
        repo = SignalRepository(memory_db)
        sig = TradingSignal(
            signal_id="sig_mfe_mae",
            direction=SignalDirection.BUY,
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit_1=2720.0,
            setup_type="SMC_ORDER_BLOCK",
        )
        repo.save_signal(sig)

        # Giả lập quỹ đạo giá: Entry 2700 -> chạy cao nhất 2712 (+12 MFE) -> chạy thấp nhất 2696 (-4 MAE)
        mfe = 2712.0 - 2700.0  # 12.0
        mae = 2700.0 - 2696.0  # 4.0
        repo.save_outcome(
            signal_id="sig_mfe_mae",
            final_status="TP_REACHED",
            entry_hit_price=2700.0,
            exit_price=2720.0,
            pnl_points=20.0,
            pnl_r=2.0,
            max_favorable_excursion=mfe,
            max_adverse_excursion=mae,
        )

        evaluator = SetupPerformanceEvaluator(repository=repo)
        metrics = evaluator.refresh()
        assert metrics["SMC_ORDER_BLOCK"].mfe_avg_points == 12.0
        assert metrics["SMC_ORDER_BLOCK"].mae_avg_points == 4.0

    # 10. Data leakage
    def test_10_data_leakage(self, synthetic_candles):
        # Trích xuất đặc trưng tại nến thứ 24 từ lịch sử sớm (<= 25 nến) và lịch sử muộn (35 nến)
        df_early = synthetic_candles.iloc[:25].copy()
        df_later = synthetic_candles.iloc[:35].copy()
        # Giả lập biến động lớn ở tương lai (nến 30-34)
        df_later.loc[30:, "rsi_14"] = 85.0
        df_later.loc[30:, "rsi"] = 85.0

        feats_at_24_early = FeatureExtractor.extract_features(df_early, candle_idx=-1)
        feats_at_24_later = FeatureExtractor.extract_features(df_later, candle_idx=24)

        # Đặc trưng tại nến 24 phải hoàn toàn đồng nhất, không bị rò rỉ dữ liệu tương lai
        assert feats_at_24_early["rsi_14"] == feats_at_24_later["rsi_14"]
        assert feats_at_24_early["close_ema20_ratio"] == feats_at_24_later["close_ema20_ratio"]

        # Nến 34 ở tương lai có giá trị khác biệt hoàn toàn
        feats_at_34 = FeatureExtractor.extract_features(df_later, candle_idx=-1)
        assert feats_at_34["rsi_14"] == 85.0
        assert feats_at_24_later["rsi_14"] != feats_at_34["rsi_14"]

    # 11. Chronological split
    def test_11_chronological_split(self):
        evaluator = MLWalkForwardEvaluator(num_folds=3, min_train_samples=20, min_test_samples=10)
        n_samples = 60
        clf = SignalQualityClassifier(model_version="test-wf", n_estimators=5)
        data = {f: np.random.randn(n_samples) for f in clf.feature_names}
        df_X = pd.DataFrame(data)
        s_y = pd.Series([0, 1] * (n_samples // 2))

        report = evaluator.evaluate(
            classifier_factory=lambda: SignalQualityClassifier(model_version="test-wf", n_estimators=5),
            X=df_X,
            y=s_y,
        )
        assert len(report.folds) > 0
        for fold in report.folds:
            # Nguyên tắc bất biến: train_end <= test_start (chuỗi thời gian đơn điệu tăng)
            assert fold.train_end_idx <= fold.test_start_idx
            assert fold.test_end_idx > fold.test_start_idx

    # 12. Performance aggregation
    def test_12_performance_aggregation(self, memory_db):
        repo = SignalRepository(memory_db)
        repo.save_signal(TradingSignal(signal_id="s1", setup_type="SMC_ORDER_BLOCK", market_regime="TRENDING_BULLISH"))
        repo.save_signal(TradingSignal(signal_id="s2", setup_type="SMC_ORDER_BLOCK", market_regime="TRENDING_BULLISH"))
        repo.save_outcome(signal_id="s1", final_status="TP_REACHED", pnl_points=15.0, pnl_r=1.5)
        repo.save_outcome(signal_id="s2", final_status="TP_REACHED", pnl_points=12.0, pnl_r=1.2)

        evaluator = SetupPerformanceEvaluator(repository=repo)
        metrics = evaluator.refresh()
        assert "SMC_ORDER_BLOCK" in metrics
        assert metrics["SMC_ORDER_BLOCK"].win_rate == 100.0
        assert metrics["SMC_ORDER_BLOCK"].sample_size == 2

    # 13. Model evaluation
    def test_13_model_evaluation(self):
        clf = SignalQualityClassifier(model_version="test-eval", n_estimators=10)
        data = {f: np.random.randn(20) for f in clf.feature_names}
        X = pd.DataFrame(data)
        y = pd.Series([1] * 10 + [0] * 10)
        clf.train(X, y)
        metrics = clf.evaluate(X, y)

        assert isinstance(metrics, ModelMetrics)
        assert 0.0 <= metrics.brier_score <= 1.0
        assert metrics.sample_size == 20

    # 14. Model versioning
    def test_14_model_versioning(self, memory_db):
        registry = ModelRegistry(memory_db)
        clf = SignalQualityClassifier(model_version="v2.0.0-phase11")
        metrics = ModelMetrics(
            accuracy=0.70, precision=0.72, recall=0.68, f1=0.70, roc_auc=0.75, brier_score=0.18, sample_size=50
        )

        registry.register_model(
            classifier=clf,
            file_path="models/v2.0.0-phase11.joblib",
            metrics=metrics,
            status=ModelStatus.CANDIDATE.value,
            description="Phase 11 verification model",
        )
        mod_info = registry.get_model_details("v2.0.0-phase11")
        assert mod_info is not None
        assert mod_info["status"] == "CANDIDATE"

    # 15. Promotion rules
    def test_15_promotion_rules(self, memory_db):
        registry = ModelRegistry(memory_db)
        clf = SignalQualityClassifier(model_version="v2.1.0-promote")
        metrics = ModelMetrics(
            accuracy=0.75, precision=0.80, recall=0.70, f1=0.75, roc_auc=0.82, brier_score=0.15, sample_size=40
        )

        registry.register_model(
            classifier=clf,
            file_path="models/v2.1.0-promote.joblib",
            metrics=metrics,
            status=ModelStatus.CANDIDATE.value,
        )
        success, msg = registry.promote_to_production("v2.1.0-promote")
        assert success is True

        mod_info = registry.get_model_details("v2.1.0-promote")
        assert mod_info is not None
        assert mod_info["status"] == "PRODUCTION"

    # 16. Rollback
    def test_16_rollback(self, memory_db):
        registry = ModelRegistry(memory_db)
        clf = SignalQualityClassifier(model_version="v2.2.0-degrade")
        metrics = ModelMetrics(
            accuracy=0.70, precision=0.70, recall=0.70, f1=0.70, roc_auc=0.75, brier_score=0.18, sample_size=30
        )
        registry.register_model(
            classifier=clf,
            file_path="models/v2.2.0-degrade.joblib",
            metrics=metrics,
            status=ModelStatus.PRODUCTION.value,
        )

        retired = registry.demote_to_retired("v2.2.0-degrade")
        assert retired is True
        mod_info = registry.get_model_details("v2.2.0-degrade")
        assert mod_info["status"] == "RETIRED"

    # 17. Missing market data
    def test_17_missing_market_data(self):
        empty_df = pd.DataFrame()
        adapter = SetupAdapterEngine()
        cand = SetupCandidate(
            setup_type=SetupType.SMC_ORDER_BLOCK,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
        )
        val_res = adapter.validate_and_adapt(cand, df=empty_df, regime_result=None)
        assert val_res is not None

        detector = MarketRegimeDetector()
        regime_res = detector.detect_regime(empty_df)
        assert regime_res.regime == MarketRegime.RANGING

    # 18. Stale candles
    def test_18_stale_candles(self, synthetic_candles):
        mgr = MarketDataManager("XAUUSD")
        last_t = synthetic_candles["time"].iloc[-1]

        with pytest.MonkeyPatch.context() as m:
            mock_rates = np.array([
                (int(last_t.timestamp()) - 300, 2700.0, 2702.0, 2699.0, 2701.0, 1000, 25, 0),
                (int(last_t.timestamp()), 2701.0, 2703.0, 2700.0, 2702.0, 500, 25, 0),
            ], dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8")])

            m.setattr("app.market.data_manager.mt5.copy_rates_from_pos", lambda *args: mock_rates)
            has_new, bar_dt = mgr.check_new_candle(Timeframe.M5, last_t)
            assert has_new is False

    # 19. Spread spike
    def test_19_spread_spike(self):
        mock_repo = MagicMock()
        mock_records = [
            {"final_status": "SL_REACHED", "notes": json.dumps({"root_cause": RootCause.SPREAD_WIDENING.value}), "setup_type": "SMC_ORDER_BLOCK", "market_regime": "HIGH_VOLATILITY_EXPANSION"},
            {"final_status": "SL_REACHED", "notes": json.dumps({"root_cause": RootCause.SPREAD_WIDENING.value}), "setup_type": "SMC_ORDER_BLOCK", "market_regime": "HIGH_VOLATILITY_EXPANSION"},
            {"final_status": "SL_REACHED", "notes": json.dumps({"root_cause": RootCause.SPREAD_WIDENING.value}), "setup_type": "SMC_ORDER_BLOCK", "market_regime": "HIGH_VOLATILITY_EXPANSION"},
            {"final_status": "SL_REACHED", "notes": json.dumps({"root_cause": RootCause.NORMAL_LOSS.value}), "setup_type": "SMC_ORDER_BLOCK", "market_regime": "HIGH_VOLATILITY_EXPANSION"},
            {"final_status": "SL_REACHED", "notes": json.dumps({"root_cause": RootCause.NORMAL_LOSS.value}), "setup_type": "SMC_ORDER_BLOCK", "market_regime": "HIGH_VOLATILITY_EXPANSION"},
        ]
        mock_repo.get_historical_outcomes.return_value = mock_records
        engine = SelfLearningFeedbackEngine(repository=mock_repo, min_samples_for_learning=5)
        engine.refresh()
        assert engine.cached_stats["recommended_cushion_multiplier"] == 1.15
        assert engine.cached_stats["spread_sl_ratio"] == 60.0
        adj = engine.get_feedback_adjustment("SMC_ORDER_BLOCK", "HIGH_VOLATILITY_EXPANSION")
        assert adj["cushion_multiplier"] == 1.15

    # 20. Unknown regime
    def test_20_unknown_regime(self):
        detector = MarketRegimeDetector()
        short_df = pd.DataFrame([{"close": 2700.0, "high": 2701.0, "low": 2699.0, "open": 2700.0}])
        res = detector.detect_regime(short_df)
        assert res.regime == MarketRegime.RANGING
        assert res.confidence == 0.5
        assert "Dữ liệu không đủ" in res.reasons[0]
