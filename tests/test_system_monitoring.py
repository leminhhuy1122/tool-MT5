# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for System Monitoring & Error Diagnostics Endpoints.
"""

from unittest.mock import patch, MagicMock
import pytest

from app.api.server import (
    _parse_log_file,
    get_system_diagnostics,
    get_system_logs,
    run_system_self_test,
)


def test_parse_log_file_with_sample_data(tmp_path, monkeypatch):
    """Kiểm tra parser nhật ký hệ thống tách đúng cấp độ, thời gian và traceback nhiều dòng."""
    sample_log = (
        "2026-10-26 12:00:00,100 | INFO     | app.main             | Bot khởi động thành công.\n"
        "2026-10-26 12:05:00,200 | WARNING  | app.risk             | Cảnh báo biến động spread cao 2.5 giá.\n"
        "2026-10-26 12:10:00,300 | ERROR    | app.bot.runner       | Lỗi kết nối IPC MT5 thất bại.\n"
        "Traceback (most recent call last):\n"
        '  File "runner.py", line 42, in tick\n'
        "ConnectionResetError: pipe disconnected\n"
        "2026-10-26 12:15:00,400 | INFO     | app.paper            | Khớp lệnh BUY Paper 0.01 lot.\n"
    )
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "vietkey_2026-10-26.log"
    log_file.write_text(sample_log, encoding="utf-8")

    # Monkeypatch log directory to tmp_path
    monkeypatch.chdir(tmp_path)

    # 1. Test parse tất cả logs (mới nhất lên đầu)
    logs = _parse_log_file(date_str="2026-10-26", max_lines=100)
    assert len(logs) == 4
    # Thứ tự đảo ngược: log cuối (12:15:00) xuất hiện đầu tiên
    assert "Khớp lệnh BUY" in logs[0]["message"]
    assert logs[0]["level"] == "INFO"

    # Kiểm tra log ERROR có chứa toàn bộ traceback
    error_logs = [l for l in logs if l["isError"]]
    assert len(error_logs) == 1
    assert "ConnectionResetError: pipe disconnected" in error_logs[0]["message"]

    # Kiểm tra log WARNING
    warn_logs = [l for l in logs if l["isWarning"]]
    assert len(warn_logs) == 1
    assert "Cảnh báo biến động spread" in warn_logs[0]["message"]


def test_get_system_diagnostics_endpoint():
    """Kiểm tra endpoint chẩn đoán hệ thống trả về đầy đủ các thông số."""
    diag = get_system_diagnostics()
    assert "status" in diag
    assert diag["status"] in ("HEALTHY", "WARNING", "DEGRADED", "ERROR")
    assert "stabilityScore" in diag
    assert "uptimeSeconds" in diag
    assert "timestamp" in diag
    assert "mt5" in diag
    assert "database" in diag
    assert "botRunner" in diag
    assert "resources" in diag
    assert "pid" in diag["resources"]
    assert "cpuPct" in diag["resources"]
    assert "ramMB" in diag["resources"]
    assert "errorDiagnostics" in diag
    assert "errorCount24h" in diag["errorDiagnostics"]
    assert "warningCount24h" in diag["errorDiagnostics"]
    assert "recentErrors" in diag["errorDiagnostics"]


def test_get_system_logs_endpoint():
    """Kiểm tra endpoint đọc logs hệ thống trả về schema hợp lệ và hỗ trợ bộ lọc."""
    # Test level ALL
    res = get_system_logs(level="ALL", limit=20, search="")
    assert "total" in res
    assert "errorCount" in res
    assert "warningCount" in res
    assert "infoCount" in res
    assert "logs" in res
    assert isinstance(res["logs"], list)

    # Test level ERROR
    res_err = get_system_logs(level="ERROR", limit=10)
    assert res_err["filteredCount"] <= res["total"]

    # Test keyword search
    res_search = get_system_logs(level="ALL", limit=10, search="INFO")
    assert isinstance(res_search["logs"], list)


def test_run_system_self_test_endpoint():
    """Kiểm tra tính năng chạy tự kiểm tra tính toàn vẹn (Self-Diagnostics Test)."""
    res = run_system_self_test()
    assert "timestamp" in res
    assert "ok" in res
    assert isinstance(res["ok"], bool)
    assert "tests" in res
    assert len(res["tests"]) >= 4

    # Kiểm tra các hạng mục test cốt lõi
    test_names = [t["test"] for t in res["tests"]]
    assert any("SQLite" in name for name in test_names)
    assert any("MetaTrader" in name or "MT5" in name for name in test_names)
    assert any("Paper" in name for name in test_names)
    assert any("Disk" in name for name in test_names)
