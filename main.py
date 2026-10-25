# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Main Application Entry Point.

Khởi động hệ thống:
- python main.py          : Khởi động Live Bot Runner (vòng lặp phân tích và theo dõi tín hiệu)
- python main.py --check  : Kiểm tra môi trường kết nối
- python main.py --once   : Chạy 1 chu kỳ kiểm tra nến và thoát
- python main.py --server : Khởi động Backend API Server (Uvicorn port 8000)
"""

import argparse
import sys

from config import Settings, get_settings
from logger import get_logger, setup_logging


def check_environment(settings: Settings) -> dict[str, bool]:
    """
    Kiểm tra môi trường chạy.

    Returns:
        Dictionary với trạng thái từng thành phần.
    """
    log = get_logger("startup")
    status: dict[str, bool] = {}

    # ── Kiểm tra Python version ──
    py_version = sys.version
    log.info("Python version: %s", py_version)
    status["python"] = sys.version_info >= (3, 10)
    if not status["python"]:
        log.warning("Khuyến nghị Python >= 3.10")

    # ── Kiểm tra MetaTrader5 package ──
    try:
        import MetaTrader5 as mt5  # noqa: F401
        status["mt5_package"] = True
        log.info("MetaTrader5 package: ĐÃ CÀI ✓")
    except ImportError:
        status["mt5_package"] = False
        log.warning("MetaTrader5 package: CHƯA CÀI ✗ (chạy: pip install MetaTrader5)")

    # ── Kiểm tra cấu hình MT5 ──
    mt5_configured = bool(settings.mt5.login and settings.mt5.server)
    status["mt5_config"] = mt5_configured
    if mt5_configured:
        log.info("MT5 config: ĐÃ CẤU HÌNH ✓ (server=%s)", settings.mt5.server)
    else:
        log.info("MT5 config: CHƯA CẤU HÌNH (cập nhật file .env)")

    # ── Kiểm tra cấu hình Telegram ──
    tg_configured = bool(settings.telegram.bot_token and settings.telegram.chat_id)
    status["telegram_config"] = tg_configured
    if tg_configured:
        log.info("Telegram config: ĐÃ CẤU HÌNH ✓")
    else:
        log.info("Telegram config: CHƯA CẤU HÌNH (cập nhật file .env)")

    return status


def main() -> None:
    """Hàm chính — khởi động ứng dụng."""
    parser = argparse.ArgumentParser(description="VietKey Gold AI Trading Signal Engine")
    parser.add_argument("--check", action="store_true", help="Kiểm tra môi trường và cấu hình")
    parser.add_argument("--once", action="store_true", help="Chạy một chu kỳ phân tích rồi thoát")
    parser.add_argument("--server", action="store_true", help="Khởi động FastAPI Backend Server")
    parser.add_argument("--client", action="store_true", help="Khởi động Desktop Client cửa sổ riêng biệt")
    parser.add_argument("--interval", type=float, default=5.0, help="Chu kỳ polling (giây)")

    args = parser.parse_args()

    # Load settings
    settings = get_settings()

    # Setup logging
    setup_logging(log_level=settings.app.log_level)
    log = get_logger("main")

    log.info("=" * 60)
    log.info("  VIETKEY GOLD AI — Institutional Trading System")
    log.info("  Symbol: %s | Timeframe: M5", settings.mt5.symbol)
    log.info("=" * 60)

    # Chế độ kiểm tra
    if args.check:
        log.info("Kiểm tra môi trường hệ thống...")
        status = check_environment(settings)
        all_ok = all(status.values())
        log.info("Kết quả: %s", "TẤT CẢ SẴN SÀNG ✓" if all_ok else "CẦN HOÀN THIỆN CẤU HÌNH")
        return

    # Chế độ Desktop Client (Native Window)
    if args.client:
        from client import launch_desktop_client
        log.info("Khởi chạy Desktop Client độc lập...")
        launch_desktop_client()
        return

    # Chế độ API Server
    if args.server:
        import uvicorn
        log.info("Khởi chạy Backend API Server trên http://127.0.0.1:8000...")
        uvicorn.run("app.api.server:app", host="127.0.0.1", port=8000, reload=False)
        return

    # Khởi động LiveBotRunner
    from app.bot.runner import LiveBotRunner
    runner = LiveBotRunner(settings=settings)

    if args.once:
        log.info("Thực thi một chu kỳ kiểm tra (single-run mode)...")
        runner.start()
        sig = runner.run_once()
        if sig:
            log.info("Kết quả phân tích: %s %s @ %.2f (Score: %.1f)",
                     sig.direction.value, sig.symbol, sig.entry_price, sig.score)
        else:
            log.info("Không có tín hiệu mới hoặc chưa đóng nến M5.")
        runner.stop()
        return

    # Mặc định: Chạy vòng lặp thời gian thực
    log.info("Bắt đầu Live Bot Runner liên tục...")
    runner.run_forever(poll_interval_sec=args.interval)


if __name__ == "__main__":
    main()
