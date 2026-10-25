# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho MT5 Connector.

Sử dụng mock — không cần MT5 terminal thật để chạy.
Kiểm tra:
- Kết nối thành công / thất bại.
- Retry logic.
- Disconnect.
- Context manager.
- Terminal info.
"""

from unittest.mock import patch, MagicMock, PropertyMock
from collections import namedtuple

import pytest

from config import MT5Config
from app.mt5.connector import MT5Connector, ConnectionResult


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────
@pytest.fixture
def mt5_config() -> MT5Config:
    """Config MT5 cho testing."""
    return MT5Config(
        login=12345,
        password="test_pass",
        server="TestServer-Demo",
        terminal_path=r"C:\MT5\terminal64.exe",
        symbol="XAUUSD",
    )


@pytest.fixture
def connector(mt5_config: MT5Config) -> MT5Connector:
    """MT5Connector instance cho testing."""
    return MT5Connector(mt5_config)


# ──────────────────────────────────────────────
# TestConnectionResult
# ──────────────────────────────────────────────
class TestConnectionResult:
    """Test ConnectionResult dataclass."""

    def test_success_str(self) -> None:
        r = ConnectionResult(success=True, message="Connected")
        assert "✓" in str(r)

    def test_failure_str(self) -> None:
        r = ConnectionResult(success=False, message="Failed", error_code=1)
        assert "✗" in str(r)
        assert "1" in str(r)

    def test_frozen(self) -> None:
        r = ConnectionResult(success=True, message="OK")
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore


# ──────────────────────────────────────────────
# TestMT5Connector
# ──────────────────────────────────────────────
class TestMT5Connector:
    """Test MT5Connector class."""

    def test_initial_state_not_connected(self, connector: MT5Connector) -> None:
        assert connector._connected is False

    @patch("app.mt5.connector.mt5")
    def test_connect_success(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        mock_mt5.initialize.return_value = True

        result = connector.connect()

        assert result.success is True
        assert connector._connected is True
        mock_mt5.initialize.assert_called_once()

    @patch("app.mt5.connector.mt5")
    def test_connect_with_credentials(self, mock_mt5: MagicMock, mt5_config: MT5Config) -> None:
        mock_mt5.initialize.return_value = True
        conn = MT5Connector(mt5_config)

        conn.connect()

        # Kiểm tra các tham số được truyền
        call_kwargs = mock_mt5.initialize.call_args[1]
        assert call_kwargs["login"] == 12345
        assert call_kwargs["password"] == "test_pass"
        assert call_kwargs["server"] == "TestServer-Demo"
        assert call_kwargs["path"] == r"C:\MT5\terminal64.exe"

    @patch("app.mt5.connector.mt5")
    def test_connect_failure(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        mock_mt5.initialize.return_value = False
        mock_mt5.last_error.return_value = (-1, "Connection failed")

        result = connector.connect()

        assert result.success is False
        assert result.error_code == -1
        assert connector._connected is False

    @patch("app.mt5.connector.mt5")
    def test_connect_no_credentials(self, mock_mt5: MagicMock) -> None:
        """Kết nối không có credentials (MT5 terminal đã đăng nhập)."""
        mock_mt5.initialize.return_value = True
        config = MT5Config()  # tất cả default/rỗng
        conn = MT5Connector(config)

        conn.connect()

        # Khi không có credentials, gọi initialize() không tham số
        mock_mt5.initialize.assert_called_once_with()

    @patch("app.mt5.connector.mt5")
    def test_disconnect(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        connector._connected = True

        connector.disconnect()

        assert connector._connected is False
        mock_mt5.shutdown.assert_called_once()

    @patch("app.mt5.connector.mt5")
    def test_disconnect_when_not_connected(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        connector._connected = False

        connector.disconnect()

        mock_mt5.shutdown.assert_not_called()

    @patch("app.mt5.connector.mt5")
    def test_is_connected_true(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        connector._connected = True
        TerminalInfo = namedtuple("TerminalInfo", ["build", "connected"])
        mock_mt5.terminal_info.return_value = TerminalInfo(build=1000, connected=True)

        assert connector.is_connected is True

    @patch("app.mt5.connector.mt5")
    def test_is_connected_false_when_flag_false(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        connector._connected = False
        assert connector.is_connected is False

    @patch("app.mt5.connector.mt5")
    def test_is_connected_false_when_terminal_returns_none(
        self, mock_mt5: MagicMock, connector: MT5Connector
    ) -> None:
        connector._connected = True
        mock_mt5.terminal_info.return_value = None

        assert connector.is_connected is False
        assert connector._connected is False  # flag cũng reset

    @patch("app.mt5.connector.mt5")
    def test_context_manager(self, mock_mt5: MagicMock, mt5_config: MT5Config) -> None:
        mock_mt5.initialize.return_value = True

        with MT5Connector(mt5_config) as conn:
            mock_mt5.initialize.assert_called_once()
            assert conn._connected is True

        mock_mt5.shutdown.assert_called_once()

    @patch("app.mt5.connector.mt5")
    def test_get_terminal_info_success(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        connector._connected = True
        TerminalInfo = namedtuple("TerminalInfo", ["build", "connected", "name"])
        mock_mt5.terminal_info.return_value = TerminalInfo(
            build=3700, connected=True, name="MetaTrader 5"
        )

        info = connector.get_terminal_info()

        assert info is not None
        assert info["build"] == 3700
        assert info["name"] == "MetaTrader 5"

    @patch("app.mt5.connector.mt5")
    def test_get_terminal_info_not_connected(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        connector._connected = False

        info = connector.get_terminal_info()

        assert info is None


class TestConnectWithRetry:
    """Test retry logic."""

    @patch("app.mt5.connector.mt5")
    def test_retry_succeeds_on_second_attempt(
        self, mock_mt5: MagicMock, connector: MT5Connector
    ) -> None:
        # Lần 1: thất bại, lần 2: thành công
        mock_mt5.initialize.side_effect = [False, True]
        mock_mt5.last_error.return_value = (-1, "Connection failed")

        result = connector.connect_with_retry(max_retries=3, base_delay=0.01)

        assert result.success is True
        assert mock_mt5.initialize.call_count == 2

    @patch("app.mt5.connector.mt5")
    def test_retry_all_fail(self, mock_mt5: MagicMock, connector: MT5Connector) -> None:
        mock_mt5.initialize.return_value = False
        mock_mt5.last_error.return_value = (-1, "Connection failed")

        result = connector.connect_with_retry(max_retries=2, base_delay=0.01)

        assert result.success is False
        assert mock_mt5.initialize.call_count == 2

    @patch("app.mt5.connector.mt5")
    def test_retry_succeeds_immediately(
        self, mock_mt5: MagicMock, connector: MT5Connector
    ) -> None:
        mock_mt5.initialize.return_value = True

        result = connector.connect_with_retry(max_retries=3, base_delay=0.01)

        assert result.success is True
        assert mock_mt5.initialize.call_count == 1
