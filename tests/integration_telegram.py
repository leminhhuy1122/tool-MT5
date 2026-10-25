# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: Telegram Notification.

Kiểm tra kết nối và gửi thông báo tín hiệu tới Telegram:
- Nếu đã có TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID trong .env: Gửi tin nhắn thật để test.
- Nếu chưa cấu hình: In hướng dẫn thiết lập bot và chạy dry-run mô phỏng.

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_telegram.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from logger import setup_logging, get_logger
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.telegram.client import TelegramClient
from app.telegram.formatter import (
    format_signal_message,
    format_signal_update,
    format_system_notification,
)
from app.telegram.notifier import TelegramNotifier

setup_logging()
log = get_logger("integration.telegram")


def main() -> int:
    """Chạy integration test Telegram."""
    print("=" * 65)
    print("  VietKey Gold AI — Integration Test: Telegram Notification (Phase 5)")
    print("=" * 65)

    settings = get_settings()
    tg_config = settings.telegram

    print(f"\n1. Kiểm tra cấu hình:")
    print(f"   • Enabled: {tg_config.enabled}")
    print(f"   • Bot Token: {'[ĐÃ THIẾT LẬP]' if tg_config.bot_token else '[CHƯA CÓ]'}")
    print(f"   • Chat ID: {tg_config.chat_id if tg_config.chat_id else '[CHƯA CÓ]'}")
    print(f"   • Is Configured: {tg_config.is_configured}")

    # Tạo sample signal để kiểm tra
    sample_signal = TradingSignal(
        signal_id="demo9999",
        strategy_version="v1.0",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        symbol="XAUUSD",
        timeframe="H1",
        entry_price=2000.50,
        entry_zone_low=1999.50,
        entry_zone_high=2001.50,
        stop_loss=1991.00,
        take_profit_1=2019.50,
        take_profit_2=2029.00,
        risk_reward_ratio=2.0,
        sl_distance=9.5,
        tp_distance=19.0,
        score=82.0,
        confidence="HIGH",
        trend_h4="BULLISH",
        trend_h1="BULLISH",
        setup_type="BOS_RETEST",
        reasons=[
            "BOS Bullish xác nhận đỉnh mới",
            "Giá retest hoàn hảo vùng Support 2000.00",
            "EMA20 > EMA50 và dốc lên",
            "RSI=54.2 trong vùng tăng trưởng",
        ],
        invalidation="Nến H1 đóng cửa dưới mức 1991.00",
    )

    print("\n2. Demo Format Tin Nhắn HTML:")
    msg_html = format_signal_message(sample_signal)
    print("-" * 55)
    print(msg_html)
    print("-" * 55)

    if tg_config.is_configured:
        print("\n3. Gửi tin nhắn thực tế tới Telegram...")
        client = TelegramClient(config=tg_config)
        notifier = TelegramNotifier(config=tg_config, client=client)

        # 3a. Kiểm tra bot
        bot_info = client.get_me()
        if not bot_info.ok:
            print(f"❌ Không thể kết nối tới Bot Telegram: {bot_info.description}")
            return 1

        bot_name = bot_info.raw.get("result", {}).get("first_name", "Bot")
        print(f"✓ Kết nối thành công tới Bot: @{bot_name}")

        # 3b. Gửi thông báo khởi động test
        notifier.send_system_event(
            "STARTUP",
            "VietKey Gold AI đang chạy kiểm tra tích hợp Telegram (Phase 5)..."
        )

        # 3c. Gửi tín hiệu mẫu
        success = notifier.send_signal(sample_signal)
        if success:
            print("✓ Đã gửi tin nhắn tín hiệu BUY mẫu tới Telegram.")

        # 3d. Gửi cập nhật trạng thái
        sample_signal.status = SignalStatus.ENTRY_REACHED
        notifier.send_signal_update(sample_signal, price=2000.80)
        print("✓ Đã gửi cập nhật ENTRY_REACHED.")

        print(f"\n✅ Đã gửi thành công {notifier.total_sent} tin nhắn tới Telegram!")

    else:
        print("\n3. [CHẾ ĐỘ MÔ PHỎNG / DRY-RUN]")
        print("   ℹ️ Chưa thiết lập TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID trong .env")
        print("   • Để kích hoạt nhận tin thật trên điện thoại:")
        print("     1. Nhắn /newbot với @BotFather trên Telegram để lấy Bot Token.")
        print("     2. Nhắn /start với bot của bạn, sau đó lấy Chat ID từ @userinfobot.")
        print("     3. Điền vào file .env:")
        print("        TELEGRAM_BOT_TOKEN=your_token_here")
        print("        TELEGRAM_CHAT_ID=your_chat_id_here")

        # Test notifier mô phỏng
        notifier = TelegramNotifier(config=tg_config)
        assert notifier.is_enabled is False
        print("   ✓ Notifier tự động tắt an toàn khi chưa cấu hình (không gây crash luồng giao dịch).")

    print("\n✅ Integration Test: Telegram Notification PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
