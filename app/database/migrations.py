# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Migration Runner.

Quản lý và thực thi các đợt migration cấu trúc database:
- Tự động phát hiện phiên bản schema hiện tại.
- Áp dụng tuần tự các migration chưa chạy.
- Ghi log chi tiết và an toàn rollback nếu có lỗi.
"""

from app.database.connection import DatabaseManager
from app.database.schema import INITIAL_SCHEMA_SQL
from logger import get_logger

log = get_logger("database.migrations")

# Danh sách migrations tuần tự: version -> SQL
MIGRATIONS = {
    1: INITIAL_SCHEMA_SQL,
}


def get_current_version(db: DatabaseManager) -> int:
    """
    Lấy phiên bản schema hiện tại của database.

    Returns:
        Số phiên bản cao nhất đã áp dụng (0 nếu chưa khởi tạo).
    """
    with db.session() as conn:
        # Kiểm tra xem bảng schema_migrations đã tồn tại chưa
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';"
        )
        if not cursor.fetchone():
            return 0

        cursor.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cursor.fetchone()
        return row[0] if (row and row[0] is not None) else 0


def run_migrations(db: DatabaseManager) -> int:
    """
    Chạy tất cả các migrations còn thiếu.

    Args:
        db: DatabaseManager instance.

    Returns:
        Phiên bản schema mới nhất sau khi migration thành công.
    """
    current_ver = get_current_version(db)
    log.info("Phiên bản database hiện tại: v%d", current_ver)

    for version in sorted(MIGRATIONS.keys()):
        if version > current_ver:
            log.info("Đang áp dụng migration v%d...", version)
            sql = MIGRATIONS[version]
            with db.session() as conn:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?);",
                    (version,),
                )
            log.info("✓ Áp dụng thành công migration v%d", version)
            current_ver = version

    log.info("Database đã cập nhật lên phiên bản mới nhất: v%d", current_ver)
    return current_ver
