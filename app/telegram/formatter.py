# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Telegram Message Formatter.

Định dạng tin nhắn Telegram ngắn gọn, súc tích và chuẩn phong cách giao dịch Gold:
- Tín hiệu giao dịch mới (BUY / SELL / WAIT).
- Cập nhật trạng thái tín hiệu (ENTRY / TP / SL / INVALIDATED / EXPIRED).
- Hướng dẫn quản lý lệnh cụ thể (dời SL hòa vốn, chốt 1 phần, nuôi TP).

LƯU Ý:
- Định dạng HTML an toàn, không bị lỗi cú pháp ký tự đặc biệt.
- Tiếng Việt có dấu chuẩn UTF-8.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal


# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))


def _to_vn_time_str(dt: Optional[datetime] = None) -> str:
    """Chuyển đổi datetime sang chuỗi giờ Việt Nam (HH:MM dd/mm)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    vn_time = dt.astimezone(VN_TZ)
    return vn_time.strftime("%H:%M %d/%m")


def format_signal_message(signal: TradingSignal) -> str:
    """
    Định dạng tin nhắn tín hiệu ngắn gọn, trực quan và dễ vào lệnh.

    Args:
        signal: TradingSignal cần gửi.

    Returns:
        Chuỗi HTML sẵn sàng gửi Telegram.
    """
    time_str = _to_vn_time_str(signal.created_at)

    # 1. Trạng thái WAIT
    if signal.is_wait:
        reason_text = signal.reasons[0] if signal.reasons else "Thị trường tích lũy / Chưa có setup đạt chuẩn"
        return (
            "⏳ <b>GOLD (XAUUSD) — CHỜ SETUP (WAIT)</b>\n"
            f"⏱ Khung: <b>{signal.timeframe}</b> | Xu hướng H4: <b>{signal.trend_h4 or 'NEUTRAL'}</b>\n"
            f"👉 <i>{reason_text}</i>\n"
            f"⏰ <i>{time_str} (VN)</i> | Kiên nhẫn chờ nến tiếp theo..."
        )

    # 2. Tín hiệu BUY hoặc SELL
    action = signal.direction.value.upper()
    icon = "🏆" if signal.is_buy else "🔴"
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol

    # TP2 nếu có
    tp2_line = f"\n✅ <b>TP2:</b> <code>{signal.take_profit_2:.1f}</code>" if signal.take_profit_2 > 0 else ""

    # Setup tag
    setup_tag = f"• Setup: <code>{signal.setup_type}</code>" if signal.setup_type else ""
    invalidation_line = f"\n• Hủy setup nếu: <i>{signal.invalidation}</i>" if signal.invalidation else ""

    msg = (
        f"{icon} <b>{action} {sym}: <code>{signal.entry_price:.1f}</code></b>\n"
        f"⏱ Khung: {signal.timeframe} | Mã: <code>#{signal.signal_id}</code>\n"
        f"❌ <b>SL:</b> <code>{signal.stop_loss:.1f}</code> ({signal.sl_distance:.1f} giá)\n"
        f"✅ <b>TP1:</b> <code>{signal.take_profit_1:.1f}</code> ({signal.tp_distance:.1f} giá)"
        f"{tp2_line}\n"
        f"⚖️ R:R: 1:{signal.risk_reward_ratio:.1f} | Điểm: <b>{signal.score:.0f}/100</b> ({signal.confidence})\n\n"
        "👉 <b>Lưu ý quản lý lệnh:</b>\n"
        "• Entry (điểm vào lệnh) ±1 giá.\n"
        "• Lãi 5 giá → Kéo SL về hòa vốn (BE).\n"
        "• Lãi 10 giá → Chốt 1 phần, kéo SL dương nuôi TP."
    )

    if setup_tag or invalidation_line:
        msg += f"\n{setup_tag}{invalidation_line}"

    msg += f"\n⏰ <i>{time_str} (VN) | {signal.strategy_version}</i>"

    return msg


def format_signal_update(
    signal: TradingSignal,
    price: float,
    custom_message: Optional[str] = None,
) -> str:
    """
    Định dạng tin nhắn cập nhật trạng thái ngắn gọn theo diễn biến thị trường.

    Args:
        signal: TradingSignal đang theo dõi.
        price: Giá thị trường tại thời điểm cập nhật.
        custom_message: Thông báo tùy biến thêm.

    Returns:
        Chuỗi HTML cập nhật.
    """
    action = signal.direction.value.upper()
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol
    time_str = _to_vn_time_str()

    if signal.status == SignalStatus.ENTRY_REACHED:
        return (
            f"🎯 <b>KHỚP ENTRY: {action} {sym} @ <code>{price:.1f}</code></b> [<code>#{signal.signal_id}</code>]\n"
            f"❌ SL: <code>{signal.stop_loss:.1f}</code> | ✅ TP1: <code>{signal.take_profit_1:.1f}</code>\n"
            "👉 Đã khớp lệnh. Lãi 5 giá nhớ kéo SL về hòa vốn!\n"
            f"⏰ <i>{time_str} (VN)</i>"
        )

    elif signal.status == SignalStatus.TP_REACHED:
        return (
            f"🎉 <b>TAKE PROFIT THÀNH CÔNG! {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n"
            f"✅ Chạm TP1: <code>{signal.take_profit_1:.1f}</code> (+{signal.tp_distance:.1f} giá) | <b>+{signal.risk_reward_ratio:.1f}R</b>\n"
            "👉 Chốt 1 phần, dời SL dương để gồng tiếp TP2!\n"
            f"⏰ <i>{time_str} (VN)</i>"
        )

    elif signal.status == SignalStatus.SL_REACHED:
        return (
            f"❌ <b>STOP LOSS: {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n"
            f"📍 Mức SL: <code>{signal.stop_loss:.1f}</code> (-{signal.sl_distance:.1f} giá)\n"
            "🛡 Tuân thủ kỷ luật bảo toàn vốn. Chờ setup mới!\n"
            f"⏰ <i>{time_str} (VN)</i>"
        )

    elif signal.status == SignalStatus.INVALIDATED:
        reason = custom_message or "Giá vi phạm điều kiện trước khi khớp Entry"
        return (
            f"⚠️ <b>HỦY SETUP: {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n"
            f"📝 Lý do: <i>{reason}</i>\n"
            "👉 Không vào lệnh theo tín hiệu này nữa.\n"
            f"⏰ <i>{time_str} (VN)</i>"
        )

    elif signal.status == SignalStatus.EXPIRED:
        return (
            f"⌛ <b>HẾT HẠN: {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n"
            "Hết thời gian hiệu lực, giá chưa chạm vùng Entry. Đóng theo dõi!\n"
            f"⏰ <i>{time_str} (VN)</i>"
        )

    return (
        f"ℹ️ <b>CẬP NHẬT: {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n"
        f"Trạng thái: <b>{signal.status.value}</b> | Giá: <code>{price:.1f}</code>\n"
        f"⏰ <i>{time_str} (VN)</i>"
    )


def format_early_exit_alert(
    signal: TradingSignal,
    close_price: float,
    invalidation_level: float,
) -> str:
    """
    Định dạng tin nhắn cảnh báo thoát lệnh sớm (Early Structural Exit) khi nến M5 đóng vi phạm vùng bảo vệ.
    """
    action = signal.direction.value.upper()
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol
    time_str = _to_vn_time_str()

    saved_pts = abs(signal.stop_loss - close_price)
    saved_pips = saved_pts * 10.0

    return (
        f"⚠️ <b>CẢNH BÁO CẤU TRÚC (THOÁT LỆNH SỚM): {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n\n"
        f"📌 <b>Hiện tượng:</b> Nến M5 vừa đóng cửa tại <code>{close_price:.2f}</code>, vi phạm vùng phòng thủ (Mức vô hiệu: <code>{invalidation_level:.2f}</code>).\n"
        f"💡 <b>Khuyến nghị:</b> Cắt lỗ sớm quanh <code>{close_price:.2f}</code> để bảo toàn vốn thay vì chờ cắn đủ Hard SL <code>{signal.stop_loss:.2f}</code>!\n"
        f"🛡 <b>Tiết kiệm rủi ro:</b> Giảm thiểu được ~<code>{saved_pts:.1f} giá</code> (~{saved_pips:.0f} pips) lỗ so với SL 10 giá.\n"
        f"⏰ <i>{time_str} (VN) | Quản trị rủi ro chủ động</i>"
    )


def format_system_notification(event_type: str, message: str) -> str:
    """
    Định dạng tin nhắn thông báo sự kiện hệ thống ngắn gọn.
    """
    icons = {
        "STARTUP": "🚀",
        "SHUTDOWN": "🛑",
        "DISCONNECT": "⚠️",
        "CONNECT": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
    }
    icon = icons.get(event_type.upper(), "🤖")
    time_str = _to_vn_time_str()

    return (
        f"{icon} <b>HỆ THỐNG: {event_type.upper()}</b>\n"
        f"{message}\n"
        f"⏰ <i>{time_str} (VN)</i>"
    )


def format_news_broadcast(
    title: str,
    country: str,
    impact: str,
    forecast: str = "",
    previous: str = "",
    bias_direction: str = "WAIT",
    reasoning: str = "",
    custom_note: Optional[str] = None,
) -> str:
    """
    Định dạng bản tin kinh tế & dự báo xu hướng Vàng kèm lời cảnh báo miễn trừ trách nhiệm.
    """
    time_str = _to_vn_time_str()

    bias_dir = bias_direction.upper()
    if "BUY" in bias_dir or "BULLISH" in bias_dir:
        bias_badge = "🟢 <b>KỲ VỌNG: BUY VÀNG (BULLISH ↗)</b>"
    elif "SELL" in bias_dir or "BEARISH" in bias_dir:
        bias_badge = "🔴 <b>KỲ VỌNG: SELL VÀNG (BEARISH ↘)</b>"
    else:
        bias_badge = "🟡 <b>KỲ VỌNG: RUNG LẮC 2 ĐẦU / ĐỨNG NGOÀI (WAIT ⏳)</b>"

    impact_label = "🔴 TIN ĐỎ (HIGH)" if impact.upper() == "HIGH" else ("🟠 TIN CAM (MEDIUM)" if impact.upper() == "MEDIUM" else f"⚪ {impact.upper()}")

    lines = [
        "📰 <b>BẢN TIN KINH TẾ & DỰ BÁO XU HƯỚNG VÀNG</b>",
        f"⏱ <i>{time_str} (VN)</i> | Nguồn: <b>ForexFactory / Global News</b>",
        "───────────────────────────────",
        f"📌 Sự kiện: <b>{title}</b> (<code>{country}</code>)",
        f"⚡ Mức độ ảnh hưởng: <b>{impact_label}</b>",
    ]
    if forecast or previous:
        lines.append(f"📊 Dự báo: <code>{forecast or 'N/A'}</code> | Kỳ trước: <code>{previous or 'N/A'}</code>")

    lines.extend([
        "",
        bias_badge,
        f"👉 <b>Phân tích AI:</b> <i>{reasoning or 'Thị trường có thể biến động mạnh trong khung giờ tin tức.'}</i>",
    ])

    if custom_note:
        lines.extend(["", f"💬 <b>Lời nhắn Admin:</b> <i>{custom_note}</i>"])

    lines.extend([
        "",
        "⚠️ <b>LỜI CẢNH BÁO:</b> <i>Đây chỉ là dự đoán tham khảo dựa trên phân tích dữ liệu, không cam kết đúng 100%. Quý nhà đầu tư luôn tuân thủ quản trị rủi ro!</i>",
    ])

    return "\n".join(lines)


def format_custom_announcement(message: str) -> str:
    """
    Định dạng thông báo nhanh từ Admin gửi tới Kênh Telegram.
    """
    time_str = _to_vn_time_str()
    return (
        "📢 <b>THÔNG BÁO TỪ BAN QUẢN TRỊ VIETKEY GOLD</b>\n"
        f"⏱ <i>{time_str} (VN)</i>\n"
        "───────────────────────────────\n"
        f"{message}\n"
        "───────────────────────────────\n"
        "🏆 <i>VietKey Gold AI — Chúc quý nhà đầu tư giao dịch thành công!</i>"
    )
