# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho MT5 Order Executor (Giai đoạn 1 & 2).

Mock tests — bảo đảm an toàn 100%, không cần kết nối MT5 terminal thật.
"""

from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import MetaTrader5 as mt5

from app.mt5.executor import MT5Executor, OrderResult, PositionInfo
from app.strategy.signal_models import SignalDirection
from config import MT5TradingConfig


FakeTerminalInfo = namedtuple("FakeTerminalInfo", ["connected", "trade_allowed"])
FakeAccountInfo = namedtuple(
    "FakeAccountInfo",
    ["login", "server", "name", "currency", "balance", "equity", "margin", "margin_free", "leverage", "trade_allowed", "trade_expert"],
)
FakeSymbolInfo = namedtuple("FakeSymbolInfo", ["filling_mode"])
FakeTick = namedtuple("FakeTick", ["ask", "bid"])
FakeOrderCheckResult = namedtuple("FakeOrderCheckResult", ["retcode", "comment"])
FakeOrderSendResult = namedtuple("FakeOrderSendResult", ["retcode", "order", "price", "comment"])
FakePosition = namedtuple("FakePosition", ["ticket", "symbol", "type", "volume", "price_open", "price_current", "sl", "tp", "profit", "magic", "comment", "time"])
FakeOrder = namedtuple("FakeOrder", ["ticket", "symbol", "type", "volume_current", "price_open", "sl", "tp", "magic", "comment", "time_setup"])


@pytest.fixture
def executor():
    cfg = MT5TradingConfig(
        enabled=True,
        symbol="XAUUSD",
        lot_size=0.01,
        max_open_positions=2,
        magic_number=888999,
        fast_tick_interval_ms=250,
    )
    return MT5Executor(config=cfg)


class TestFillingMode:
    """Kiểm tra logic tự động nhận diện phương thức khớp lệnh."""

    @patch("app.mt5.executor.mt5.symbol_info")
    def test_ioc_mode(self, mock_info, executor):
        mock_info.return_value = FakeSymbolInfo(filling_mode=2)  # bitmask 2 = IOC
        assert executor.get_filling_mode("XAUUSD") == mt5.ORDER_FILLING_IOC

    @patch("app.mt5.executor.mt5.symbol_info")
    def test_fok_mode(self, mock_info, executor):
        mock_info.return_value = FakeSymbolInfo(filling_mode=1)  # bitmask 1 = FOK
        assert executor.get_filling_mode("XAUUSD") == mt5.ORDER_FILLING_FOK

    @patch("app.mt5.executor.mt5.symbol_info")
    def test_return_mode(self, mock_info, executor):
        mock_info.return_value = FakeSymbolInfo(filling_mode=0)
        assert executor.get_filling_mode("XAUUSD") == mt5.ORDER_FILLING_RETURN


class TestTradeAllowed:
    """Kiểm tra điều kiện an toàn trước khi vào lệnh."""

    @patch("app.mt5.executor.mt5.account_info")
    @patch("app.mt5.executor.mt5.terminal_info")
    def test_algo_trading_disabled(self, mock_term, mock_acc, executor):
        mock_term.return_value = FakeTerminalInfo(connected=True, trade_allowed=False)
        mock_acc.return_value = FakeAccountInfo(
            login=409793, server="Demo", name="User", currency="USD",
            balance=2800.0, equity=2800.0, margin=0.0, margin_free=2800.0,
            leverage=500, trade_allowed=True, trade_expert=True,
        )
        ok, msg = executor.is_trade_allowed()
        assert ok is False
        assert "Algo Trading" in msg

    @patch("app.mt5.executor.mt5.account_info")
    @patch("app.mt5.executor.mt5.terminal_info")
    def test_trade_allowed_success(self, mock_term, mock_acc, executor):
        mock_term.return_value = FakeTerminalInfo(connected=True, trade_allowed=True)
        mock_acc.return_value = FakeAccountInfo(
            login=409793, server="Demo", name="User", currency="USD",
            balance=2800.0, equity=2800.0, margin=0.0, margin_free=2800.0,
            leverage=500, trade_allowed=True, trade_expert=True,
        )
        ok, msg = executor.is_trade_allowed()
        assert ok is True
        assert msg == "Sẵn sàng giao dịch"


class TestAccountSummary:
    """Kiểm tra truy vấn số dư và margin thời gian thực."""

    @patch("app.mt5.executor.mt5.account_info")
    def test_account_summary_disconnected(self, mock_acc, executor):
        mock_acc.return_value = None
        res = executor.get_account_summary()
        assert res["connected"] is False
        assert res["balance"] == 0.0

    @patch("app.mt5.executor.mt5.account_info")
    def test_account_summary_connected(self, mock_acc, executor):
        mock_acc.return_value = FakeAccountInfo(
            login=409793, server="DBGMarkets-Demo", name="Nguyen Van A", currency="USD",
            balance=2868.34, equity=2868.34, margin=0.0, margin_free=2868.34,
            leverage=500, trade_allowed=True, trade_expert=True,
        )
        res = executor.get_account_summary()
        assert res["connected"] is True
        assert res["balance"] == 2868.34
        assert res["leverage"] == 500
        assert res["trade_allowed"] is True


class TestMarketOrderExecution:
    """Kiểm tra vào lệnh thị trường kèm SL/TP ghim server."""

    @patch("app.mt5.executor.mt5.order_send")
    @patch("app.mt5.executor.mt5.order_check")
    @patch("app.mt5.executor.mt5.symbol_info_tick")
    @patch("app.mt5.executor.mt5.symbol_info")
    @patch.object(MT5Executor, "is_trade_allowed", return_value=(True, "OK"))
    def test_buy_market_order_success(self, mock_allow, mock_sym, mock_tick, mock_check, mock_send, executor):
        mock_sym.return_value = FakeSymbolInfo(filling_mode=2)
        mock_tick.return_value = FakeTick(ask=2750.50, bid=2750.20)
        mock_check.return_value = FakeOrderCheckResult(retcode=0, comment="Done")
        mock_send.return_value = FakeOrderSendResult(
            retcode=mt5.TRADE_RETCODE_DONE,
            order=1234567,
            price=2750.50,
            comment="Done",
        )

        res = executor.send_market_order(
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            volume=0.01,
            sl=2745.0,
            tp=2760.0,
            comment="VietKey AI",
        )

        assert res.success is True
        assert res.ticket == 1234567
        assert res.direction == "BUY"
        assert res.price == 2750.50
        assert res.sl == 2745.0
        assert res.tp == 2760.0

    @patch("app.mt5.executor.mt5.order_check")
    @patch("app.mt5.executor.mt5.symbol_info_tick")
    @patch("app.mt5.executor.mt5.symbol_info")
    @patch.object(MT5Executor, "is_trade_allowed", return_value=(True, "OK"))
    def test_market_order_check_rejected(self, mock_allow, mock_sym, mock_tick, mock_check, executor):
        mock_sym.return_value = FakeSymbolInfo(filling_mode=2)
        mock_tick.return_value = FakeTick(ask=2750.50, bid=2750.20)
        mock_check.return_value = FakeOrderCheckResult(retcode=10014, comment="Invalid volume")

        res = executor.send_market_order(
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            volume=0.001,
            sl=2745.0,
            tp=2760.0,
        )

        assert res.success is False
        assert "Invalid volume" in res.comment


class TestLimitOrderExecution:
    """Kiểm tra đặt lệnh chờ Limit."""

    @patch("app.mt5.executor.mt5.order_send")
    @patch("app.mt5.executor.mt5.order_check")
    @patch("app.mt5.executor.mt5.symbol_info")
    @patch.object(MT5Executor, "is_trade_allowed", return_value=(True, "OK"))
    def test_sell_limit_success(self, mock_allow, mock_sym, mock_check, mock_send, executor):
        mock_sym.return_value = FakeSymbolInfo(filling_mode=2)
        mock_check.return_value = FakeOrderCheckResult(retcode=0, comment="Done")
        mock_send.return_value = FakeOrderSendResult(
            retcode=mt5.TRADE_RETCODE_DONE,
            order=7654321,
            price=2760.0,
            comment="Done",
        )

        res = executor.send_limit_order(
            symbol="XAUUSD",
            direction=SignalDirection.SELL,
            price=2760.0,
            volume=0.01,
            sl=2765.0,
            tp=2750.0,
        )

        assert res.success is True
        assert res.ticket == 7654321
        assert res.direction == "SELL_LIMIT"


class TestPositionModificationAndClose:
    """Kiểm tra dời SL server-side và đóng lệnh khẩn cấp/chốt lời."""

    @patch("app.mt5.executor.mt5.order_send")
    @patch("app.mt5.executor.mt5.positions_get")
    def test_modify_sltp_success(self, mock_pos, mock_send, executor):
        mock_pos.return_value = [
            FakePosition(
                ticket=111, symbol="XAUUSD", type=mt5.ORDER_TYPE_BUY,
                volume=0.01, price_open=2750.0, price_current=2755.0,
                sl=2745.0, tp=2765.0, profit=5.0, magic=888999, comment="", time=1700000000,
            )
        ]
        mock_send.return_value = FakeOrderSendResult(
            retcode=mt5.TRADE_RETCODE_DONE, order=111, price=0.0, comment="Done"
        )

        ok = executor.modify_position_sltp(ticket=111, sl=2750.50)
        assert ok is True
        mock_send.assert_called_once()
        req = mock_send.call_args[0][0]
        assert req["action"] == mt5.TRADE_ACTION_SLTP
        assert req["sl"] == 2750.50

    @patch("app.mt5.executor.mt5.order_send")
    @patch("app.mt5.executor.mt5.symbol_info_tick")
    @patch("app.mt5.executor.mt5.symbol_info")
    @patch("app.mt5.executor.mt5.positions_get")
    def test_close_position_buy(self, mock_pos, mock_sym, mock_tick, mock_send, executor):
        mock_pos.return_value = [
            FakePosition(
                ticket=222, symbol="XAUUSD", type=mt5.ORDER_TYPE_BUY,
                volume=0.01, price_open=2750.0, price_current=2756.0,
                sl=2750.5, tp=2765.0, profit=6.0, magic=888999, comment="", time=1700000000,
            )
        ]
        mock_sym.return_value = FakeSymbolInfo(filling_mode=2)
        mock_tick.return_value = FakeTick(ask=2756.30, bid=2756.00)
        mock_send.return_value = FakeOrderSendResult(
            retcode=mt5.TRADE_RETCODE_DONE, order=222, price=2756.00, comment="Done"
        )

        res = executor.close_position(ticket=222, comment="TP Hit")
        assert res.success is True
        assert res.ticket == 222
        req = mock_send.call_args[0][0]
        assert req["action"] == mt5.TRADE_ACTION_DEAL
        assert req["type"] == mt5.ORDER_TYPE_SELL  # Đóng BUY thì gửi SELL
        assert req["price"] == 2756.00

    @patch("app.mt5.executor.mt5.order_send")
    def test_cancel_pending_order(self, mock_send, executor):
        mock_send.return_value = FakeOrderSendResult(
            retcode=mt5.TRADE_RETCODE_DONE, order=333, price=0.0, comment="Done"
        )
        ok = executor.cancel_order(ticket=333)
        assert ok is True
        req = mock_send.call_args[0][0]
        assert req["action"] == mt5.TRADE_ACTION_REMOVE
        assert req["order"] == 333
