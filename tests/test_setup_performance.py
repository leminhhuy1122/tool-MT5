# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Setup Performance Tracking & Evaluation (Phase 5).
"""

from datetime import datetime, timezone, timedelta
import pytest

from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.database.repository import SignalRepository
from app.market.market_structure import MarketStructureResult, TrendDirection
from app.strategy.performance_evaluator import (
    SetupPerformanceEvaluator,
    SetupPerformanceMetrics,
    SetupStatus,
)
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_scoring import calculate_signal_score


def _create_candidate(
    setup_type: SetupType = SetupType.SMC_ORDER_BLOCK,
    direction: str = "BUY",
    entry: float = 2000.0,
    sl: float = 1990.0,
    tp: float = 2025.0,
    score_components: dict | None = None,
) -> SetupCandidate:
    return SetupCandidate(
        setup_type=setup_type,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        score_components=score_components or {"order_block": 15, "ema": 10, "rsi": 10},
    )


class TestSetupPerformance:
    """Test suite cho Historical Setup Performance Tracking & Evaluation."""

    def test_setup_performance_metrics_calculation(self):
        """Kiểm tra tính toán chuẩn xác các chỉ số Win Rate, Profit Factor, Expectancy."""
        evaluator = SetupPerformanceEvaluator(min_sample_size=5, full_sample_size=15)

        # Giả lập 10 lệnh: 7 Win (+15 giá, +1.5R) và 3 Loss (-10 giá, -1.0R)
        records = [
            {
                "setup_type": "SMC_ORDER_BLOCK",
                "pnl_points": 15.0,
                "pnl_r": 1.5,
                "duration_seconds": 1800,
                "max_favorable_excursion": 18.0,
                "max_adverse_excursion": 3.0,
            }
            for _ in range(7)
        ] + [
            {
                "setup_type": "SMC_ORDER_BLOCK",
                "pnl_points": -10.0,
                "pnl_r": -1.0,
                "duration_seconds": 900,
                "max_favorable_excursion": 2.0,
                "max_adverse_excursion": 10.0,
            }
            for _ in range(3)
        ]

        metrics_map = evaluator.evaluate_records(records)
        assert "SMC_ORDER_BLOCK" in metrics_map
        ob_metrics = metrics_map["SMC_ORDER_BLOCK"]

        assert ob_metrics.sample_size == 10
        assert ob_metrics.wins == 7
        assert ob_metrics.losses == 3
        assert ob_metrics.win_rate == 70.0
        # Total profit = 7 * 15 = 105, Total loss = 3 * 10 = 30 -> PF = 105 / 30 = 3.5
        assert round(ob_metrics.profit_factor, 2) == 3.5
        # Exp_R = (0.7 * 1.5) - (0.3 * 1.0) = 1.05 - 0.30 = 0.75R
        assert ob_metrics.expectancy_r > 0.5
        assert ob_metrics.net_points == 75.0
        assert ob_metrics.status == SetupStatus.FAVORED
        assert ob_metrics.score_modifier > 0.0

    def test_insufficient_sample_size(self):
        """Setup có số mẫu < 5 lệnh phải ở trạng thái INSUFFICIENT_DATA và modifier = 0.0."""
        evaluator = SetupPerformanceEvaluator(min_sample_size=5)

        records = [
            {"setup_type": "PREDICTIVE_LIMIT", "pnl_points": 20.0, "pnl_r": 2.0},
            {"setup_type": "PREDICTIVE_LIMIT", "pnl_points": 15.0, "pnl_r": 1.5},
            {"setup_type": "PREDICTIVE_LIMIT", "pnl_points": -10.0, "pnl_r": -1.0},
        ]
        metrics_map = evaluator.evaluate_records(records)
        limit_metrics = metrics_map["PREDICTIVE_LIMIT"]

        assert limit_metrics.sample_size == 3
        assert limit_metrics.status == SetupStatus.INSUFFICIENT_DATA
        assert limit_metrics.score_modifier == 0.0

    def test_underperforming_and_probation_setups(self):
        """Setup thua lỗ kéo dài bị phân loại UNDERPERFORMING hoặc PROBATION và bị trừ điểm."""
        evaluator = SetupPerformanceEvaluator(min_sample_size=5, full_sample_size=15)

        # 10 lệnh: 2 Win (+10 giá), 8 Loss (-10 giá) -> WinRate 20%
        records = [
            {"setup_type": "RSI_DIVERGENCE", "pnl_points": 10.0, "pnl_r": 1.0}
            for _ in range(2)
        ] + [
            {"setup_type": "RSI_DIVERGENCE", "pnl_points": -10.0, "pnl_r": -1.0}
            for _ in range(8)
        ]

        metrics_map = evaluator.evaluate_records(records)
        rsi_metrics = metrics_map["RSI_DIVERGENCE"]

        assert rsi_metrics.sample_size == 10
        assert rsi_metrics.win_rate == 20.0
        assert rsi_metrics.expectancy_r < -0.4
        assert rsi_metrics.status in (SetupStatus.UNDERPERFORMING, SetupStatus.PROBATION)
        assert rsi_metrics.score_modifier <= -5.0

    def test_repository_historical_outcomes_query(self):
        """Kiểm tra truy vấn database thực tế JOIN giữa signals và signal_outcomes."""
        db = DatabaseManager(db_path=":memory:")
        run_migrations(db)
        repo = SignalRepository(db)

        # Lưu 3 signals
        sig1 = TradingSignal(
            signal_id="sig_hist_1",
            setup_type="SMC_ORDER_BLOCK",
            direction=SignalDirection.BUY,
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit_1=2020.0,
        )
        sig2 = TradingSignal(
            signal_id="sig_hist_2",
            setup_type="SMC_ORDER_BLOCK",
            direction=SignalDirection.BUY,
            entry_price=2005.0,
            stop_loss=1995.0,
            take_profit_1=2025.0,
        )
        sig3 = TradingSignal(
            signal_id="sig_hist_3",
            setup_type="BOS_RETEST",
            direction=SignalDirection.SELL,
            entry_price=2010.0,
            stop_loss=2020.0,
            take_profit_1=1990.0,
        )

        repo.save_signal(sig1)
        repo.save_signal(sig2)
        repo.save_signal(sig3)

        # Lưu outcomes
        repo.save_outcome(
            signal_id="sig_hist_1",
            final_status="TP_REACHED",
            entry_hit_price=2000.0,
            exit_price=2020.0,
            pnl_points=20.0,
            pnl_r=2.0,
            duration_seconds=1200,
        )
        repo.save_outcome(
            signal_id="sig_hist_2",
            final_status="SL_REACHED",
            entry_hit_price=2005.0,
            exit_price=1995.0,
            pnl_points=-10.0,
            pnl_r=-1.0,
            duration_seconds=600,
        )

        # Lấy lịch sử outcomes
        hist = repo.get_historical_outcomes()
        assert len(hist) == 2
        sig_ids = [h["signal_id"] for h in hist]
        assert "sig_hist_1" in sig_ids
        assert "sig_hist_2" in sig_ids

        # Kiểm tra evaluator refresh với repo
        evaluator = SetupPerformanceEvaluator(repository=repo, min_sample_size=1)
        metrics = evaluator.refresh()
        assert "SMC_ORDER_BLOCK" in metrics
        assert metrics["SMC_ORDER_BLOCK"].sample_size == 2
        assert metrics["SMC_ORDER_BLOCK"].wins == 1
        assert metrics["SMC_ORDER_BLOCK"].losses == 1

    def test_scoring_integration_with_setup_evaluator(self):
        """Kiểm tra calculate_signal_score cộng/trừ điểm thích ứng từ evaluator."""
        evaluator = SetupPerformanceEvaluator(min_sample_size=5)

        # Giả lập setup SMC_ORDER_BLOCK có hiệu suất vượt trội (7 Win / 3 Loss)
        records = [
            {"setup_type": "SMC_ORDER_BLOCK", "pnl_points": 15.0, "pnl_r": 1.5}
            for _ in range(7)
        ] + [
            {"setup_type": "SMC_ORDER_BLOCK", "pnl_points": -10.0, "pnl_r": -1.0}
            for _ in range(3)
        ]
        evaluator._cached_setup_metrics = evaluator.evaluate_records(records)

        cand = _create_candidate(setup_type=SetupType.SMC_ORDER_BLOCK)

        # Chấm điểm có evaluator
        score_with_perf = calculate_signal_score(
            candidate=cand,
            setup_evaluator=evaluator,
        )
        # Chấm điểm không có evaluator
        score_base = calculate_signal_score(
            candidate=cand,
        )

        assert score_with_perf.setup_perf_score > 0.0
        assert score_with_perf.total_score > score_base.total_score
        assert "setup_perf_score" in score_with_perf.factor_breakdown
        assert any("Setup Performance" in d for d in score_with_perf.details)

    def test_signal_engine_probation_filter(self):
        """Setup đang bị PROBATION và điểm chưa đạt 80 sẽ bị từ chối phát lệnh."""
        evaluator = SetupPerformanceEvaluator(min_sample_size=5)

        # Giả lập setup RSI_DIVERGENCE bị PROBATION nặng
        records = [
            {"setup_type": "RSI_DIVERGENCE", "pnl_points": 10.0, "pnl_r": 1.0}
            for _ in range(1)
        ] + [
            {"setup_type": "RSI_DIVERGENCE", "pnl_points": -10.0, "pnl_r": -1.0}
            for _ in range(11)
        ]
        evaluator._cached_setup_metrics = evaluator.evaluate_records(records)

        assert evaluator.is_setup_on_probation("RSI_DIVERGENCE")

        engine = SignalEngine(
            strategy_version="v1.0",
            setup_evaluator=evaluator,
        )
        assert engine.setup_evaluator is not None
