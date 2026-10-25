# -*- coding: utf-8 -*-
"""Unit tests for ML Model Registry."""

import pytest
from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.ml.model import ModelMetrics, SignalQualityClassifier
from app.ml.registry import ModelRegistry


@pytest.fixture
def memory_db():
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)
    return db


def test_registry_save_and_retrieve(memory_db):
    registry = ModelRegistry(memory_db)
    clf = SignalQualityClassifier(model_version="ML-v1.0")
    metrics = ModelMetrics(accuracy=0.75, precision=0.80, recall=0.70, f1=0.74, roc_auc=0.78, brier_score=0.15, sample_size=50)

    success = registry.register_model(clf, file_path="models/ml_v1.joblib", metrics=metrics)
    assert success is True

    eval_id = registry.record_evaluation("ML-v1.0", metrics, details={"comment": "Passed test"})
    assert eval_id > 0

    latest_path = registry.get_latest_production_model_path()
    assert latest_path == "models/ml_v1.joblib"


def test_is_eligible_for_production(memory_db):
    registry = ModelRegistry(memory_db)
    poor_metrics = ModelMetrics(accuracy=0.40, precision=0.35, recall=0.30, f1=0.32, roc_auc=0.45, brier_score=0.35, sample_size=5)
    good_metrics = ModelMetrics(accuracy=0.75, precision=0.70, recall=0.65, f1=0.67, roc_auc=0.72, brier_score=0.15, sample_size=40)

    assert registry.is_eligible_for_production(poor_metrics) is False
    assert registry.is_eligible_for_production(good_metrics) is True
