# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Database Migrations.
"""

import pytest

from app.database.connection import DatabaseManager
from app.database.migrations import get_current_version, run_migrations


class TestDatabaseMigrations:
    """Test suite cho Database Migrations."""

    def test_fresh_database_version_is_zero(self):
        """Database mới tinh chưa có bảng migrations phải trả về version 0."""
        db = DatabaseManager(db_path=":memory:")
        assert get_current_version(db) == 0

    def test_run_migrations_applies_schema_v1(self):
        """Chạy migration thành công áp dụng schema v1."""
        db = DatabaseManager(db_path=":memory:")
        new_ver = run_migrations(db)

        assert new_ver == 1
        assert get_current_version(db) == 1

        # Kiểm tra danh sách bảng đã được tạo
        with db.session() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = [r[0] for r in cursor.fetchall()]

        expected_tables = [
            "market_data",
            "model_evaluations",
            "model_versions",
            "schema_migrations",
            "signal_features",
            "signal_outcomes",
            "signals",
            "strategy_versions",
        ]

        for t in expected_tables:
            assert t in tables, f"Thiếu bảng {t} trong database!"

    def test_run_migrations_idempotency(self):
        """Chạy migration nhiều lần liên tiếp không gây lỗi và giữ nguyên version."""
        db = DatabaseManager(db_path=":memory:")
        v1 = run_migrations(db)
        assert v1 == 1

        v2 = run_migrations(db)
        assert v2 == 1
