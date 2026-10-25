# -*- coding: utf-8 -*-
"""Unit tests for Signal Quality Classifier."""

import os
import pandas as pd
import numpy as np
import pytest

from app.ml.features import FEATURE_NAMES
from app.ml.model import SignalQualityClassifier


def make_dummy_data(n: int = 50):
    np.random.seed(42)
    data = {name: np.random.normal(0, 1, n) for name in FEATURE_NAMES}
    df = pd.DataFrame(data)
    y = pd.Series([1 if i % 2 == 0 else 0 for i in range(n)])
    return df, y


def test_train_and_evaluate():
    X, y = make_dummy_data(60)
    clf = SignalQualityClassifier(model_version="test-v1", n_estimators=10)
    clf.train(X.iloc[:40], y.iloc[:40])
    assert clf.is_trained is True

    metrics = clf.evaluate(X.iloc[40:], y.iloc[40:])
    assert metrics.sample_size == 20
    assert 0.0 <= metrics.accuracy <= 1.0


def test_predict_confidence():
    X, y = make_dummy_data(40)
    clf = SignalQualityClassifier(model_version="test-v1", n_estimators=10)
    clf.train(X, y)

    sample_dict = {name: 0.5 for name in FEATURE_NAMES}
    conf = clf.predict_confidence(sample_dict)
    assert 0.0 <= conf <= 1.0


def test_save_and_load(tmp_path):
    X, y = make_dummy_data(30)
    clf = SignalQualityClassifier(model_version="saved-v1", n_estimators=10)
    clf.train(X, y)

    save_file = str(tmp_path / "test_model.joblib")
    clf.save(save_file)
    assert os.path.exists(save_file)

    loaded = SignalQualityClassifier.load(save_file)
    assert loaded is not None
    assert loaded.model_version == "saved-v1"
    assert loaded.is_trained is True
