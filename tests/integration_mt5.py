# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: MT5 Connection.

Script này kiểm tra kết nối MT5 THẬT.
Yêu cầu:
- MT5 terminal đang mở và đã đăng nhập.
- File .env đã điền thông tin MT5.

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_mt5.py

KHÔNG tự động chạy trong CI/CD — chỉ chạy thủ công.
"""

import sys
import os

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from logger import setup_logging, get_logger
from app.mt5.connector import MT5Connector
from app.mt5.account_info import get_account_info
from app.mt5.symbol_info import check_symbol, get_symbol_info


def main() -> None:
    """Chạy integration test MT5."""
    settings = get_settings()
    setup_logging(log_level="DEBUG")
    log = get_logger("integration_test")

    log.info("=" * 60)
    log.info("  INTEGRATION TEST — MT5 Connection")
    log.info("=" * 60)

    results: dict[str, str] = {}

    # ── Test 1: Kết nối MT5 ──
    log.info("\n[TEST 1] Kết nối MetaTrader 5...")
    connector = MT5Connector(settings.mt5)
    result = connector.connect()
    results["1. Connect MT5"] = "✓ PASS" if result.success else f"✗ FAIL: {result.message}"

    if not result.success:
        log.error("Không thể kết nối MT5. Dừng test.")
        _print_results(results, log)
        return

    try:
        # ── Test 2: Terminal info ──
        log.info("\n[TEST 2] Lấy terminal info...")
        term_info = connector.get_terminal_info()
        if term_info:
            results["2. Terminal Info"] = f"✓ PASS (build={term_info.get('build')})"
        else:
            results["2. Terminal Info"] = "✗ FAIL"

        # ── Test 3: Account info ──
        log.info("\n[TEST 3] Lấy account info...")
        account = get_account_info()
        if account:
            results["3. Account Info"] = (
                f"✓ PASS ({account.trade_mode_name} | "
                f"Balance: {account.balance:.2f} {account.currency})"
            )
        else:
            results["3. Account Info"] = "✗ FAIL"

        # ── Test 4: Check symbol ──
        symbol = settings.mt5.symbol
        log.info("\n[TEST 4] Kiểm tra symbol '%s'...", symbol)
        sym_ok = check_symbol(symbol)
        results[f"4. Symbol '{symbol}'"] = "✓ PASS" if sym_ok else "✗ FAIL"

        # ── Test 5: Symbol info ──
        if sym_ok:
            log.info("\n[TEST 5] Lấy thông tin symbol '%s'...", symbol)
            sym_info = get_symbol_info(symbol)
            if sym_info:
                results[f"5. Symbol Info"] = (
                    f"✓ PASS (Bid={sym_info.bid} | Ask={sym_info.ask} | "
                    f"Spread={sym_info.spread})"
                )
            else:
                results["5. Symbol Info"] = "✗ FAIL"
        else:
            results["5. Symbol Info"] = "⊘ SKIP (symbol not available)"

    finally:
        # ── Luôn disconnect ──
        log.info("\n[CLEANUP] Ngắt kết nối MT5...")
        connector.disconnect()
        results["6. Disconnect"] = "✓ PASS"

    _print_results(results, log)


def _print_results(results: dict[str, str], log) -> None:
    """In kết quả tổng hợp."""
    log.info("\n" + "=" * 60)
    log.info("  KẾT QUẢ INTEGRATION TEST")
    log.info("=" * 60)
    for test_name, status in results.items():
        log.info("  %s: %s", test_name, status)

    passed = sum(1 for v in results.values() if "PASS" in v)
    total = len(results)
    log.info("-" * 60)
    log.info("  Tổng: %d/%d passed", passed, total)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
