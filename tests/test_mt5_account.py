# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho MT5 Account Info.

Mock tests — không cần MT5 terminal thật.
"""

from collections import namedtuple
from unittest.mock import patch, MagicMock

import pytest

from app.mt5.account_info import AccountInfo, get_account_info


# ──────────────────────────────────────────────
# TestAccountInfo dataclass
# ──────────────────────────────────────────────
class TestAccountInfo:
    """Test AccountInfo dataclass."""

    def test_is_demo_true(self) -> None:
        acc = AccountInfo(
            login=123, server="Demo", name="Test", currency="USD",
            balance=10000, equity=10000, margin=0, margin_free=10000,
            leverage=100, trade_mode=0,
        )
        assert acc.is_demo is True
        assert acc.trade_mode_name == "DEMO"

    def test_is_demo_false_for_real(self) -> None:
        acc = AccountInfo(
            login=123, server="Real", name="Test", currency="USD",
            balance=10000, equity=10000, margin=0, margin_free=10000,
            leverage=100, trade_mode=2,
        )
        assert acc.is_demo is False
        assert acc.trade_mode_name == "REAL"

    def test_contest_mode(self) -> None:
        acc = AccountInfo(
            login=123, server="Contest", name="Test", currency="USD",
            balance=10000, equity=10000, margin=0, margin_free=10000,
            leverage=100, trade_mode=1,
        )
        assert acc.is_demo is False
        assert acc.trade_mode_name == "CONTEST"

    def test_frozen(self) -> None:
        acc = AccountInfo(
            login=123, server="Demo", name="Test", currency="USD",
            balance=10000, equity=10000, margin=0, margin_free=10000,
            leverage=100, trade_mode=0,
        )
        with pytest.raises(AttributeError):
            acc.balance = 999  # type: ignore


# ──────────────────────────────────────────────
# TestGetAccountInfo
# ──────────────────────────────────────────────
class TestGetAccountInfo:
    """Test get_account_info function."""

    @patch("app.mt5.account_info.mt5")
    def test_success(self, mock_mt5: MagicMock) -> None:
        AccInfo = namedtuple("AccountInfo", [
            "login", "server", "name", "currency",
            "balance", "equity", "margin", "margin_free",
            "leverage", "trade_mode",
        ])
        mock_mt5.account_info.return_value = AccInfo(
            login=12345, server="TestServer-Demo", name="Test User",
            currency="USD", balance=10000.0, equity=10000.0,
            margin=0.0, margin_free=10000.0, leverage=100, trade_mode=0,
        )

        result = get_account_info()

        assert result is not None
        assert result.login == 12345
        assert result.server == "TestServer-Demo"
        assert result.balance == 10000.0
        assert result.is_demo is True

    @patch("app.mt5.account_info.mt5")
    def test_returns_none_on_failure(self, mock_mt5: MagicMock) -> None:
        mock_mt5.account_info.return_value = None
        mock_mt5.last_error.return_value = (-1, "Not connected")

        result = get_account_info()

        assert result is None

    @patch("app.mt5.account_info.mt5")
    def test_warns_on_real_account(self, mock_mt5: MagicMock) -> None:
        AccInfo = namedtuple("AccountInfo", [
            "login", "server", "name", "currency",
            "balance", "equity", "margin", "margin_free",
            "leverage", "trade_mode",
        ])
        mock_mt5.account_info.return_value = AccInfo(
            login=99999, server="RealServer", name="Real User",
            currency="USD", balance=50000.0, equity=50000.0,
            margin=0.0, margin_free=50000.0, leverage=500, trade_mode=2,
        )

        result = get_account_info()

        assert result is not None
        assert result.is_demo is False
        assert result.trade_mode_name == "REAL"
