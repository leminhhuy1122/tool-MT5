# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Model Registry (Phase 7).

Quản lý vòng đời và phiên bản của mô hình ML trong SQLite:
- Lưu metadata, features list, metrics và file path vào bảng model_versions.
- Quản lý trạng thái mô hình: DRAFT, CANDIDATE, PRODUCTION, RETIRED.
- Lưu kết quả kiểm định Out-of-Sample và Walk-Forward vào bảng model_evaluations.
- Kiểm duyệt chất lượng trước khi cho phép mô hình được đưa vào PRODUCTION.
- Tự động Fallback: Nếu không có mô hình PRODUCTION đạt chuẩn, hệ thống rule-based tiếp tục 100%.
"""

from datetime import datetime, timezone
from enum import Enum
import json
import os
from typing import Any, Optional, Tuple

from app.database.connection import DatabaseManager
from app.ml.model import ModelMetrics, SignalQualityClassifier
from app.ml.walk_forward import MLWalkForwardReport
from logger import get_logger

log = get_logger("ml.registry")


class ModelStatus(str, Enum):
    """Trạng thái vòng đời của mô hình Machine Learning."""
    DRAFT = "DRAFT"              # Mới khởi tạo / thử nghiệm
    CANDIDATE = "CANDIDATE"      # Ứng viên đang chờ kiểm định
    PRODUCTION = "PRODUCTION"    # Mô hình active đang chạy live / forward test
    RETIRED = "RETIRED"          # Mô hình cũ đã lưu trữ


class ModelRegistry:
    """Quản lý phiên bản và trạng thái của các mô hình Machine Learning."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Đảm bảo bảng model_versions có các cột status và description."""
        try:
            with self.db.session() as conn:
                cursor = conn.execute("PRAGMA table_info(model_versions);")
                columns = [row["name"] for row in cursor.fetchall()]
                if columns:
                    if "status" not in columns:
                        conn.execute("ALTER TABLE model_versions ADD COLUMN status TEXT DEFAULT 'DRAFT';")
                        log.info("✓ Đã bổ sung cột 'status' vào bảng model_versions.")
                    if "description" not in columns:
                        conn.execute("ALTER TABLE model_versions ADD COLUMN description TEXT DEFAULT '';")
                        log.info("✓ Đã bổ sung cột 'description' vào bảng model_versions.")
        except Exception as e:
            log.warning("Không thể kiểm tra/thêm cột trong model_versions: %s", e)

    def register_model(
        self,
        classifier: SignalQualityClassifier,
        file_path: str,
        metrics: Optional[ModelMetrics] = None,
        status: str = ModelStatus.DRAFT.value,
        description: str = "",
    ) -> bool:
        """
        Đăng ký phiên bản mô hình vào bảng model_versions.
        """
        features_json = json.dumps(classifier.feature_names)
        metrics_dict = metrics.to_dict() if metrics else (classifier.metrics.to_dict() if classifier.metrics else {})
        metrics_json = json.dumps(metrics_dict)
        now_str = datetime.now(timezone.utc).isoformat()

        # Kiểm tra xem bảng có cột status không
        has_status = False
        try:
            with self.db.session() as conn:
                cursor = conn.execute("PRAGMA table_info(model_versions);")
                cols = [r["name"] for r in cursor.fetchall()]
                has_status = "status" in cols
        except Exception:
            pass

        if has_status:
            sql = """
            INSERT OR REPLACE INTO model_versions (
                version, model_type, features_list, metrics, file_path, status, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """
            params = (
                classifier.model_version,
                "RandomForestClassifier",
                features_json,
                metrics_json,
                file_path,
                status.upper(),
                description,
                now_str,
            )
        else:
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
            if has_status and status.upper() == ModelStatus.PRODUCTION.value:
                # Nếu đặt làm PRODUCTION -> Đưa các model PRODUCTION cũ sang RETIRED
                conn.execute(
                    "UPDATE model_versions SET status = 'RETIRED' WHERE status = 'PRODUCTION' AND version != ?;",
                    (classifier.model_version,),
                )

        log.info("✓ Đã đăng ký mô hình %s (status=%s) vào model_versions.", classifier.model_version, status)
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

    def record_walk_forward_evaluation(
        self,
        version: str,
        report: MLWalkForwardReport,
    ) -> int:
        """
        Lưu toàn diện báo cáo Walk-Forward Out-of-Sample vào bảng model_evaluations.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        details_dict = report.to_dict()

        sql = """
        INSERT INTO model_evaluations (
            model_version, evaluation_date, win_rate, profit_factor, sample_size, details
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        params = (
            version,
            now_str,
            float(report.avg_test_precision * 100.0),
            float(report.avg_test_auc),
            int(report.total_test_samples),
            json.dumps(details_dict, ensure_ascii=False),
        )

        with self.db.session() as conn:
            cursor = conn.execute(sql, params)
            eval_id = cursor.lastrowid or 0

        log.info(
            "✓ Đã lưu Walk-Forward evaluation #%d cho model %s (Eligible=%s).",
            eval_id, version, report.is_production_eligible,
        )
        return eval_id

    def check_production_eligibility(
        self,
        metrics: Optional[ModelMetrics] = None,
        walk_forward_report: Optional[MLWalkForwardReport] = None,
    ) -> Tuple[bool, list[str]]:
        """
        Kiểm tra chi tiết điều kiện thăng cấp mô hình lên PRODUCTION.
        """
        reasons: list[str] = []

        if walk_forward_report is not None:
            if not walk_forward_report.is_production_eligible:
                reasons.extend(walk_forward_report.rejection_reasons)
            return len(reasons) == 0, reasons

        if metrics is not None:
            if metrics.sample_size < 10:
                reasons.append(f"Mẫu kiểm định quá nhỏ ({metrics.sample_size} < 10)")
            if metrics.accuracy < 0.50:
                reasons.append(f"Độ chính xác dưới 50% ({metrics.accuracy * 100:.1f}%)")
            if metrics.precision < 0.50:
                reasons.append(f"Precision dưới 50% ({metrics.precision * 100:.1f}%)")
            if metrics.brier_score > 0.28:
                reasons.append(f"Brier Score vượt ngưỡng ({metrics.brier_score:.3f} > 0.28)")
            return len(reasons) == 0, reasons

        return False, ["Không có dữ liệu metrics hoặc walk-forward để thẩm định"]

    def is_eligible_for_production(
        self,
        metrics: ModelMetrics,
        walk_forward_report: Optional[MLWalkForwardReport] = None,
    ) -> bool:
        """
        Kiểm tra mô hình có đạt chuẩn chất lượng tối thiểu để kích hoạt không.
        (Giữ nguyên kiểu trả về bool cho backward compatibility).
        """
        eligible, reasons = self.check_production_eligibility(
            metrics=metrics,
            walk_forward_report=walk_forward_report,
        )
        if not eligible:
            for r in reasons:
                log.warning("Chưa đủ điều kiện kích hoạt: %s", r)
        return eligible

    def promote_to_production(
        self,
        version: str,
        force: bool = False,
        walk_forward_report: Optional[MLWalkForwardReport] = None,
    ) -> Tuple[bool, str]:
        """
        Thăng cấp phiên bản mô hình lên PRODUCTION.

        Args:
            version: Phiên bản cần thăng cấp.
            force: Bỏ qua kiểm tra chuẩn chất lượng nếu True.
            walk_forward_report: Báo cáo Walk-Forward thẩm định (nếu có).

        Returns:
            Tuple (Thành công, Thông điệp).
        """
        sql_find = "SELECT version, metrics, file_path FROM model_versions WHERE version = ?;"
        with self.db.session() as conn:
            row = conn.execute(sql_find, (version,)).fetchone()

        if not row:
            return False, f"Không tìm thấy mô hình phiên bản '{version}' trong hệ thống."

        if not force:
            # Lấy metrics từ DB nếu không truyền walk_forward_report
            if walk_forward_report is not None:
                eligible, reasons = self.check_production_eligibility(walk_forward_report=walk_forward_report)
            else:
                metrics_data = json.loads(row["metrics"]) if row["metrics"] else {}
                metrics = ModelMetrics.from_dict(metrics_data) if metrics_data else None
                eligible, reasons = self.check_production_eligibility(metrics=metrics)

            if not eligible:
                reasons_str = "; ".join(reasons)
                log.warning("Từ chối promote '%s' lên PRODUCTION: %s", version, reasons_str)
                return False, f"Mô hình chưa đạt chuẩn PRODUCTION: {reasons_str}"

        # Cập nhật trạng thái
        with self.db.session() as conn:
            # 1. Đưa các mô hình PRODUCTION cũ sang RETIRED
            conn.execute("UPDATE model_versions SET status = 'RETIRED' WHERE status = 'PRODUCTION';")
            # 2. Đặt mô hình đích thành PRODUCTION
            conn.execute("UPDATE model_versions SET status = 'PRODUCTION' WHERE version = ?;", (version,))

        log.info("✓ ĐÃ THĂNG CẤP THÀNH CÔNG MÔ HÌNH %s LÊN PRODUCTION!", version)
        return True, f"Mô hình '{version}' đã được kích hoạt thành PRODUCTION."

    def demote_to_retired(self, version: str) -> bool:
        """Thu hồi mô hình về trạng thái RETIRED."""
        with self.db.session() as conn:
            cursor = conn.execute(
                "UPDATE model_versions SET status = 'RETIRED' WHERE version = ?;",
                (version,),
            )
            return cursor.rowcount > 0

    def get_latest_production_model_path(self) -> Optional[str]:
        """Lấy đường dẫn file của mô hình PRODUCTION hiện tại (hoặc mới nhất nếu chưa gán status)."""
        has_status = False
        try:
            with self.db.session() as conn:
                cursor = conn.execute("PRAGMA table_info(model_versions);")
                cols = [r["name"] for r in cursor.fetchall()]
                has_status = "status" in cols
        except Exception:
            pass

        if has_status:
            # Ưu tiên lấy model có status = 'PRODUCTION'
            sql_prod = "SELECT file_path FROM model_versions WHERE status = 'PRODUCTION' ORDER BY created_at DESC LIMIT 1;"
            with self.db.session() as conn:
                row = conn.execute(sql_prod).fetchone()
                if row and row["file_path"]:
                    return row["file_path"]

        # Fallback: Lấy mô hình mới nhất
        sql_fallback = "SELECT file_path FROM model_versions ORDER BY created_at DESC LIMIT 1;"
        with self.db.session() as conn:
            row = conn.execute(sql_fallback).fetchone()
            if row:
                return row["file_path"]
        return None

    def get_active_production_model(self) -> Optional[SignalQualityClassifier]:
        """
        Nạp mô hình PRODUCTION đang hoạt động từ đĩa.
        Nếu không có hoặc lỗi nạp file, trả về None (hệ thống tự động Fallback rule-based).
        """
        model_path = self.get_latest_production_model_path()
        if not model_path or not os.path.exists(model_path):
            log.info("Chưa có mô hình ML PRODUCTION nào sẵn sàng. Hệ thống vận hành ở chế độ Rule-Based thuần túy.")
            return None

        try:
            classifier = SignalQualityClassifier.load(model_path)
            log.info("✓ Đã nạp thành công mô hình ML PRODUCTION [%s] từ %s", classifier.model_version, model_path)
            return classifier
        except Exception as e:
            log.error("Không thể nạp mô hình ML từ đường dẫn '%s': %s", model_path, e)
            return None

    def list_models(self) -> list[dict[str, Any]]:
        """Lấy danh sách tất cả các phiên bản mô hình trong registry."""
        sql = "SELECT version, model_type, features_list, metrics, file_path, created_at, status, description FROM model_versions ORDER BY created_at DESC;"
        try:
            with self.db.session() as conn:
                rows = conn.execute(sql).fetchall()
        except Exception:
            # Fallback nếu bảng chưa có cột status/description
            sql_fb = "SELECT version, model_type, features_list, metrics, file_path, created_at FROM model_versions ORDER BY created_at DESC;"
            with self.db.session() as conn:
                rows = conn.execute(sql_fb).fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            m_dict = dict(r)
            if "metrics" in m_dict and m_dict["metrics"]:
                try:
                    m_dict["metrics"] = json.loads(m_dict["metrics"])
                except Exception:
                    pass
            if "features_list" in m_dict and m_dict["features_list"]:
                try:
                    m_dict["features_list"] = json.loads(m_dict["features_list"])
                except Exception:
                    pass
            if "status" not in m_dict:
                m_dict["status"] = "DRAFT"
            results.append(m_dict)
        return results

    def get_model_details(self, version: str) -> Optional[dict[str, Any]]:
        """Lấy thông tin chi tiết một phiên bản mô hình kèm lịch sử đánh giá."""
        sql_ver = "SELECT * FROM model_versions WHERE version = ?;"
        with self.db.session() as conn:
            row_v = conn.execute(sql_ver, (version,)).fetchone()
            if not row_v:
                return None
            model_info = dict(row_v)

            if "metrics" in model_info and model_info["metrics"]:
                try:
                    model_info["metrics"] = json.loads(model_info["metrics"])
                except Exception:
                    pass

            sql_eval = "SELECT id, evaluation_date, win_rate, profit_factor, sample_size, details FROM model_evaluations WHERE model_version = ? ORDER BY evaluation_date DESC;"
            eval_rows = conn.execute(sql_eval, (version,)).fetchall()
            evaluations = []
            for er in eval_rows:
                ed = dict(er)
                if "details" in ed and ed["details"]:
                    try:
                        ed["details"] = json.loads(ed["details"])
                    except Exception:
                        pass
                evaluations.append(ed)
            model_info["evaluations"] = evaluations

        return model_info
