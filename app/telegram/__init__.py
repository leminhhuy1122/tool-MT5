# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Telegram Notification Package.

Cung cấp các công cụ kết nối và phát thông báo qua Telegram:
- TelegramClient, TelegramResponse
- TelegramNotifier
- Message formatters: format_signal_message, format_signal_update, format_system_notification
"""

from app.telegram.client import TelegramClient, TelegramResponse
from app.telegram.formatter import (
    format_signal_message,
    format_signal_update,
    format_system_notification,
)
from app.telegram.notifier import TelegramNotifier

__all__ = [
    "TelegramClient",
    "TelegramResponse",
    "TelegramNotifier",
    "format_signal_message",
    "format_signal_update",
    "format_system_notification",
]
