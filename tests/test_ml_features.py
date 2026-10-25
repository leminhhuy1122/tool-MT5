# -*- coding: utf-8 -*-
"""Unit tests for ML Feature Extractor."""

import pandas as pd
import numpy as np
import pytest

from app.ml.features import FeatureExtractor, FEATURE_NAMES


def make_sample_df(n: int = 30) -> pd.DataFrame:
    times = pd.date_range("2026-03-01 00:00:00", periods=n, freq="5min")
    prices = [2700.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "time": times,
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": [p + 0.2 for p in prices],
        "rsi": [55.0 for _ in range(n)],
        "ema_fast": prices,
        "ema_mid": [p - 1.0 for p in prices],
        "ema_slow": [p - 2.0 for p in prices],
        "atr": [2.5 for _ in range(n)],
    })


def test_extract_features_keys():
    df = make_sample_df(30)
    feats = FeatureExtractor.extract_features(df, candle_idx=-1, spread=0.3, h4_trend="BULLISH", h1_trend="BULLISH")
    for key in FEATURE_NAMES:
        assert key in feats, f"Missing feature: {key}"
    assert feats["h4_trend_encoded"] == 1.0
    assert feats["h1_trend_encoded"] == 1.0
    assert feats["rsi_14"] == 55.0


def test_extract_features_neutral_trend():
    df = make_sample_df(20)
    feats = FeatureExtractor.extract_features(df, candle_idx=5, spread=0.5, h4_trend="BEARISH", h1_trend="NEUTRAL")
    assert feats["h4_trend_encoded"] == -1.0
    assert feats["h1_trend_encoded"] == 0.0
