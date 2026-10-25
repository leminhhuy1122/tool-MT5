# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Backup Utility (Phase 11).

Sao lưu an toàn cơ sở dữ liệu SQLite trong lúc hệ thống đang chạy (Online Backup):
- Sử dụng API sqlite3.Connection.backup() bảo đảm tính nhất quán dữ liệu (ACID).
- Tự động nén và xoay vòng giữ lại N bản sao lưu gần nhất.
- Hỗ trợ chạy tự động qua Windows Task Scheduler.
"""

from datetime import datetime, timezone
import os
import shutil
import sqlite3
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from logger import get_logger, setup_logging

setup_logging()
log = get_logger("backup")


def backup_database(max_backups: int = 14) -> bool:
    """
    Thực hiện sao lưu an toàn database vietkey_gold.db.

    Args:
        max_backups: Số lượng bản sao lưu tối đa cần giữ lại.

    Returns:
        True nếu sao lưu thành công.
    """
    from app.database.connection import DatabaseManager
    settings = get_settings()
    db = DatabaseManager(config=settings.database)
    source_db_path = db.db_path
    if not os.path.exists(source_db_path):
        log.warning("File database không tồn tại: %s", source_db_path)
        return False

    backup_dir = os.path.join(os.path.dirname(source_db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_backup_path = os.path.join(backup_dir, f"vietkey_gold_{timestamp}.db")

    log.info("Bắt đầu sao lưu SQLite: %s -> %s", source_db_path, target_backup_path)

    try:
        # Sử dụng SQLite Online Backup API
        src_conn = sqlite3.connect(source_db_path)
        dest_conn = sqlite3.connect(target_backup_path)

        with dest_conn:
            src_conn.backup(dest_conn)

        dest_conn.close()
        src_conn.close()

        file_size_kb = os.path.getsize(target_backup_path) / 1024
        log.info("✓ Sao lưu thành công! Kích thước: %.1f KB", file_size_kb)

        # Xoay vòng bản sao lưu (Xóa các file cũ nếu vượt quá max_backups)
        backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("vietkey_gold_") and f.endswith(".db")
        ])

        if len(backups) > max_backups:
            to_remove = backups[:-max_backups]
            for old_f in to_remove:
                try:
                    os.remove(old_f)
                    log.info("Đã xóa bản sao lưu cũ: %s", os.path.basename(old_f))
                except Exception as e:
                    log.warning("Không thể xóa file cũ %s: %s", old_f, e)

        return True

    except Exception as e:
        log.error("Lỗi sao lưu database: %s", e, exc_info=True)
        return False


if __name__ == "__main__":
    success = backup_database()
    sys.exit(0 if success else 1)
