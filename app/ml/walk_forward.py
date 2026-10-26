# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Walk-Forward Evaluator (Phase 7).

Thẩm định mô hình học máy theo phương pháp Walk-Forward Out-of-Sample:
- Phân đoạn chuỗi thời gian (Expanding / Rolling Window Chronological Splits).
- Tuyệt đối không dùng k-fold ngẫu nhiên (chống Data Leakage & Look-ahead Bias).
- Đo lường suy giảm hiệu suất (Performance Degradation Ratio) giữa In-Sample (IS) và Out-of-Sample (OOS).
- Đánh giá độ tin cậy xác suất qua Brier Score và Precision @ High Confidence.
- Xác định tiêu chuẩn đủ điều kiện đưa vào Production (Production Eligibility Criteria).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple, Type
import numpy as np
import pandas as pd

from app.ml.model import ModelMetrics, SignalQualityClassifier
from logger import get_logger

log = get_logger("ml.walk_forward")


@dataclass
class MLFoldResult:
    """Kết quả kiểm định Out-of-Sample cho một chu kỳ Walk-Forward."""
    fold_index: int
    train_start_idx: int
    train_end_idx: int
    test_start_idx: int
    test_end_idx: int
    train_sample_size: int
    test_sample_size: int
    train_metrics: ModelMetrics
    test_metrics: ModelMetrics
    degradation_auc: float
    precision_at_high_conf: float
    high_conf_samples: int
    is_acceptable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_index": self.fold_index,
            "train_range": [self.train_start_idx, self.train_end_idx],
            "test_range": [self.test_start_idx, self.test_end_idx],
            "train_sample_size": self.train_sample_size,
            "test_sample_size": self.test_sample_size,
            "train_metrics": self.train_metrics.to_dict(),
            "test_metrics": self.test_metrics.to_dict(),
            "degradation_auc": round(self.degradation_auc, 3),
            "precision_at_high_conf": round(self.precision_at_high_conf, 3),
            "high_conf_samples": self.high_conf_samples,
            "is_acceptable": self.is_acceptable,
        }


@dataclass
class MLWalkForwardReport:
    """Báo cáo tổng hợp đánh giá Walk-Forward của mô hình ML."""
    model_version: str
    num_folds: int
    total_test_samples: int
    avg_train_auc: float
    avg_test_auc: float
    avg_test_accuracy: float
    avg_test_precision: float
    avg_test_recall: float
    avg_test_f1: float
    avg_test_brier: float
    avg_precision_high_conf: float
    avg_degradation_ratio: float
    consistency_rate: float
    is_production_eligible: bool
    rejection_reasons: list[str] = field(default_factory=list)
    folds: list[MLFoldResult] = field(default_factory=list)

    def summary(self) -> str:
        eligible_str = "ĐẠT CHUẨN PRODUCTION ✓" if self.is_production_eligible else "CHƯA ĐỦ ĐIỀU KIỆN ✗"
        lines = [
            f"=== BÁO CÁO WALK-FORWARD ML: {self.model_version} ===",
            f"• Trạng thái thẩm định: {eligible_str}",
            f"• Số chu kỳ (Folds): {self.num_folds} | Tổng mẫu OOS: {self.total_test_samples}",
            f"• OOS ROC-AUC trung bình: {self.avg_test_auc:.3f} (In-Sample: {self.avg_train_auc:.3f})",
            f"• Tỷ lệ suy giảm hiệu suất (Degradation): {self.avg_degradation_ratio * 100:.1f}%",
            f"• OOS Precision trung bình: {self.avg_test_precision * 100:.1f}%",
            f"• Precision @ High Confidence (>=60%): {self.avg_precision_high_conf * 100:.1f}%",
            f"• Brier Score trung bình: {self.avg_test_brier:.3f}",
            f"• Độ ổn định (Consistency Rate): {self.consistency_rate:.1f}%",
        ]
        if self.rejection_reasons:
            lines.append("• Lý do chưa đạt:")
            for r in self.rejection_reasons:
                lines.append(f"  - {r}")
        lines.append("=====================================================")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "num_folds": self.num_folds,
            "total_test_samples": self.total_test_samples,
            "avg_train_auc": round(self.avg_train_auc, 3),
            "avg_test_auc": round(self.avg_test_auc, 3),
            "avg_test_accuracy": round(self.avg_test_accuracy, 3),
            "avg_test_precision": round(self.avg_test_precision, 3),
            "avg_test_recall": round(self.avg_test_recall, 3),
            "avg_test_f1": round(self.avg_test_f1, 3),
            "avg_test_brier": round(self.avg_test_brier, 3),
            "avg_precision_high_conf": round(self.avg_precision_high_conf, 3),
            "avg_degradation_ratio": round(self.avg_degradation_ratio, 3),
            "consistency_rate": round(self.consistency_rate, 1),
            "is_production_eligible": self.is_production_eligible,
            "rejection_reasons": self.rejection_reasons,
            "folds": [f.to_dict() for f in self.folds],
        }


