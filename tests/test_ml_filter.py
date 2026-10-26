# -*- coding: utf-8 -*-
"""Unit tests for ML Signal Filter."""

import pytest
from app.ml.filter import MLSignalFilter
from app.ml.model import SignalQualityClassifier
from app.strategy.signal_models import SignalDirection, TradingSignal
from app.strategy.signal_engine import SignalEngine
from tests.test_ml_features import make_sample_df


def test_filter_inactive_fallback():
    # Model not trained -> signals pass unchanged
    filter_layer = MLSignalFilter(classifier=None)
    sig = TradingSignal(
        signal_id="S1",
        strategy_version="v1.0",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.BUY,
        entry_price=2700.0,
        score=75.0,
    )
    df = make_sample_df(30)
    out = filter_layer.apply(sig, df)
    assert out.direction == SignalDirection.BUY
    assert out.score == 75.0


def test_filter_low_confidence_rejection():
    class MockLowClassifier(SignalQualityClassifier):
        def __init__(self):
            self.model_version = "mock-low"
            self.is_trained = True
        def predict_confidence(self, features):
            return 0.20  # Below 0.35 min threshold

    filter_layer = MLSignalFilter(classifier=MockLowClassifier())
    sig = TradingSignal(
        signal_id="S2",
        strategy_version="v1.0",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.BUY,
        entry_price=2700.0,
        score=80.0,
    )
    df = make_sample_df(30)
    out = filter_layer.apply(sig, df)
    assert out.direction == SignalDirection.WAIT
    assert "ML Filter lọc bỏ" in out.reasons[0]


def test_filter_high_confidence_bonus():
    class MockHighClassifier(SignalQualityClassifier):
        def __init__(self):
            self.model_version = "mock-high"
            self.is_trained = True
        def predict_confidence(self, features):
            return 0.85  # Above 0.60 threshold

    filter_layer = MLSignalFilter(classifier=MockHighClassifier())
    sig = TradingSignal(
        signal_id="S3",
        strategy_version="v1.0",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.BUY,
        entry_price=2700.0,
        score=80.0,
        reasons=["Original Reason"],
    )
    df = make_sample_df(30)
    out = filter_layer.apply(sig, df)
    assert out.direction == SignalDirection.BUY
    assert out.score > 80.0
    assert any("ML Confirmation" in r for r in out.reasons)


def test_filter_preserves_phase2_to_5_fields():
    class MockHighClassifier(SignalQualityClassifier):
        def __init__(self):
            self.model_version = "mock-high"
            self.is_trained = True
        def predict_confidence(self, features):
            return 0.85

    filter_layer = MLSignalFilter(classifier=MockHighClassifier())
    sig = TradingSignal(
        signal_id="S4",
        setup_id="setup_OB_bull",
        strategy_version="v1.0",
        symbol="XAUUSD",
        timeframe="H1",
        direction=SignalDirection.BUY,
        entry_price=2700.0,
        entry_zone_low=2698.0,
        entry_zone_high=2702.0,
        stop_loss=2690.0,
        take_profit_1=2715.0,
        take_profit_2=2730.0,
        invalidation_level=2688.0,
        risk_reward_ratio=2.5,
        sl_distance=10.0,
        tp_distance=15.0,
        score=82.0,
        confidence="MEDIUM",
        market_regime="TRENDING_BULLISH",
        score_breakdown={"session_name": "NEW_YORK", "volume_surge": 1.7, "setup_historical_wr": 0.65},
        structure_context={"strong_high": 2750.0, "strong_low": 2680.0},
        reasons=["Order Block Bullish"],
    )
    df = make_sample_df(30)
    out = filter_layer.apply(sig, df)

    assert out.direction == SignalDirection.BUY
    assert out.setup_id == "setup_OB_bull"
    assert out.market_regime == "TRENDING_BULLISH"
    assert out.invalidation_level == 2688.0
    assert out.confidence == "HIGH"
    assert out.score > 82.0
    assert out.score_breakdown.get("ml_confidence") == 0.85
    assert out.score_breakdown.get("ml_approved") is True
    assert out.structure_context.get("ml_confidence") == 0.85
    assert out.structure_context.get("strong_high") == 2750.0


