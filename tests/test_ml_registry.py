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


def test_model_status_lifecycle(memory_db):
    from app.ml.registry import ModelStatus
    registry = ModelRegistry(memory_db)

    clf1 = SignalQualityClassifier(model_version="ML-v1.1")
    clf2 = SignalQualityClassifier(model_version="ML-v1.2")

    # Register as DRAFT and CANDIDATE
    registry.register_model(clf1, file_path="models/v1_1.joblib", status=ModelStatus.DRAFT.value)
    registry.register_model(clf2, file_path="models/v1_2.joblib", status=ModelStatus.CANDIDATE.value)

    models = registry.list_models()
    v1_1 = next(m for m in models if m["version"] == "ML-v1.1")
    v1_2 = next(m for m in models if m["version"] == "ML-v1.2")

    assert v1_1["status"] == "DRAFT"
    assert v1_2["status"] == "CANDIDATE"

    # Promote ML-v1.2 with force=True
    promoted, msg = registry.promote_to_production("ML-v1.2", force=True)
    assert promoted is True

    # Active path should be ML-v1.2
    active_path = registry.get_latest_production_model_path()
    assert active_path == "models/v1_2.joblib"

    # Promote ML-v1.1 -> ML-v1.2 should become RETIRED
    promoted2, msg2 = registry.promote_to_production("ML-v1.1", force=True)
    assert promoted2 is True

    models_after = registry.list_models()
    v1_1_after = next(m for m in models_after if m["version"] == "ML-v1.1")
    v1_2_after = next(m for m in models_after if m["version"] == "ML-v1.2")

    assert v1_1_after["status"] == "PRODUCTION"
    assert v1_2_after["status"] == "RETIRED"


def test_promote_to_production_rejection_for_poor_model(memory_db):
    registry = ModelRegistry(memory_db)
    clf = SignalQualityClassifier(model_version="ML-vPoor")
    poor_metrics = ModelMetrics(accuracy=0.30, precision=0.25, recall=0.20, f1=0.22, roc_auc=0.40, brier_score=0.45, sample_size=5)

    registry.register_model(clf, file_path="models/poor.joblib", metrics=poor_metrics)

    # Promoting poor model without force must fail
    promoted, reason = registry.promote_to_production("ML-Poor", force=False)
    assert promoted is False
    assert "chưa đạt chuẩn" in reason or "Không tìm thấy" in reason

    promoted_actual, reason_actual = registry.promote_to_production("ML-vPoor", force=False)
    assert promoted_actual is False
    assert "chưa đạt chuẩn" in reason_actual


def test_record_walk_forward_evaluation(memory_db):
    from app.ml.walk_forward import MLWalkForwardReport
    registry = ModelRegistry(memory_db)

    clf = SignalQualityClassifier(model_version="ML-v2.0")
    good_metrics = ModelMetrics(accuracy=0.72, precision=0.70, recall=0.68, f1=0.69, roc_auc=0.74, brier_score=0.16, sample_size=40)
    registry.register_model(clf, file_path="models/v2_0.joblib", metrics=good_metrics)

    report = MLWalkForwardReport(
        model_version="ML-v2.0",
        num_folds=3,
        total_test_samples=45,
        avg_train_auc=0.82,
        avg_test_auc=0.71,
        avg_test_accuracy=0.70,
        avg_test_precision=0.68,
        avg_test_recall=0.65,
        avg_test_f1=0.66,
        avg_test_brier=0.17,
        avg_precision_high_conf=0.75,
        avg_degradation_ratio=0.13,
        consistency_rate=100.0,
        is_production_eligible=True,
    )

    eval_id = registry.record_walk_forward_evaluation("ML-v2.0", report)
    assert eval_id > 0

    details = registry.get_model_details("ML-v2.0")
    assert details is not None
    assert details["version"] == "ML-v2.0"
    assert len(details["evaluations"]) == 1
    assert details["evaluations"][0]["sample_size"] == 45

