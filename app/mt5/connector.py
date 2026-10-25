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
        """Kiểm tra MT5 đang kết nối hay không, tự động khôi phục nếu terminal đang chạy."""
        try:
            info = mt5.terminal_info()
            if info is not None and info.connected:
                self._connected = True
                return True
        except Exception:
            pass

        # Nếu chưa kết nối, thử gắn kết nối trực tiếp vào terminal đang chạy
        try:
            if mt5.initialize():
                info = mt5.terminal_info()
                if info is not None:
                    self._connected = True
                    return True
        except Exception:
            pass

        self._connected = False
        return False

    def connect(self) -> ConnectionResult:
        """
        Kết nối tới MT5 terminal.

        Returns:
            ConnectionResult với trạng thái và thông tin lỗi.
        """
        log.info("Đang kết nối MetaTrader 5...")

        # 1. Thử kết nối trực tiếp vào terminal đang chạy (nhanh & ổn định nhất)
        try:
            if mt5.initialize():
                info = mt5.terminal_info()
                acc = mt5.account_info()
                if info is not None and acc is not None:
                    self._connected = True
                    log.info("✓ Đã gắn kết nối MT5 terminal đang chạy (Login: %s, Server: %s)", acc.login, acc.server)
                    return ConnectionResult(success=True, message=f"Đã kết nối MetaTrader 5 (Account: {acc.login})")
        except Exception as e:
            log.warning("Thử initialize() không tham số thất bại: %s", e)

        # 2. Chuẩn bị tham số khởi tạo nếu cần khởi động hoặc đăng nhập cụ thể
        init_kwargs: dict = {}

        term_path = (self._config.terminal_path or "").strip().strip("'\"")
        if term_path and os.path.isfile(term_path):
            init_kwargs["path"] = term_path
        elif not term_path:
            # Kiểm tra đường dẫn mặc định nếu có
            default_path = os.path.expanduser(r"~\AppData\Roaming\DBG Markets MetaTrader 5\terminal64.exe")
            if os.path.isfile(default_path):
                init_kwargs["path"] = default_path

        if self._config.login:
            init_kwargs["login"] = self._config.login
        if self._config.password:
            init_kwargs["password"] = self._config.password.strip().strip("'\"")
        if self._config.server:
            init_kwargs["server"] = self._config.server.strip().strip("'\"")

        success = False
        try:
            if init_kwargs:
                success = mt5.initialize(**init_kwargs)
            else:
                success = mt5.initialize()
        except Exception as e:
            log.error("Lỗi ngoại lệ khi khởi tạo MT5: %s", e)

        if not success:
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
