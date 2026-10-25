# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: Market Data.

Kiểm tra lấy dữ liệu thị trường THẬT từ MT5.
Yêu cầu: MT5 terminal đang mở và đã đăng nhập.

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_market.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from logger import setup_logging, get_logger
from app.mt5.connector import MT5Connector
from app.market.timeframe_manager import Timeframe, DEFAULT_TIMEFRAMES
from app.market.data_manager import MarketDataManager


def main() -> None:
    """Chạy integration test Market Data."""
    settings = get_settings()
    setup_logging(log_level="DEBUG")
    log = get_logger("integration_market")

    log.info("=" * 60)
    log.info("  INTEGRATION TEST — Market Data Engine")
    log.info("=" * 60)

    results: dict[str, str] = {}

    connector = MT5Connector(settings.mt5)
    result = connector.connect()

    if not result.success:
        log.error("Không thể kết nối MT5. Dừng test.")
        return

    try:
        symbol = settings.mt5.symbol
        mgr = MarketDataManager(symbol)

        # ── Test 1: Lấy giá hiện tại ──
        log.info("\n[TEST 1] Lấy giá hiện tại %s...", symbol)
        price = mgr.get_latest_price()
        if price:
            results["1. Latest Price"] = (
                f"✓ PASS (Bid={price['bid']:.2f} | Ask={price['ask']:.2f} | "
                f"Spread={price['spread']:.2f})"
            )
        else:
            results["1. Latest Price"] = "✗ FAIL"

        # ── Test 2-5: Lấy dữ liệu từng timeframe ──
        for idx, tf in enumerate(DEFAULT_TIMEFRAMES, start=2):
            log.info("\n[TEST %d] Lấy dữ liệu %s %s...", idx, symbol, tf.label)
            df = mgr.get_candles(tf, num_bars=50)
            if df is not None and len(df) > 0:
                quality = mgr.validate(df, tf)
                status = "✓ PASS" if quality.is_valid else "⚠ WARN"
                issues_str = f" ({', '.join(quality.issues)})" if quality.issues else ""
                results[f"{idx}. {tf.label} Data"] = (
                    f"{status} ({len(df)} bars){issues_str}"
                )
            else:
                results[f"{idx}. {tf.label} Data"] = "✗ FAIL"

        # ── Test 6: Lấy nhiều timeframes cùng lúc ──
        test_num = len(DEFAULT_TIMEFRAMES) + 2
        log.info("\n[TEST %d] Lấy tất cả timeframes...", test_num)
        all_data = mgr.get_multiple_timeframes()
        results[f"{test_num}. All Timeframes"] = (
            f"✓ PASS ({len(all_data)}/{len(DEFAULT_TIMEFRAMES)} loaded)"
            if len(all_data) == len(DEFAULT_TIMEFRAMES)
            else f"⚠ WARN ({len(all_data)}/{len(DEFAULT_TIMEFRAMES)} loaded)"
        )

        # ── Test 7: Cache hoạt động ──
        test_num += 1
        log.info("\n[TEST %d] Kiểm tra cache...", test_num)
        cached_h1 = mgr.get_cached(Timeframe.H1)
        if cached_h1 is not None and len(cached_h1) > 0:
            results[f"{test_num}. Cache"] = f"✓ PASS ({len(cached_h1)} bars cached)"
        else:
            results[f"{test_num}. Cache"] = "✗ FAIL"

        # ── Test 8: Clear cache ──
        test_num += 1
        mgr.clear_cache()
        cleared = mgr.get_cached(Timeframe.H1) is None
        results[f"{test_num}. Clear Cache"] = "✓ PASS" if cleared else "✗ FAIL"

    finally:
        connector.disconnect()

    # ── Kết quả ──
    log.info("\n" + "=" * 60)
    log.info("  KẾT QUẢ INTEGRATION TEST — MARKET DATA")
    log.info("=" * 60)
    for test_name, status in results.items():
        log.info("  %s: %s", test_name, status)

    passed = sum(1 for v in results.values() if "PASS" in v)
    log.info("-" * 60)
    log.info("  Tổng: %d/%d passed", passed, len(results))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
