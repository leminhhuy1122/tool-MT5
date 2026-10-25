# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho MT5 Symbol Info.

Mock tests — không cần MT5 terminal thật.
"""

from collections import namedtuple
from unittest.mock import patch, MagicMock

import pytest

from app.mt5.symbol_info import SymbolInfo, check_symbol, get_symbol_info


# ──────────────────────────────────────────────
# Mock data
# ──────────────────────────────────────────────
def _make_mt5_symbol_info(
    name: str = "XAUUSD",
    description: str = "Gold vs US Dollar",
    visible: bool = True,
    trade_mode: int = 4,
) -> namedtuple:
    """Helper tạo mock symbol info."""
    SymInfo = namedtuple("SymbolInfo", [
        "name", "description", "point", "digits", "spread",
        "trade_mode", "volume_min", "volume_max", "volume_step",
        "bid", "ask", "visible",
    ])
    return SymInfo(
        name=name, description=description, point=0.01, digits=2,
        spread=30, trade_mode=trade_mode, volume_min=0.01,
        volume_max=100.0, volume_step=0.01, bid=2650.50,
        ask=2650.80, visible=visible,
    )


# ──────────────────────────────────────────────
# TestSymbolInfo
# ──────────────────────────────────────────────
class TestSymbolInfo:
    """Test SymbolInfo dataclass."""

    def test_spread_value(self) -> None:
        sym = SymbolInfo(
            name="XAUUSD", description="Gold", point=0.01, digits=2,
            spread=30, trade_mode=4, volume_min=0.01, volume_max=100,
            volume_step=0.01, bid=2650.50, ask=2650.80, visible=True,
        )
        assert sym.spread_value == pytest.approx(0.30)

    def test_is_tradeable_true(self) -> None:
        sym = SymbolInfo(
            name="XAUUSD", description="Gold", point=0.01, digits=2,
            spread=30, trade_mode=4, volume_min=0.01, volume_max=100,
            volume_step=0.01, bid=2650.50, ask=2650.80, visible=True,
        )
        assert sym.is_tradeable is True

    def test_is_tradeable_false(self) -> None:
        sym = SymbolInfo(
            name="XAUUSD", description="Gold", point=0.01, digits=2,
            spread=30, trade_mode=0, volume_min=0.01, volume_max=100,
            volume_step=0.01, bid=2650.50, ask=2650.80, visible=True,
        )
        assert sym.is_tradeable is False

    def test_frozen(self) -> None:
        sym = SymbolInfo(
            name="XAUUSD", description="Gold", point=0.01, digits=2,
            spread=30, trade_mode=4, volume_min=0.01, volume_max=100,
            volume_step=0.01, bid=2650.50, ask=2650.80, visible=True,
        )
        with pytest.raises(AttributeError):
            sym.bid = 9999  # type: ignore


# ──────────────────────────────────────────────
# TestCheckSymbol
# ──────────────────────────────────────────────
class TestCheckSymbol:
    """Test check_symbol function."""

    @patch("app.mt5.symbol_info.mt5")
    def test_symbol_exists_and_visible(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info.return_value = _make_mt5_symbol_info(visible=True)

        result = check_symbol("XAUUSD")

        assert result is True

    @patch("app.mt5.symbol_info.mt5")
    def test_symbol_not_found(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info.return_value = None

        result = check_symbol("INVALID")

        assert result is False

    @patch("app.mt5.symbol_info.mt5")
    def test_symbol_not_visible_auto_select(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info.return_value = _make_mt5_symbol_info(visible=False)
        mock_mt5.symbol_select.return_value = True

        result = check_symbol("XAUUSD")

        assert result is True
        mock_mt5.symbol_select.assert_called_once_with("XAUUSD", True)

    @patch("app.mt5.symbol_info.mt5")
    def test_symbol_select_fails(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info.return_value = _make_mt5_symbol_info(visible=False)
        mock_mt5.symbol_select.return_value = False

        result = check_symbol("XAUUSD")

        assert result is False


# ──────────────────────────────────────────────
# TestGetSymbolInfo
# ──────────────────────────────────────────────
class TestGetSymbolInfo:
    """Test get_symbol_info function."""

    @patch("app.mt5.symbol_info.mt5")
    def test_success(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info.return_value = _make_mt5_symbol_info()

        result = get_symbol_info("XAUUSD")

        assert result is not None
        assert result.name == "XAUUSD"
        assert result.bid == 2650.50
        assert result.ask == 2650.80
        assert result.digits == 2

    @patch("app.mt5.symbol_info.mt5")
    def test_returns_none_on_failure(self, mock_mt5: MagicMock) -> None:
        mock_mt5.symbol_info.return_value = None
        mock_mt5.last_error.return_value = (-1, "Symbol not found")

        result = get_symbol_info("INVALID")

        assert result is None
