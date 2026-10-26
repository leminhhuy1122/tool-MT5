# -*- coding: utf-8 -*-
"""
Unit tests for Machine Learning Walk-Forward Evaluator (Phase 7).
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.features import FEATURE_NAMES
from app.ml.model import SignalQualityClassifier
from app.ml.walk_forward import (
    MLFoldResult,
    MLWalkForwardEvaluator,
    MLWalkForwardReport,
)


def make_synthetic_dataset(n_samples: int = 100, win_ratio: float = 0.55) -> tuple[pd.DataFrame, pd.Series]:
    """Tạo tập dữ liệu đặc trưng và nhãn giả lập cho bài test."""
    np.random.seed(42)
    rows = []
    labels = []

    for i in range(n_samples):
        # Tạo đặc trưng có tính tương quan nhẹ với nhãn
        label = 1 if np.random.rand() < win_ratio else 0
        feat = {name: float(np.random.randn()) for name in FEATURE_NAMES}

        # Tạo tín hiệu phân biệt cho mô hình học
        if label == 1:
            feat["rsi_14"] = float(np.random.uniform(50.0, 70.0))
            feat["risk_reward_ratio"] = float(np.random.uniform(2.0, 3.5))
            feat["volume_surge_ratio"] = float(np.random.uniform(1.2, 2.5))
        else:
            feat["rsi_14"] = float(np.random.uniform(30.0, 50.0))
            feat["risk_reward_ratio"] = float(np.random.uniform(1.0, 1.8))
            feat["volume_surge_ratio"] = float(np.random.uniform(0.5, 1.1))

        rows.append(feat)
        labels.append(label)

    X = pd.DataFrame(rows)[FEATURE_NAMES]
    y = pd.Series(labels, name="target")
    return X, y


class TestMLWalkForwardEvaluator:
    """Test suite cho ML Walk-Forward Evaluator."""

    def test_insufficient_samples_rejection(self):
        """Dữ liệu quá ít (< min_train + folds*min_test) phải từ chối an toàn."""
        X, y = make_synthetic_dataset(n_samples=15)
        evaluator = MLWalkForwardEvaluator(num_folds=3, min_train_samples=20, min_test_samples=8)

        report = evaluator.evaluate(
            classifier_factory=lambda: SignalQualityClassifier(model_version="test-short"),
            X=X,
            y=y,
        )

        assert report.num_folds == 0
        assert report.is_production_eligible is False
        assert any("không đủ" in r for r in report.rejection_reasons)

    def test_walk_forward_evaluation_execution(self):
        """Thực thi thành công quy trình Walk-Forward đa chu kỳ."""
        X, y = make_synthetic_dataset(n_samples=80, win_ratio=0.60)
        evaluator = MLWalkForwardEvaluator(
            num_folds=3,
            min_train_samples=30,
            min_test_samples=10,
        )

        report = evaluator.evaluate(
            classifier_factory=lambda: SignalQualityClassifier(model_version="test-wf-v1"),
            X=X,
            y=y,
            model_version="test-wf-v1",
        )

        assert report.num_folds == 3
        assert report.total_test_samples > 0
        assert len(report.folds) == 3
        assert report.avg_train_auc >= 0.50
        assert 0.0 <= report.avg_test_auc <= 1.0
        assert 0.0 <= report.avg_test_brier <= 1.0
        assert 0.0 <= report.consistency_rate <= 100.0

        # Kiểm tra chi tiết từng fold
        fold1 = report.folds[0]
        assert fold1.fold_index == 1
        assert fold1.train_sample_size >= 30
        assert fold1.test_sample_size >= 10
        assert fold1.to_dict()["fold_index"] == 1

    def test_report_summary_and_serialization(self):
        """Kiểm tra báo cáo tổng quan và định dạng dictionary."""
        X, y = make_synthetic_dataset(n_samples=70, win_ratio=0.55)
        evaluator = MLWalkForwardEvaluator(num_folds=3, min_train_samples=25, min_test_samples=10)

        report = evaluator.evaluate(
            classifier_factory=lambda: SignalQualityClassifier(model_version="test-wf-summary"),
            X=X,
            y=y,
            model_version="test-wf-summary",
        )

        summary_text = report.summary()
        assert "BÁO CÁO WALK-FORWARD ML" in summary_text
        assert "OOS ROC-AUC trung bình" in summary_text

        rep_dict = report.to_dict()
        assert rep_dict["model_version"] == "test-wf-summary"
        assert rep_dict["num_folds"] == 3
        assert "avg_test_auc" in rep_dict
        assert "folds" in rep_dict
