# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Database Connection.
"""

from pathlib import Path
import sqlite3
import pytest

from app.database.connection import DatabaseManager, parse_sqlite_path
from config import BASE_DIR, DatabaseConfig


class TestDatabaseConnection:
    """Test suite cho Database Connection."""

    def test_parse_sqlite_path(self):
        """Kiểm tra chuyển đổi URL thành file path chuẩn."""
        assert parse_sqlite_path(":memory:") == ":memory:"
        assert parse_sqlite_path("sqlite:///:memory:") == ":memory:"

        rel_path = parse_sqlite_path("sqlite:///data/test.db")
        expected = str((BASE_DIR / "data" / "test.db").resolve())
        assert rel_path == expected

    def test_in_memory_connection(self):
        """Khởi tạo database in-memory cho testing."""
        db = DatabaseManager(db_path=":memory:")
        assert db.db_path == ":memory:"

        with db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 + 1;")
            assert cursor.fetchone()[0] == 2

    def test_session_commit_on_success(self):
        """Session tự động commit khi khối lệnh hoàn thành không có lỗi."""
        db = DatabaseManager(db_path=":memory:")
        with db.session() as conn:
            conn.execute("CREATE TABLE test_tab (id INT);")
            conn.execute("INSERT INTO test_tab VALUES (42);")

        with db.session() as conn:
            cursor = conn.execute("SELECT id FROM test_tab;")
            assert cursor.fetchone()[0] == 42

    def test_session_rollback_on_error(self):
        """Session tự động rollback khi phát sinh exception."""
        db = DatabaseManager(db_path=":memory:")
        with db.session() as conn:
            conn.execute("CREATE TABLE items (val INT);")

        with pytest.raises(ValueError):
            with db.session() as conn:
                conn.execute("INSERT INTO items VALUES (100);")
                raise ValueError("Giả lập lỗi bất ngờ")

        with db.session() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items;")
            assert cursor.fetchone()[0] == 0

    def test_pragmas_enabled(self):
        """Kiểm tra foreign keys và pragmas được cấu hình đúng."""
        db = DatabaseManager(db_path=":memory:")
        with db.session() as conn:
            cursor = conn.execute("PRAGMA foreign_keys;")
            assert cursor.fetchone()[0] == 1  # Foreign keys bật
