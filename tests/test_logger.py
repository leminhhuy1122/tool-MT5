# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho logger.py

Kiểm tra:
- setup_logging tạo logger đúng.
- Logger có handlers.
- get_logger trả về child logger.
- File log được tạo đúng thư mục.
"""

import logging
import tempfile
from pathlib import Path

from logger import setup_logging, get_logger


class TestSetupLogging:
    """Test setup_logging function."""

    def test_returns_logger(self) -> None:
        logger = setup_logging(log_level="DEBUG", log_to_file=False)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "vietkey"

    def test_logger_has_console_handler(self) -> None:
        logger = setup_logging(log_level="INFO", log_to_file=False)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types

    def test_logger_level_set_correctly(self) -> None:
        logger = setup_logging(log_level="WARNING", log_to_file=False)
        assert logger.level == logging.WARNING

    def test_file_handler_creates_log_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            logger = setup_logging(
                log_level="DEBUG", log_dir=log_dir, log_to_file=True
            )
            assert log_dir.exists()
            log_files = list(log_dir.glob("vietkey_*.log"))
            assert len(log_files) >= 1
            # Đóng tất cả handlers để giải phóng file lock trên Windows
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_no_duplicate_handlers_on_rerun(self) -> None:
        setup_logging(log_level="INFO", log_to_file=False)
        logger = setup_logging(log_level="INFO", log_to_file=False)
        # Chỉ có 1 console handler sau khi gọi lại
        assert len(logger.handlers) == 1


class TestGetLogger:
    """Test get_logger function."""

    def test_returns_child_logger(self) -> None:
        logger = get_logger("test_module")
        assert logger.name == "vietkey.test_module"

    def test_different_names_different_loggers(self) -> None:
        a = get_logger("module_a")
        b = get_logger("module_b")
        assert a is not b
        assert a.name != b.name
