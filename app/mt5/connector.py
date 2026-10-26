# -*- coding: utf-8 -*-
"""
VietKey Gold AI — MT5 Connector.

Quản lý kết nối MetaTrader 5:
- Khởi tạo và kết nối MT5 terminal.
- Kiểm tra trạng thái kết nối.
- Retry với exponential backoff.
- Graceful shutdown.

KHÔNG có chức năng đặt lệnh (order/trade).
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

import MetaTrader5 as mt5

from app.mt5.lock import mt5_lock
from config import MT5Config
from logger import get_logger

log = get_logger("mt5.connector")


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
MAX_RETRIES: int = 3
BASE_DELAY: float = 2.0  # giây — delay cơ bản cho exponential backoff
MAX_DELAY: float = 30.0  # giây — delay tối đa


# ──────────────────────────────────────────────
# Kết quả kết nối
# ──────────────────────────────────────────────
@dataclass(frozen=True)
class ConnectionResult:
    """Kết quả của lần kết nối MT5."""

    success: bool
    message: str
    error_code: Optional[int] = None

    def __str__(self) -> str:
        if self.success:
            return f"✓ {self.message}"
        return f"✗ {self.message} (error_code={self.error_code})"


# ──────────────────────────────────────────────
# MT5 Connector Class
# ──────────────────────────────────────────────
class MT5Connector:
    """
    Quản lý kết nối tới MetaTrader 5.

    Sử dụng:
        connector = MT5Connector(config)
        result = connector.connect()
        if result.success:
            # làm việc với MT5...
            connector.disconnect()

    KHÔNG có phương thức đặt lệnh.
    """

    def __init__(self, config: MT5Config) -> None:
        """
        Khởi tạo connector.

        Args:
            config: Cấu hình MT5 từ environment.
        """
        self._config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Kiểm tra MT5 đang kết nối hay không."""
        if not self._connected:
            return False
        # Kiểm tra thực tế bằng terminal_info
        try:
            with mt5_lock:
                info = mt5.terminal_info()
            if info is None:
                self._connected = False
                return False
            return True
        except Exception:
            self._connected = False
            return False

    def connect(self) -> ConnectionResult:
        """
        Kết nối tới MT5 terminal.

        Returns:
            ConnectionResult với trạng thái và thông tin lỗi.
        """
        log.info("Đang kết nối MetaTrader 5...")

        # Chuẩn bị tham số khởi tạo
        init_kwargs: dict = {}

        term_path = (self._config.terminal_path or "").strip().strip("'\"")
        if term_path and (os.path.isfile(term_path) or term_path.lower().endswith(".exe")):
            init_kwargs["path"] = term_path

        if self._config.login:
            init_kwargs["login"] = self._config.login
        if self._config.password:
            init_kwargs["password"] = self._config.password.strip().strip("'\"")
        if self._config.server:
            init_kwargs["server"] = self._config.server.strip().strip("'\"")

        success = False
        try:
            with mt5_lock:
                if init_kwargs:
                    success = mt5.initialize(**init_kwargs)
                else:
                    success = mt5.initialize()
        except Exception as e:
            log.error("Lỗi ngoại lệ khi khởi tạo MT5: %s", e)

        if not success:
            with mt5_lock:
                error_code = mt5.last_error()
            error_msg = f"Không thể khởi tạo MT5: {error_code}"
            log.error(error_msg)
            self._connected = False
            return ConnectionResult(
                success=False,
                message=error_msg,
                error_code=error_code[0] if error_code else None,
            )

        self._connected = True
        log.info("✓ Đã kết nối MetaTrader 5")
        return ConnectionResult(success=True, message="Đã kết nối MetaTrader 5")

    def connect_with_retry(
        self,
        max_retries: int = MAX_RETRIES,
        base_delay: float = BASE_DELAY,
        max_delay: float = MAX_DELAY,
    ) -> ConnectionResult:
        """
        Kết nối MT5 với exponential backoff retry.

        Args:
            max_retries: Số lần thử tối đa.
            base_delay: Delay cơ bản (giây).
            max_delay: Delay tối đa (giây).

        Returns:
            ConnectionResult của lần thử cuối cùng.
        """
        last_result = ConnectionResult(success=False, message="Chưa thử kết nối")

        for attempt in range(1, max_retries + 1):
            log.info("Lần thử kết nối %d/%d", attempt, max_retries)
            last_result = self.connect()

            if last_result.success:
                return last_result

            if attempt < max_retries:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                log.warning(
                    "Kết nối thất bại. Thử lại sau %.1f giây...", delay
                )
                time.sleep(delay)

        log.error(
            "Đã thử %d lần nhưng không thể kết nối MT5.", max_retries
        )
        return last_result

    def disconnect(self) -> None:
        """Ngắt kết nối MT5 an toàn."""
        if self._connected:
            with mt5_lock:
                mt5.shutdown()
            self._connected = False
            log.info("Đã ngắt kết nối MetaTrader 5")

    def get_terminal_info(self) -> Optional[dict]:
        """
        Lấy thông tin MT5 terminal.

        Returns:
            Dictionary chứa thông tin terminal, hoặc None nếu lỗi.
        """
        if not self.is_connected:
            log.warning("MT5 chưa kết nối. Gọi connect() trước.")
            return None

        with mt5_lock:
            info = mt5.terminal_info()
        if info is None:
            log.error("Không lấy được terminal info")
            return None

        # Chuyển NamedTuple sang dict
        info_dict = info._asdict()
        log.debug("Terminal info: build=%s, connected=%s",
                   info_dict.get("build"), info_dict.get("connected"))
        return info_dict

    def __enter__(self) -> "MT5Connector":
        """Context manager — kết nối khi vào."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager — ngắt kết nối khi ra."""
        self.disconnect()

    def __del__(self) -> None:
        """Đảm bảo ngắt kết nối khi object bị garbage collected."""
        self.disconnect()
