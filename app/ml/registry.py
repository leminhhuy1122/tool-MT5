# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Model Registry.

Quản lý vòng đời và phiên bản của mô hình ML trong SQLite:
- Lưu metadata và file path vào bảng model_versions.
- Lưu kết quả kiểm định vào bảng model_evaluations.
- Kiểm duyệt chất lượng trước khi cho phép mô hình được đưa vào PRODUCTION.
"""

from datetime import datetime, timezone
import json
from typing import Optional

from app.database.connection import DatabaseManager
from app.ml.model import ModelMetrics, SignalQualityClassifier
from logger import get_logger

log = get_logger("ml.registry")


class ModelRegistry:
    """Quản lý phiên bản và trạng thái của các mô hình Machine Learning."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def register_model(
        self,
        classifier: SignalQualityClassifier,
        file_path: str,
        metrics: Optional[ModelMetrics] = None,
    ) -> bool:
        """
        Đăng ký phiên bản mô hình vào bảng model_versions.
        """
        features_json = json.dumps(classifier.feature_names)
        metrics_dict = metrics.to_dict() if metrics else (classifier.metrics.to_dict() if classifier.metrics else {})
        metrics_json = json.dumps(metrics_dict)
        now_str = datetime.now(timezone.utc).isoformat()

        sql = """
        INSERT OR REPLACE INTO model_versions (
            version, model_type, features_list, metrics, file_path, created_at
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        params = (
            classifier.model_version,
            "RandomForestClassifier",
            features_json,
            metrics_json,
            file_path,
            now_str,
        )

        with self.db.session() as conn:
            conn.execute(sql, params)

        log.info("✓ Đã đăng ký mô hình %s vào model_versions.", classifier.model_version)
        return True

    def record_evaluation(
        self,
        version: str,
        metrics: ModelMetrics,
        details: Optional[dict] = None,
    ) -> int:
        """
        Lưu kết quả kiểm định vào bảng model_evaluations.
        """
        details_json = json.dumps(details or {}, ensure_ascii=False)
        now_str = datetime.now(timezone.utc).isoformat()

        sql = """
        INSERT INTO model_evaluations (
            model_version, evaluation_date, win_rate, profit_factor, sample_size, details
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        params = (
            version,
            now_str,
            float(metrics.precision * 100.0),
            float(metrics.roc_auc),
            int(metrics.sample_size),
            details_json,
        )

        with self.db.session() as conn:
            cursor = conn.execute(sql, params)
            eval_id = cursor.lastrowid or 0

        log.info("✓ Đã lưu evaluation #%d cho model %s.", eval_id, version)
        return eval_id

    def is_eligible_for_production(self, metrics: ModelMetrics) -> bool:
        """
        Kiểm tra mô hình có đạt chuẩn chất lượng tối thiểu để kích hoạt không.
        Nguyên tắc cốt lõi: 'Không mặc định ML tốt hơn rule-based'.
        """
        if metrics.sample_size < 10:
            log.warning("Mẫu kiểm định quá nhỏ (%d < 10), không đủ điều kiện kích hoạt.", metrics.sample_size)
            return False

        if metrics.accuracy < 0.50 or metrics.precision < 0.50:
            log.warning("Độ chính xác/Precision dưới 50%% (Acc: %.1f%%, Prec: %.1f%%).",
                        metrics.accuracy * 100, metrics.precision * 100)
            return False

        return True

    def get_latest_production_model_path(self) -> Optional[str]:
        """Lấy đường dẫn file của mô hình mới nhất."""
        sql = "SELECT file_path FROM model_versions ORDER BY created_at DESC LIMIT 1;"
        with self.db.session() as conn:
            row = conn.execute(sql).fetchone()
            if row:
                return row["file_path"]
        return None