def test_filter_rejection_preserves_context():
    class MockLowClassifier(SignalQualityClassifier):
        def __init__(self):
            self.model_version = "mock-low"
            self.is_trained = True
        def predict_confidence(self, features):
            return 0.25

    filter_layer = MLSignalFilter(classifier=MockLowClassifier())
    sig = TradingSignal(
        signal_id="S5",
        setup_id="setup_FVG_bear",
        strategy_version="v1.0",
        symbol="XAUUSD",
        timeframe="H1",
        direction=SignalDirection.SELL,
        entry_price=2720.0,
        entry_zone_low=2718.0,
        entry_zone_high=2722.0,
        stop_loss=2730.0,
        take_profit_1=2705.0,
        invalidation_level=2735.0,
        risk_reward_ratio=2.0,
        score=78.0,
        market_regime="HIGH_VOLATILITY",
        score_breakdown={"session_name": "LONDON"},
        structure_context={"regime": "HIGH_VOLATILITY"},
        reasons=["FVG Retest"],
    )
    df = make_sample_df(30)
    out = filter_layer.apply(sig, df)

    assert out.direction == SignalDirection.WAIT
    assert out.setup_id == "setup_FVG_bear"
    assert out.market_regime == "HIGH_VOLATILITY"
    assert out.invalidation_level == 2735.0
    assert out.score_breakdown.get("ml_confidence") == 0.25
    assert out.score_breakdown.get("ml_rejected") is True
    assert out.structure_context.get("ml_rejected") is True
    assert any("ML Filter lọc bỏ" in r for r in out.reasons)


def test_signal_engine_ml_filter_rejection():
    from tests.test_signal_engine import _make_zigzag_uptrend_df
    from app.market.indicators import add_all_indicators

    class MockRejectClassifier(SignalQualityClassifier):
        def __init__(self):
            self.model_version = "mock-rej"
            self.is_trained = True
        def predict_confidence(self, features):
            return 0.15

    filter_layer = MLSignalFilter(classifier=MockRejectClassifier())
    engine = SignalEngine(ml_filter=filter_layer)

    df = _make_zigzag_uptrend_df()
    df = add_all_indicators(df)

    last_idx = df.index[-1]
    prev_idx = df.index[-2]
    df.loc[prev_idx, "close"] = 145.1
    df.loc[last_idx, "close"] = 148.0
    df.loc[last_idx, "ema_20"] = 145.0
    df.loc[last_idx, "ema_50"] = 135.0
    df.loc[last_idx, "rsi_14"] = 50.0
    df.loc[last_idx, "atr_14"] = 3.0

    h4_df = df.copy()

    sig = engine.generate_signal(df=df, h4_df=h4_df)
    assert sig.direction == SignalDirection.WAIT
    assert any("ML Filter" in r for r in sig.reasons)


def test_signal_engine_ml_filter_approval():
    from tests.test_signal_engine import _make_zigzag_uptrend_df
    from app.market.indicators import add_all_indicators

    class MockApproveClassifier(SignalQualityClassifier):
        def __init__(self):
            self.model_version = "mock-app"
            self.is_trained = True
        def predict_confidence(self, features):
            return 0.88

    filter_layer = MLSignalFilter(classifier=MockApproveClassifier())
    engine = SignalEngine(ml_filter=filter_layer)

    df = _make_zigzag_uptrend_df()
    df = add_all_indicators(df)

    last_idx = df.index[-1]
    prev_idx = df.index[-2]
    df.loc[prev_idx, "close"] = 145.1
    df.loc[last_idx, "close"] = 148.0
    df.loc[last_idx, "ema_20"] = 145.0
    df.loc[last_idx, "ema_50"] = 135.0
    df.loc[last_idx, "rsi_14"] = 50.0
    df.loc[last_idx, "atr_14"] = 3.0

    h4_df = df.copy()

    sig = engine.generate_signal(df=df, h4_df=h4_df)
    assert sig.direction == SignalDirection.BUY
    assert any("ML Confirmation" in r for r in sig.reasons)
    assert sig.score_breakdown.get("ml_approved") is True


