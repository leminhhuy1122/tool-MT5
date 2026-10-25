# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Kiểm tra kết nối Telegram và tự động phát hiện Chat ID.
"""

import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings


def test_telegram():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    settings = get_settings()
    token = settings.telegram.bot_token
    chat_id = settings.telegram.chat_id

    print("=" * 60)
    print("  VIETKEY GOLD AI — KIỂM TRA TELEGRAM BOT")
    print("=" * 60)

    if not token:
        print("[LỖI] TELEGRAM_BOT_TOKEN chưa được điền trong file .env!")
        return

    # 1. Kiểm tra thông tin Bot
    try:
        url_me = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url_me, headers={"User-Agent": "VietKeyBot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            bot_user = data["result"]["username"]
            bot_name = data["result"]["first_name"]
            print(f"✓ Đã kết nối thành công tới Bot: {bot_name} (@{bot_user})")
    except Exception as e:
        print(f"[LỖI] Không thể kết nối tới Telegram API: {e}")
        return

    # 2. Kiểm tra xem người dùng đã bấm START chưa
    try:
        url_updates = f"https://api.telegram.org/bot{token}/getUpdates"
        req = urllib.request.Request(url_updates, headers={"User-Agent": "VietKeyBot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            updates = json.loads(resp.read().decode("utf-8")).get("result", [])
    except Exception as e:
        print(f"[CẢNH BÁO] Không thể đọc getUpdates: {e}")
        updates = []

    detected_id = None
    if updates:
        for upd in reversed(updates):
            msg = upd.get("message") or upd.get("channel_post")
            if msg and "chat" in msg:
                detected_id = str(msg["chat"]["id"])
                user_name = msg["chat"].get("first_name") or msg["chat"].get("title") or "User"
                print(f"✓ Phát hiện tin nhắn gần nhất từ: {user_name} (ID: {detected_id})")
                break

    target_id = chat_id or detected_id

    if not target_id:
        print("\n" + "=" * 60)
        print("👉 HƯỚNG DẪN KÍCH HOẠT:")
        print(f"1. Mở Telegram, tìm kiếm bot: @{bot_user}")
        print(f"   (hoặc nhấn vào liên kết: https://t.me/{bot_user})")
        print("2. Nhấn nút START (hoặc gửi tin nhắn: 'Xin chào') cho bot.")
        print("3. Chạy lại script này để kiểm tra!")
        print("=" * 60)
        return

    # 3. Thử gửi tin nhắn
    print(f"\nĐang gửi tin nhắn thử nghiệm tới Chat ID: {target_id}...")
    sample_text = (
        "🏆 <b>BUY GOLD: 4003.00</b>\n"
        "❌ <b>SL:</b> 3989.00\n"
        "✅ <b>TP1:</b> 4013.00 (+10 giá)\n"
        "✅ <b>TP2:</b> 4025.00\n\n"
        "👉 <b>Lưu ý:</b> Entry (điểm vào lệnh) ±1 giá.\n"
        "• Lãi 5 giá → Kéo SL hòa vốn.\n"
        "• Lãi 10 giá → Chốt 50% TP1, kéo SL dương nuôi TP2.\n\n"
        "🎉 <i>Xin chào! Bot VietKey Gold AI đã kết nối thành công với Telegram của bạn!</i>"
    )

    payload = {
        "chat_id": target_id,
        "text": sample_text,
        "parse_mode": "HTML",
    }

    try:
        url_send = f"https://api.telegram.org/bot{token}/sendMessage"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url_send,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "VietKeyBot"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("\n🎉 THÀNH CÔNG RỰC RỠ!")
            print("✓ Tin nhắn tín hiệu test đã được gửi tới Telegram của bạn!")
            print("✓ Bạn hãy mở ứng dụng Telegram để kiểm tra tin nhắn ngay nhé!")
    except urllib.error.HTTPError as he:
        body = he.read().decode("utf-8")
        print(f"\n[LỖI GỬI TIN NHẮN]: {he.code} - {he.reason}")
        print(f"Chi tiết: {body}")
        if "chat not found" in body.lower():
            print("\n👉 NGUYÊN NHÂN: Bot chưa được bạn bấm START!")
            print(f"Vui lòng vào link https://t.me/{bot_user} và bấm nút 'START', sau đó chạy lại lệnh test.")
    except Exception as e:
        print(f"\n[LỖI]: {e}")


if __name__ == "__main__":
    test_telegram()
