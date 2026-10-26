# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Telegram Notifier.

Bộ điều phối thông báo Telegram:
- Nhận TradingSignal và cập nhật trạng thái từ SignalEngine / MT5Connector.
- Định dạng tin nhắn qua Formatter.
- Gửi tin nhắn qua TelegramClient.
- Quản lý trạng thái Bật/Tắt (Toggle enabled/disabled).
- Chống gửi lặp thông báo (Duplicate Notification Protection).
"""

from datetime import datetime, timezone
from typing import Any, Optional

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.telegram.client import TelegramClient, TelegramResponse
from app.telegram.formatter import (
    format_custom_announcement,
    format_early_exit_alert,
    format_news_broadcast,
    format_signal_message,
    format_signal_update,
    format_system_notification,
    format_trade_outcome_summary,
)
from config import TelegramConfig
from logger import get_logger

log = get_logger("telegram.notifier")


class TelegramNotifier:
    """
    Quản lý thông báo Telegram cho hệ thống VietKey Gold AI.
    """

    def __init__(
        self,
        config: Optional[TelegramConfig] = None,
        client: Optional[TelegramClient] = None,
        send_wait_signals: bool = False,
    ):
        self.config = config or TelegramConfig()
        self.client = client or TelegramClient(config=self.config)
        self.send_wait_signals = send_wait_signals
        self._enabled = self.config.enabled

        # Bộ nhớ lưu vết các thông báo đã gửi để chống trùng lặp: key = "{signal_id}_{status}"
        self._sent_keys: set[str] = set()

        # Thống kê
        self.total_sent: int = 0
        self.total_failed: int = 0

        log.info(
            "Đã khởi tạo TelegramNotifier (enabled=%s, send_wait=%s)",
            self._enabled, self.send_wait_signals,
        )

    @property
    def is_enabled(self) -> bool:
        """Kiểm tra notifier có đang bật và client sẵn sàng hay không."""
        return self._enabled and self.client.is_configured

    def enable(self) -> None:
        """Bật tính năng thông báo Telegram."""
        self._enabled = True
        log.info("Đã BẬT thông báo Telegram.")

    def disable(self) -> None:
        """Tắt tính năng thông báo Telegram."""
        self._enabled = False
        log.info("Đã TẮT thông báo Telegram.")

    def _make_key(self, signal_id: str, status: SignalStatus) -> str:
        """Tạo định danh duy nhất cho một lần phát tín hiệu/cập nhật."""
        return f"{signal_id}_{status.value}"

    def is_already_sent(self, signal_id: str, status: SignalStatus) -> bool:
        """Kiểm tra thông báo này đã được gửi trước đó hay chưa."""
        return self._make_key(signal_id, status) in self._sent_keys

    def send_signal(self, signal: TradingSignal, force: bool = False) -> bool:
        """
        Gửi thông báo tín hiệu mới (BUY / SELL hoặc WAIT).

        Args:
            signal: TradingSignal cần phát.
            force: Bỏ qua kiểm tra trùng lặp nếu True.

        Returns:
            True nếu gửi thành công (hoặc bỏ qua hợp lệ), False nếu lỗi mạng.
        """
        # Nếu là WAIT và cấu hình không gửi WAIT
        if signal.is_wait and not self.send_wait_signals and not force:
            log.debug("Bỏ qua gửi tín hiệu WAIT theo cấu hình.")
            return True

        if not self.is_enabled and not force:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        # Kiểm tra trùng lặp
        key = self._make_key(signal.signal_id, signal.status)
        if not force and key in self._sent_keys:
            log.info("Trùng lặp: Thông báo cho tín hiệu [%s] trạng thái %s đã được gửi.",
                     signal.signal_id, signal.status.value)
            return True

        text = format_signal_message(signal)
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self._sent_keys.add(key)
            self.total_sent += 1
            log.info("✓ Đã gửi tin nhắn tín hiệu [%s] %s tới Telegram.",
                     signal.signal_id, signal.direction.value)
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi tín hiệu [%s] thất bại: %s", signal.signal_id, resp.description)
            return False

    def send_signal_update(
        self,
        signal: TradingSignal,
        price: float,
        custom_message: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """
        Gửi thông báo cập nhật trạng thái tín hiệu (ENTRY / TP / SL / INVALIDATED / EXPIRED).

        Args:
            signal: TradingSignal đang được cập nhật.
            price: Giá thị trường hiện tại.
            custom_message: Lời nhắn bổ sung nếu có.
            force: Bỏ qua kiểm tra trùng lặp nếu True.

        Returns:
            True nếu gửi thành công.
        """
        if not self.is_enabled and not force:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        key = self._make_key(signal.signal_id, signal.status)
        if not force and key in self._sent_keys:
            log.info("Trùng lặp: Cập nhật trạng thái %s cho [%s] đã được gửi.",
                     signal.status.value, signal.signal_id)
            return True

        text = format_signal_update(signal, price=price, custom_message=custom_message)
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self._sent_keys.add(key)
            self.total_sent += 1
            log.info("✓ Đã gửi cập nhật trạng thái %s [%s] tới Telegram.",
                     signal.status.value, signal.signal_id)
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi cập nhật trạng thái [%s] thất bại: %s", signal.signal_id, resp.description)
            return False

    def notify_signal(self, signal: TradingSignal, force: bool = False) -> bool:
        """Alias cho send_signal."""
        return self.send_signal(signal, force=force)

    def notify_status_update(
        self,
        signal: TradingSignal,
        price: float,
        custom_message: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """Alias cho send_signal_update."""
        return self.send_signal_update(signal, price=price, custom_message=custom_message, force=force)

    def send_early_exit_alert(
        self,
        signal: TradingSignal,
        close_price: float,
        invalidation_level: float,
    ) -> bool:
        """
        Gửi cảnh báo thoát lệnh sớm (Early Structural Exit) khi nến M5 đóng vi phạm Order Block/FVG.
        """
        if not self.is_enabled:
            return False

        key = f"{signal.signal_id}_EARLY_EXIT"
        if key in self._sent_keys:
            log.info("Cảnh báo Early Exit cho [%s] đã được gửi trước đó, bỏ qua lặp.", signal.signal_id)
            return True

        text = format_early_exit_alert(
            signal=signal,
            close_price=close_price,
            invalidation_level=invalidation_level,
        )
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self._sent_keys.add(key)
            self.total_sent += 1
            log.info("✓ Đã gửi cảnh báo thoát lệnh sớm [%s] tới Telegram.", signal.signal_id)
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi cảnh báo thoát lệnh sớm [%s] thất bại: %s", signal.signal_id, resp.description)
            return False

    def send_system_event(self, event_type: str, message: str) -> bool:
        """
        Gửi thông báo sự kiện hệ thống (khởi động, cảnh báo, lỗi kết nối MT5...).

        Args:
            event_type: Loại sự kiện (STARTUP, SHUTDOWN, WARNING, ERROR, v.v.).
            message: Chi tiết sự kiện.

        Returns:
            True nếu gửi thành công.
        """
        if not self.is_enabled:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        text = format_system_notification(event_type, message)
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self.total_sent += 1
            log.info("✓ Đã gửi thông báo hệ thống [%s] tới Telegram.", event_type)
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi thông báo hệ thống thất bại: %s", resp.description)
            return False

    def resend_signal(self, signal: TradingSignal) -> bool:
        """
        Gửi lại tín hiệu giao dịch theo yêu cầu thủ công của Admin (bỏ qua chống trùng lặp).
        """
        log.info("Admin kích hoạt gửi lại tín hiệu [%s] lên Telegram.", signal.signal_id)
        return self.send_signal(signal, force=True)

    def send_news_broadcast(
        self,
        title: str,
        country: str,
        impact: str,
        forecast: str = "",
        previous: str = "",
        bias_direction: str = "WAIT",
        reasoning: str = "",
        custom_note: Optional[str] = None,
    ) -> bool:
        """
        Bắn bản tin kinh tế và dự báo xu hướng Vàng lên Kênh Telegram.
        """
        if not self.is_enabled:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        text = format_news_broadcast(
            title=title,
            country=country,
            impact=impact,
            forecast=forecast,
            previous=previous,
            bias_direction=bias_direction,
            reasoning=reasoning,
            custom_note=custom_note,
        )
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self.total_sent += 1
            log.info("✓ Đã gửi bản tin kinh tế [%s] tới Telegram.", title)
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi bản tin kinh tế thất bại: %s", resp.description)
            return False

    def send_custom_broadcast(self, message: str) -> bool:
        """
        Gửi thông báo nhanh từ Admin tới Kênh Telegram.
        """
        if not self.is_enabled:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        text = format_custom_announcement(message)
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self.total_sent += 1
            log.info("✓ Đã gửi thông báo Admin tới Telegram.")
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi thông báo Admin thất bại: %s", resp.description)
            return False

    def send_raw_message(self, text: str) -> bool:
        """
        Gửi trực tiếp nội dung bài viết / bản tin (HTML format) tới Kênh Telegram.
        """
        if not self.is_enabled:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        resp: TelegramResponse = self.client.send_message(text)
        if resp.ok:
            self.total_sent += 1
            log.info("✓ Đã gửi bài viết tài chính / lịch kinh tế tới Telegram.")
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi bài viết tới Telegram thất bại: %s", resp.description)
            return False

    def send_trade_outcome_summary(
        self,
        signal_or_data: Any,
        exit_price: float,
        pnl_points: float,
        duration_str: Optional[str] = None,
        stats: Optional[dict] = None,
        force: bool = False,
    ) -> bool:
        """
        Gửi thông báo tổng hợp kết quả lệnh vừa khớp/vừa đóng (Lời/Lỗ bao nhiêu Pip) lên Telegram.

        Args:
            signal_or_data: TradingSignal hoặc dict chứa thông tin lệnh.
            exit_price: Mức giá đóng lệnh thực tế.
            pnl_points: Số điểm lãi/lỗ (+ hoặc -).
            duration_str: Chuỗi thời gian nắm giữ lệnh (ví dụ '45 phút').
            stats: Thống kê hiệu suất tài khoản tích lũy (winrate, net pips, PF...).
            force: Bỏ qua kiểm tra trùng lặp nếu True.

        Returns:
            True nếu gửi thành công.
        """
        if not self.is_enabled and not force:
            log.debug("TelegramNotifier đang tắt hoặc chưa cấu hình.")
            return False

        if hasattr(signal_or_data, "signal_id"):
            sig_id = signal_or_data.signal_id
        elif isinstance(signal_or_data, dict):
            sig_id = signal_or_data.get("signal_id", "unknown")
        else:
            sig_id = "unknown"

        key = f"{sig_id}_OUTCOME_SUMMARY"
        if not force and key in self._sent_keys:
            log.info("Trùng lặp: Thông báo tổng hợp lệnh [%s] đã được gửi trước đó.", sig_id)
            return True

        text = format_trade_outcome_summary(
            signal_or_data=signal_or_data,
            exit_price=exit_price,
            pnl_points=pnl_points,
            duration_str=duration_str,
            stats=stats,
        )
        resp: TelegramResponse = self.client.send_message(text)

        if resp.ok:
            self._sent_keys.add(key)
            self.total_sent += 1
            log.info("✓ Đã gửi thông báo tổng hợp kết quả lệnh [%s] (PnL: %.2f pts) tới Telegram.",
                     sig_id, pnl_points)
            return True
        else:
            self.total_failed += 1
            log.error("✗ Gửi thông báo tổng hợp kết quả [%s] thất bại: %s", sig_id, resp.description)
            return False

    def clear_cache(self) -> None:
        """Xóa bộ nhớ đệm chống trùng lặp."""
        self._sent_keys.clear()
        log.debug("Đã xóa bộ nhớ đệm chống trùng lặp.")


