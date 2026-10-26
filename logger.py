# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Logging Setup.

Thiết lập logging cho toàn bộ ứng dụng.
- Console handler: hiển thị trên terminal.
- File handler: lưu vào thư mục logs/.
- Format chuẩn với timestamp, level, module.
"""

import logging
from logging.handlers import RotatingFileHandler
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_to_file: bool = True,
) -> logging.Logger:
    """
    Thiết lập logging cho ứng dụng.

    Args:
        log_level: Mức log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Thư mục chứa file log. Mặc định: ./logs/
        log_to_file: Có ghi log ra file hay không.

    Returns:
        Root logger đã được cấu hình.
    """
    # Xác định log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Format
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Root logger
    root_logger = logging.getLogger("vietkey")
    root_logger.setLevel(numeric_level)

    # Xóa handlers cũ (tránh duplicate khi gọi lại)
    root_logger.handlers.clear()

    # ── Console Handler ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        logging.Formatter(log_format, datefmt=date_format)
    )
    root_logger.addHandler(console_handler)

    # ── File Handler ──
    if log_to_file:
        if log_dir is None:
            log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"vietkey_{today}.log"
        # Rotating file handler: giới hạn 10MB mỗi file, tối đa 5 file backups
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            mode="a",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(log_format, datefmt=date_format)
        )
        root_logger.addHandler(file_handler)

        root_logger.info("Log file (rotating 10MB): %s", log_file)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Lấy logger con theo tên module.

    Args:
        name: Tên module (ví dụ: 'mt5_connector', 'signal_engine').

    Returns:
        Logger con kế thừa cấu hình từ root logger 'vietkey'.
    """
    return logging.getLogger(f"vietkey.{name}")
