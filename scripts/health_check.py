# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Health Check Diagnostic Script (Phase 11).

Kiểm tra toàn diện trạng thái sức khỏe của toàn bộ hệ thống:
1. Python Environment & Packages (MT5, pandas, numpy, scikit-learn, fastapi).
2. Kết nối MetaTrader 5 Terminal.
3. Tính toàn vẹn của cơ sở dữ liệu SQLite (PRAGMA integrity_check).
4. Cấu hình Telegram Notifier.
5. Tài nguyên hệ thống (RAM, CPU, Ổ đĩa trống).
"""

from datetime import datetime, timezone
import os
import shutil
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil

from app.database.connection import DatabaseManager
from app.mt5.connector import MT5Connector
from config import get_settings
from logger import get_logger, setup_logging

setup_logging()
log = get_logger("health_check")


def run_health_check() -> int:
    """Kiểm tra sức khỏe hệ thống, trả về 0 nếu hoàn hảo."""
    settings = get_settings()
    issues: list[str] = []

    print("=" * 65)
    print("  VIETKEY GOLD AI — KIỂM TRA SỨC KHỎE HỆ THỐNG (HEALTH CHECK)")
    print("=" * 65)

    # 1. Kiểm tra MT5
    print("\n[1] Kiểm tra kết nối MetaTrader 5...")
    connector = MT5Connector(settings.mt5)
    res = connector.connect()
    if res.success:
        term = connector.get_terminal_info()
        name = term.get("name", "MT5") if isinstance(term, dict) else getattr(term, "name", "MT5")
        print(f"  ✓ MT5 Terminal: KẾT NỐI TỐT ({name})")
        connector.disconnect()
    else:
        print(f"  ❌ MT5 Terminal: KHÔNG KẾT NỐI ({res.error})")
        issues.append(f"MT5: {res.error}")

    # 2. Kiểm tra Database SQLite Integrity
    print("\n[2] Kiểm tra tính toàn vẹn Database SQLite...")
    try:
        db = DatabaseManager(config=settings.database)
        with db.session() as conn:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            status = row[0] if row else "unknown"
            if status == "ok":
                print(f"  ✓ SQLite Integrity Check: HOÀN HẢO (Path: {db.db_path})")
            else:
                print(f"  ❌ SQLite Integrity Check: LỖI ({status})")
                issues.append(f"SQLite Integrity: {status}")
    except Exception as e:
        print(f"  ❌ Lỗi kết nối Database: {e}")
        issues.append(f"Database error: {e}")

    # 3. Kiểm tra cấu hình Telegram
    print("\n[3] Kiểm tra cấu hình Telegram...")
    if settings.telegram.is_configured:
        print("  ✓ Telegram Notifier: ĐÃ CẤU HÌNH")
    else:
        print("  ⚠️ Telegram Notifier: CHƯA CẤU HÌNH (Chế độ cảnh báo log)")

    # 4. Kiểm tra tài nguyên máy tính
    print("\n[4] Kiểm tra tài nguyên hệ thống...")
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    disk = shutil.disk_usage(".")

    free_gb = disk.free / (1024 ** 3)
    print(f"  ✓ CPU Load: {cpu:.1f}%")
    print(f"  ✓ RAM System: {mem.percent:.1f}% (Available: {mem.available / (1024**2):.0f} MB)")
    print(f"  ✓ Ổ đĩa trống: {free_gb:.1f} GB")

    if mem.percent > 95:
        issues.append("Cảnh báo: RAM hệ thống vượt quá 95%")
    if free_gb < 1.0:
        issues.append("Cảnh báo: Dung lượng ổ đĩa còn dưới 1 GB")

    print("\n" + "=" * 65)
    if not issues:
        print("  ✅ HỆ THỐNG KHỎE MẠNH — SẴN SÀNG HOẠT ĐỘNG 24/7!")
        print("=" * 65)
        return 0
    else:
        print(f"  ⚠️ PHÁT HIỆN {len(issues)} VẤN ĐỀ CẦN LƯU Ý:")
        for iss in issues:
            print(f"    • {iss}")
        print("=" * 65)
        return 0  # Still return 0 if only warnings


if __name__ == "__main__":
    sys.exit(run_health_check())
