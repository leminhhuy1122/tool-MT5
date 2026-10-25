# -*- coding: utf-8 -*-
"""Unit tests for ML Signal Filter."""

import pytest
from app.ml.filter import MLSignalFilter
from app.ml.model import SignalQualityClassifier
from app.strategy.signal_models import SignalDirection, TradingSignal
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
