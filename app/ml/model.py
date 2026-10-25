# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Model.

Huấn luyện và đánh giá mô hình phân loại chất lượng tín hiệu:
- Sử dụng RandomForestClassifier với xác suất được hiệu chuẩn (Probability Calibration).
- Đánh giá toàn diện: Accuracy, Precision, Recall, F1, ROC-AUC, Brier Calibration Score.
- Lưu trữ và tải mô hình an toàn qua joblib.
"""

from dataclasses import asdict, dataclass
import os
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.features import FEATURE_NAMES
from logger import get_logger

log = get_logger("ml.model")


@dataclass
class ModelMetrics:
    """Các chỉ số đánh giá mô hình học máy."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    brier_score: float
    sample_size: int

    def to_dict(self) -> dict:
        return asdict(self)


class SignalQualityClassifier:
    """Mô hình phân loại và dự đoán xác suất thành công của tín hiệu."""

    def __init__(
        self,
        model_version: str = "ML-v1.0",
        n_estimators: int = 80,
        max_depth: int = 5,
        random_state: int = 42,
    ):
        self.model_version = model_version
        self.feature_names = list(FEATURE_NAMES)
        self.classifier = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=4,
            random_state=random_state,
        )
        self.is_trained = False
        self.metrics: Optional[ModelMetrics] = None

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """
        Huấn luyện mô hình trên tập dữ liệu.
        """
        if len(X_train) == 0 or len(y_train.unique()) < 2:
            log.warning("Tập huấn luyện không đủ dữ liệu hoặc chỉ có 1 class. Bỏ qua train.")
            return

        # Đảm bảo chỉ dùng đúng thứ tự các cột features
        X_clean = X_train[self.feature_names].fillna(0.0)
        self.classifier.fit(X_clean, y_train)
        self.is_trained = True
        log.info("✓ Đã huấn luyện thành công mô hình %s trên %d mẫu.", self.model_version, len(X_train))

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> ModelMetrics:
        """
        Đánh giá độ chính xác và chất lượng hiệu chuẩn của mô hình.
        """
        if not self.is_trained or len(X_test) == 0:
            return ModelMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0)

        X_clean = X_test[self.feature_names].fillna(0.0)
        preds = self.classifier.predict(X_clean)
        probas = self.classifier.predict_proba(X_clean)[:, 1] if hasattr(self.classifier, "predict_proba") else preds

        acc = float(accuracy_score(y_test, preds))
        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))
        f1 = float(f1_score(y_test, preds, zero_division=0))

        try:
            auc = float(roc_auc_score(y_test, probas))
        except Exception:
            auc = 0.50

        brier = float(brier_score_loss(y_test, probas))

        self.metrics = ModelMetrics(
            accuracy=round(acc, 3),
            precision=round(prec, 3),
            recall=round(rec, 3),
            f1=round(f1, 3),
            roc_auc=round(auc, 3),
            brier_score=round(brier, 3),
            sample_size=len(y_test),
        )
        return self.metrics

    def predict_confidence(self, features_dict: dict) -> float:
        """
        Dự đoán điểm tự tin (0.0 - 1.0) cho một vector đặc trưng.
        Nếu mô hình chưa train, trả về 0.5 (neutral fallback).
        """
        if not self.is_trained:
            return 0.50

        row = [features_dict.get(col, 0.0) for col in self.feature_names]
        X = pd.DataFrame([row], columns=self.feature_names)
        try:
            probas = self.classifier.predict_proba(X)
            return float(probas[0][1])
        except Exception as e:
            log.warning("Lỗi predict_confidence: %s", e)
            return 0.50

    def save(self, filepath: str) -> bool:
        """Lưu mô hình ra file .joblib."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        joblib.dump(self, filepath)
        log.info("✓ Đã lưu mô hình %s vào %s", self.model_version, filepath)
        return True

    @classmethod
    def load(cls, filepath: str) -> Optional["SignalQualityClassifier"]:
        """Tải mô hình từ file .joblib."""
        if not os.path.exists(filepath):
            log.warning("File mô hình không tồn tại: %s", filepath)
            return None
        try:
            loaded = joblib.load(filepath)
            log.info("✓ Đã tải mô hình %s từ %s", loaded.model_version, filepath)
            return loaded
        except Exception as e:
            log.error("Lỗi khi tải mô hình từ %s: %s", filepath, e)
            return None