class MLWalkForwardEvaluator:
    """
    Bộ thẩm định độ ổn định của Machine Learning qua Walk-Forward Out-of-Sample.
    """

    def __init__(
        self,
        num_folds: int = 4,
        min_train_samples: int = 20,
        min_test_samples: int = 8,
        high_conf_threshold: float = 0.60,
        max_allowed_degradation: float = 0.35,
        min_required_auc: float = 0.52,
        min_required_precision: float = 0.50,
        min_required_high_conf_precision: float = 0.55,
        max_allowed_brier: float = 0.25,
        min_consistency_rate: float = 50.0,
    ):
        self.num_folds = max(2, num_folds)
        self.min_train_samples = min_train_samples
        self.min_test_samples = min_test_samples
        self.high_conf_threshold = high_conf_threshold
        self.max_allowed_degradation = max_allowed_degradation
        self.min_required_auc = min_required_auc
        self.min_required_precision = min_required_precision
        self.min_required_high_conf_precision = min_required_high_conf_precision
        self.max_allowed_brier = max_allowed_brier
        self.min_consistency_rate = min_consistency_rate

    def evaluate(
        self,
        classifier_factory: Callable[[], SignalQualityClassifier],
        X: pd.DataFrame,
        y: pd.Series,
        model_version: str = "ML-WalkForward",
        expanding_window: bool = True,
    ) -> MLWalkForwardReport:
        """
        Thực hiện đánh giá Walk-Forward trên tập dữ liệu đặc trưng X và nhãn y.

        Args:
            classifier_factory: Hàm tạo mới instance Classifier (để train độc lập mỗi fold).
            X: DataFrame các vector đặc trưng định lượng.
            y: Series nhãn nhị phân (1: Thắng, 0: Thua).
            model_version: Tên phiên bản mô hình thẩm định.
            expanding_window: True nếu Train mở rộng lũy tiến, False nếu Train cố định độ dài trượt.

        Returns:
            MLWalkForwardReport với đầy đủ metrics chi tiết.
        """
        n_samples = len(X)
        total_required = self.min_train_samples + (self.min_test_samples * self.num_folds)

        if n_samples < total_required or len(y.unique()) < 2:
            log.warning(
                "Không đủ dữ liệu cho Walk-Forward (%d mẫu có sẵn < %d yêu cầu tối thiểu).",
                n_samples, total_required,
            )
            return MLWalkForwardReport(
                model_version=model_version,
                num_folds=0,
                total_test_samples=0,
                avg_train_auc=0.0,
                avg_test_auc=0.0,
                avg_test_accuracy=0.0,
                avg_test_precision=0.0,
                avg_test_recall=0.0,
                avg_test_f1=0.0,
                avg_test_brier=1.0,
                avg_precision_high_conf=0.0,
                avg_degradation_ratio=1.0,
                consistency_rate=0.0,
                is_production_eligible=False,
                rejection_reasons=[
                    f"Số lượng mẫu dữ liệu không đủ ({n_samples} < {total_required} yêu cầu tối thiểu)"
                ],
            )

        test_fold_size = (n_samples - self.min_train_samples) // self.num_folds
        test_fold_size = max(self.min_test_samples, test_fold_size)

        folds: list[MLFoldResult] = []

        for fold_idx in range(self.num_folds):
            test_start = self.min_train_samples + (fold_idx * test_fold_size)
            test_end = test_start + test_fold_size if fold_idx < self.num_folds - 1 else n_samples

            if test_start >= n_samples or (test_end - test_start) < 2:
                break

            train_start = 0 if expanding_window else max(0, test_start - (self.min_train_samples + test_fold_size))
            train_end = test_start

            X_tr = X.iloc[train_start:train_end]
            y_tr = y.iloc[train_start:train_end]
            X_te = X.iloc[test_start:test_end]
            y_te = y.iloc[test_start:test_end]

            # Kiểm tra tập train phải có đủ cả 2 lớp nhãn
            if len(y_tr.unique()) < 2:
                log.warning("Fold %d: Tập train chỉ có 1 nhãn, bỏ qua fold.", fold_idx + 1)
                continue

            clf = classifier_factory()
            clf.train(X_tr, y_tr)
            train_metrics = clf.evaluate(X_tr, y_tr)

            # Thẩm định Out-of-Sample trên tập test
            test_metrics = clf.evaluate(X_te, y_te)

            # Tính toán xác suất dự đoán trên tập test
            probs = clf.predict_proba(X_te)
            y_te_arr = np.array(y_te)

            # Precision @ High Confidence
            high_conf_mask = probs >= self.high_conf_threshold
            high_conf_samples = int(np.sum(high_conf_mask))
            if high_conf_samples > 0:
                high_conf_prec = float(np.mean(y_te_arr[high_conf_mask] == 1))
            else:
                high_conf_prec = float(test_metrics.precision)

            # Degradation Ratio: Đo lường mức độ sụt giảm từ IS sang OOS
            if train_metrics.roc_auc > 0:
                degradation = max(0.0, (train_metrics.roc_auc - test_metrics.roc_auc) / train_metrics.roc_auc)
            else:
                degradation = 0.0

            # Tiêu chí chấp nhận được cho fold này: test AUC >= 0.50 và test precision >= 0.48
            is_acceptable = (test_metrics.roc_auc >= 0.50) and (test_metrics.precision >= 0.48)

            folds.append(
                MLFoldResult(
                    fold_index=len(folds) + 1,
                    train_start_idx=train_start,
                    train_end_idx=train_end,
                    test_start_idx=test_start,
                    test_end_idx=test_end,
                    train_sample_size=len(X_tr),
                    test_sample_size=len(X_te),
                    train_metrics=train_metrics,
                    test_metrics=test_metrics,
                    degradation_auc=degradation,
                    precision_at_high_conf=high_conf_prec,
                    high_conf_samples=high_conf_samples,
                    is_acceptable=is_acceptable,
                )
            )

        if not folds:
            return MLWalkForwardReport(
                model_version=model_version,
                num_folds=0,
                total_test_samples=0,
                avg_train_auc=0.0,
                avg_test_auc=0.0,
                avg_test_accuracy=0.0,
                avg_test_precision=0.0,
                avg_test_recall=0.0,
                avg_test_f1=0.0,
                avg_test_brier=1.0,
                avg_precision_high_conf=0.0,
                avg_degradation_ratio=1.0,
                consistency_rate=0.0,
                is_production_eligible=False,
                rejection_reasons=["Không tạo được fold hợp lệ do thiếu cân bằng nhãn"],
            )

        num_valid_folds = len(folds)
        total_test_samples = sum(f.test_sample_size for f in folds)
        avg_train_auc = sum(f.train_metrics.roc_auc for f in folds) / num_valid_folds
        avg_test_auc = sum(f.test_metrics.roc_auc for f in folds) / num_valid_folds
        avg_test_acc = sum(f.test_metrics.accuracy for f in folds) / num_valid_folds
        avg_test_prec = sum(f.test_metrics.precision for f in folds) / num_valid_folds
        avg_test_rec = sum(f.test_metrics.recall for f in folds) / num_valid_folds
        avg_test_f1 = sum(f.test_metrics.f1 for f in folds) / num_valid_folds
        avg_test_brier = sum(f.test_metrics.brier_score for f in folds) / num_valid_folds
        avg_prec_high = sum(f.precision_at_high_conf for f in folds) / num_valid_folds
        avg_degradation = sum(f.degradation_auc for f in folds) / num_valid_folds
        consistency_rate = (sum(1 for f in folds if f.is_acceptable) / num_valid_folds) * 100.0

        # Kiểm tra tiêu chuẩn Production Eligibility
        rejection_reasons: list[str] = []
        if total_test_samples < 20:
            rejection_reasons.append(
                f"Tổng mẫu OOS quá nhỏ ({total_test_samples} < 20 mẫu yêu cầu)"
            )
        if avg_test_auc < self.min_required_auc:
            rejection_reasons.append(
                f"OOS ROC-AUC trung bình chưa đạt ({avg_test_auc:.3f} < {self.min_required_auc:.2f})"
            )
        if avg_test_prec < self.min_required_precision:
            rejection_reasons.append(
                f"OOS Precision trung bình dưới 50% ({avg_test_prec*100:.1f}%)"
            )
        if avg_prec_high < self.min_required_high_conf_precision:
            rejection_reasons.append(
                f"Precision @ High Conf chưa đạt ({avg_prec_high*100:.1f}% < {self.min_required_high_conf_precision*100:.1f}%)"
            )
        if avg_test_brier > self.max_allowed_brier:
            rejection_reasons.append(
                f"Brier Score vượt ngưỡng cho phép ({avg_test_brier:.3f} > {self.max_allowed_brier:.2f})"
            )
        if avg_degradation > self.max_allowed_degradation:
            rejection_reasons.append(
                f"Độ sụt giảm hiệu suất (Degradation) quá cao do Overfitting ({avg_degradation*100:.1f}% > {self.max_allowed_degradation*100:.1f}%)"
            )
        if consistency_rate < self.min_consistency_rate:
            rejection_reasons.append(
                f"Độ ổn định các chu kỳ không đủ ({consistency_rate:.1f}% < {self.min_consistency_rate:.1f}%)"
            )

        is_production_eligible = len(rejection_reasons) == 0

        return MLWalkForwardReport(
            model_version=model_version,
            num_folds=num_valid_folds,
            total_test_samples=total_test_samples,
            avg_train_auc=round(avg_train_auc, 3),
            avg_test_auc=round(avg_test_auc, 3),
            avg_test_accuracy=round(avg_test_acc, 3),
            avg_test_precision=round(avg_test_prec, 3),
            avg_test_recall=round(avg_test_rec, 3),
            avg_test_f1=round(avg_test_f1, 3),
            avg_test_brier=round(avg_test_brier, 3),
            avg_precision_high_conf=round(avg_prec_high, 3),
            avg_degradation_ratio=round(avg_degradation, 3),
            consistency_rate=round(consistency_rate, 1),
            is_production_eligible=is_production_eligible,
            rejection_reasons=rejection_reasons,
            folds=folds,
        )
