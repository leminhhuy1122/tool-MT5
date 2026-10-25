# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Connection & Manager.

Quản lý kết nối SQLite:
- Hỗ trợ đường dẫn file hoặc in-memory (:memory: cho testing).
- Giữ persistent connection cho in-memory database để bảo toàn dữ liệu giữa các session.
- Tự động tạo thư mục chứa database (data/) nếu chưa có.
- Bật WAL mode (Write-Ahead Logging) cho hiệu năng và an toàn dữ liệu cao.
- Bật Foreign Keys enforcement.
- Bật busy_timeout để tránh lỗi 'database is locked'.
- Context manager tự động commit và rollback an toàn.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Generator, Optional

from config import BASE_DIR, DatabaseConfig
from logger import get_logger

log = get_logger("database.connection")


def parse_sqlite_path(db_url: str) -> str:
    """
    Trích xuất đường dẫn file SQLite từ database URL.

    Ví dụ:
    - 'sqlite:///data/vietkey_gold.db' -> 'd:/dung/chibao MT5/data/vietkey_gold.db'
    - 'sqlite:///:memory:' -> ':memory:'
    - ':memory:' -> ':memory:'
    """
    if db_url in (":memory:", "sqlite:///:memory:"):
        return ":memory:"

    prefix = "sqlite:///"
    if db_url.startswith(prefix):
        raw_path = db_url[len(prefix):]
    elif db_url.startswith("sqlite://"):
        raw_path = db_url[len("sqlite://"):]
    else:
        raw_path = db_url

    path_obj = Path(raw_path)
    if not path_obj.is_absolute():
        path_obj = (BASE_DIR / path_obj).resolve()

    return str(path_obj)


class DatabaseManager:
    """
    Quản lý kết nối và vòng đời SQLite Database.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None, db_path: Optional[str] = None):
        if db_path is not None:
            self.db_path = parse_sqlite_path(db_path)
        elif config is not None:
            self.db_path = parse_sqlite_path(config.url)
        else:
            self.db_path = parse_sqlite_path("sqlite:///data/vietkey_gold.db")

        self.is_memory = (self.db_path == ":memory:")
        self._shared_conn: Optional[sqlite3.Connection] = None

        # Tự động tạo thư mục cha nếu là file thực tế
        if not self.is_memory:
            parent_dir = Path(self.db_path).parent
            parent_dir.mkdir(parents=True, exist_ok=True)
            log.info("Database path: %s", self.db_path)
        else:
            log.info("Sử dụng In-memory Database (:memory:)")
            self._shared_conn = self._create_raw_connection()

    def _create_raw_connection(self) -> sqlite3.Connection:
        """Tạo một connection mới với đầy đủ PRAGMA tối ưu."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=10.0,
        )
        conn.row_factory = sqlite3.Row  # Trả về kết quả dạng dict-like

        # Tối ưu hóa SQLite
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        if not self.is_memory:
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()

        return conn

    def get_raw_connection(self) -> sqlite3.Connection:
        """Lấy raw connection (dùng shared cho in-memory, tạo mới cho file)."""
        if self.is_memory and self._shared_conn:
            return self._shared_conn
        return self._create_raw_connection()

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager cung cấp connection tự động commit / rollback.

        Usage:
            with db.session() as conn:
                conn.execute(...)
        """
        if self.is_memory:
            conn = self._shared_conn if self._shared_conn else self._create_raw_connection()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                log.error("Database transaction rolled back do lỗi: %s", e)
                raise
        else:
            conn = self._create_raw_connection()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                log.error("Database transaction rolled back do lỗi: %s", e)
                raise
            finally:
                conn.close()

    def execute_script(self, sql_script: str) -> None:
        """Thực thi script SQL (nhiều lệnh)."""
        with self.session() as conn:
            conn.executescript(sql_script)

    def close(self) -> None:
        """Đóng kết nối persistent nếu có."""
        if self._shared_conn:
            self._shared_conn.close()
            self._shared_conn = None
