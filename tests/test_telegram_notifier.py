# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Telegram Notifier.
"""

from unittest.mock import MagicMock
import pytest

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.telegram.client import TelegramClient, TelegramResponse
from app.telegram.notifier import TelegramNotifier
from config import TelegramConfig


def _make_signal(
    signal_id: str = "sig001",
    direction: SignalDirection = SignalDirection.BUY,
    status: SignalStatus = SignalStatus.ACTIVE,
) -> TradingSignal:
    return TradingSignal(
        signal_id=signal_id,
        direction=direction,
        status=status,
        symbol="XAUUSD",
        timeframe="H1",
        entry_price=2000.0,
        entry_zone_low=1999.0,
        entry_zone_high=2001.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        risk_reward_ratio=2.0,
        score=75.0,
        confidence="HIGH",
    )


class TestTelegramNotifier:
    """Test suite cho TelegramNotifier."""

    def test_notifier_initialization_defaults(self):
        """Khởi tạo Notifier với cấu hình và mock client."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        notifier = TelegramNotifier(client=mock_client)

        assert notifier.is_enabled is True
        assert notifier.total_sent == 0
        assert notifier.total_failed == 0

    def test_enable_and_disable_toggle(self):
        """Bật/tắt notifier bằng enable() và disable()."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        notifier = TelegramNotifier(client=mock_client)

        assert notifier.is_enabled is True
        notifier.disable()
        assert notifier.is_enabled is False
        notifier.enable()
        assert notifier.is_enabled is True

    def test_send_signal_disabled_does_not_send(self):
        """Khi notifier bị tắt -> không gọi client.send_message."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        notifier = TelegramNotifier(client=mock_client)
        notifier.disable()

        sig = _make_signal()
        res = notifier.send_signal(sig)

        assert res is False
        mock_client.send_message.assert_not_called()

    def test_send_signal_wait_skipped_by_default(self):
        """Tín hiệu WAIT mặc định được bỏ qua (send_wait_signals=False)."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        notifier = TelegramNotifier(client=mock_client, send_wait_signals=False)

        sig_wait = _make_signal(direction=SignalDirection.WAIT)
        res = notifier.send_signal(sig_wait)

        assert res is True  # Bỏ qua hợp lệ
        mock_client.send_message.assert_not_called()

    def test_send_signal_wait_sent_when_enabled(self):
        """Tín hiệu WAIT được gửi khi send_wait_signals=True."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=1)
        notifier = TelegramNotifier(client=mock_client, send_wait_signals=True)

        sig_wait = _make_signal(direction=SignalDirection.WAIT)
        res = notifier.send_signal(sig_wait)

        assert res is True
        mock_client.send_message.assert_called_once()
        assert notifier.total_sent == 1

    def test_send_signal_buy_success_and_duplicate_prevention(self):
        """Gửi tín hiệu BUY thành công và ngăn gửi lại lần 2 (duplicate protection)."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=101)
        notifier = TelegramNotifier(client=mock_client)

        sig = _make_signal()

        # Lần 1: Gửi thành công
        res1 = notifier.send_signal(sig)
        assert res1 is True
        mock_client.send_message.assert_called_once()
        assert notifier.total_sent == 1

        # Lần 2: Cùng tín hiệu -> Chặn không gửi lại
        res2 = notifier.send_signal(sig)
        assert res2 is True
        assert mock_client.send_message.call_count == 1  # Vẫn chỉ gọi 1 lần

        # Lần 3: force=True -> Vẫn cho phép gửi lại
        res3 = notifier.send_signal(sig, force=True)
        assert res3 is True
        assert mock_client.send_message.call_count == 2
        assert notifier.total_sent == 2

    def test_send_signal_update_lifecycle(self):
        """Gửi cập nhật trạng thái theo vòng đời tín hiệu (ENTRY -> TP)."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=202)
        notifier = TelegramNotifier(client=mock_client)

        sig = _make_signal()

        # Cập nhật 1: ENTRY_REACHED
        sig.status = SignalStatus.ENTRY_REACHED
        res1 = notifier.send_signal_update(sig, price=2000.5)
        assert res1 is True
        assert mock_client.send_message.call_count == 1

        # Cập nhật 1 lần nữa với cùng status -> Chặn trùng lặp
        res_dup = notifier.send_signal_update(sig, price=2000.8)
        assert res_dup is True
        assert mock_client.send_message.call_count == 1

        # Cập nhật 2: TP_REACHED
        sig.status = SignalStatus.TP_REACHED
        res2 = notifier.send_signal_update(sig, price=2020.0)
        assert res2 is True
        assert mock_client.send_message.call_count == 2

    def test_send_system_event(self):
        """Gửi thông báo sự kiện hệ thống."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=303)
        notifier = TelegramNotifier(client=mock_client)

        res = notifier.send_system_event("STARTUP", "Hệ thống sẵn sàng.")
        assert res is True
        mock_client.send_message.assert_called_once()
        assert notifier.total_sent == 1

    def test_clear_cache(self):
        """Xóa bộ nhớ đệm chống trùng lặp."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=404)
        notifier = TelegramNotifier(client=mock_client)

        sig = _make_signal()
        notifier.send_signal(sig)
        assert notifier.is_already_sent(sig.signal_id, sig.status) is True

        notifier.clear_cache()
        assert notifier.is_already_sent(sig.signal_id, sig.status) is False

    def test_resend_signal_forces_delivery(self):
        """resend_signal gửi lại tin nhắn ngay cả khi đã có trong cache trùng lặp."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=505)
        notifier = TelegramNotifier(client=mock_client)

        sig = _make_signal(signal_id="resend001")
        # Gửi lần 1
        notifier.send_signal(sig)
        assert mock_client.send_message.call_count == 1

        # Gửi lại qua resend_signal
        res = notifier.resend_signal(sig)
        assert res is True
        assert mock_client.send_message.call_count == 2

    def test_send_news_broadcast(self):
        """Bắn bản tin kinh tế & dự báo xu hướng Vàng lên Telegram."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=606)
        notifier = TelegramNotifier(client=mock_client)

        res = notifier.send_news_broadcast(
            title="Non-Farm Employment Change",
            country="USD",
            impact="High",
            forecast="150K",
            previous="142K",
            bias_direction="BUY",
            reasoning="Tăng trưởng việc làm suy yếu hỗ trợ vàng tăng.",
        )
        assert res is True
        mock_client.send_message.assert_called_once()
        msg_arg = mock_client.send_message.call_args[0][0]
        assert "BẢN TIN KINH TẾ" in msg_arg
        assert "LỜI CẢNH BÁO" in msg_arg

    def test_send_custom_broadcast(self):
        """Gửi thông báo nhanh Admin lên Telegram."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=707)
        notifier = TelegramNotifier(client=mock_client)

        res = notifier.send_custom_broadcast("Cảnh báo biến động mạnh đầu phiên Mỹ!")
        assert res is True
        mock_client.send_message.assert_called_once()
        msg_arg = mock_client.send_message.call_args[0][0]
        assert "THÔNG BÁO TỪ BAN QUẢN TRỊ" in msg_arg
        assert "Cảnh báo biến động mạnh" in msg_arg

    def test_send_trade_outcome_summary(self):
        """Bắn thông báo tổng hợp kết quả lệnh lên Telegram kèm pips và stats."""
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.is_configured = True
        mock_client.send_message.return_value = TelegramResponse(ok=True, message_id=808)
        notifier = TelegramNotifier(client=mock_client)

        sig = _make_signal(signal_id="outcome_test_01")
        res = notifier.send_trade_outcome_summary(
            signal_or_data=sig,
            exit_price=2020.0,
            pnl_points=20.0,
            duration_str="30 phút",
            stats={"total": 2, "wins": 2, "losses": 0, "win_rate": 100.0, "profit_factor": 5.0, "net_pips": 400.0, "net_points": 40.0},
        )
        assert res is True
        mock_client.send_message.assert_called_once()
        msg_arg = mock_client.send_message.call_args[0][0]
        assert "TỔNG HỢP LỆNH VỪA KHỚP: CHỐT LÃI (+200.0 PIPS)" in msg_arg
        assert "+200.0 PIPS" in msg_arg

        # Kiểm tra chống gửi lặp (deduplication)
        res_dup = notifier.send_trade_outcome_summary(
            signal_or_data=sig,
            exit_price=2020.0,
            pnl_points=20.0,
        )
        assert res_dup is True
        assert mock_client.send_message.call_count == 1  # Không gửi lần 2 vì bị chặn duplicate

