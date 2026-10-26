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
from typing import Any, Optional

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


def _render_score_bar(score: float) -> str:
    """Vẽ thanh tiến trình trực quan cho Confluence Score (0-100)."""
    blocks = max(0, min(10, int(round(score / 10.0))))
    return "█" * blocks + "░" * (10 - blocks)


def _format_breakdown_summary(score_breakdown: Optional[dict]) -> str:
    """Tạo dòng tóm tắt ngắn gọn các yếu tố hội tụ (Tier, Session, Regime)."""
    if not score_breakdown or not isinstance(score_breakdown, dict):
        return ""
    tier = score_breakdown.get("confidence_tier")
    session = score_breakdown.get("session_name")
    parts = []
    if tier:
        parts.append(f"Tier: <b>{tier}</b>")
    if session and session != "DEFAULT":
        parts.append(f"Phiên: <b>{session}</b>")
    if parts:
        return "\n📊 " + " | ".join(parts)
    return ""


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

    # Kế hoạch Dự Đoán Từ Xa (PREDICTIVE LIMIT SETUP)
    if signal.setup_type == "PREDICTIVE_LIMIT":
        reasons_bullet = "\n".join(f"• <i>{r}</i>" for r in signal.reasons[:3]) if signal.reasons else "• <i>Phân tích khối lệnh tổ chức & Vùng cản chưa kiểm định</i>"
        return (
            f"🔮 <b>KẾ HOẠCH DỰ ĐOÁN ĐÓN SÓNG TỪ XA ({action} LIMIT)</b>\n"
            f"🎯 <b>{action} LIMIT {sym} @ <code>{signal.entry_price:.1f}</code></b>\n"
            f"⏱ Khung: {signal.timeframe} | Mã: <code>#{signal.signal_id}</code>\n\n"
            f"📍 <b>Vùng đón Entry:</b> <code>{signal.entry_zone_low:.1f} – {signal.entry_zone_high:.1f}</code>\n"
            f"❌ <b>SL:</b> <code>{signal.stop_loss:.1f}</code> ({signal.sl_distance:.1f} giá)\n"
            f"✅ <b>TP1:</b> <code>{signal.take_profit_1:.1f}</code> ({signal.tp_distance:.1f} giá)"
            f"{tp2_line}\n"
            f"⚖️ R:R: 1:{signal.risk_reward_ratio:.1f} | Điểm Confluence: <b>{signal.score:.0f}/100</b> [<code>{_render_score_bar(signal.score)}</code>] ({signal.confidence})"
            f"{_format_breakdown_summary(signal.score_breakdown)}\n\n"
            f"💡 <b>Lý do dự đoán từ xa:</b>\n{reasons_bullet}\n\n"
            "👉 <b>Hướng dẫn cho Trader:</b>\n"
            "• Kế hoạch đón trước — Chưa vào lệnh tại giá thị trường hiện tại.\n"
            "• Trader có thể cài sẵn lệnh Limit hoặc đặt chuông cảnh báo giá.\n"
            "• Khi giá về vùng đón, Bot sẽ gửi thông báo khớp lệnh!\n"
            f"⏰ <i>{time_str} (VN) | {signal.strategy_version}</i>"
        )

    # Setup tag
    setup_tag = f"• Setup: <code>{signal.setup_type}</code>" if signal.setup_type else ""
    invalidation_line = f"\n• Hủy setup nếu: <i>{signal.invalidation}</i>" if signal.invalidation else ""

    msg = (
        f"{icon} <b>{action} {sym}: <code>{signal.entry_price:.1f}</code></b>\n"
        f"⏱ Khung: {signal.timeframe} | Mã: <code>#{signal.signal_id}</code>\n"
        f"❌ <b>SL:</b> <code>{signal.stop_loss:.1f}</code> ({signal.sl_distance:.1f} giá)\n"
        f"✅ <b>TP1:</b> <code>{signal.take_profit_1:.1f}</code> ({signal.tp_distance:.1f} giá)"
        f"{tp2_line}\n"
        f"⚖️ R:R: 1:{signal.risk_reward_ratio:.1f} | Điểm: <b>{signal.score:.0f}/100</b> [<code>{_render_score_bar(signal.score)}</code>] ({signal.confidence})"
        f"{_format_breakdown_summary(signal.score_breakdown)}\n\n"
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
        if signal.setup_type == "PREDICTIVE_LIMIT":
            return (
                f"🎯 <b>ĐÃ KHỚP KẾ HOẠCH DỰ ĐOÁN TỪ XA! {action} {sym} @ <code>{price:.1f}</code></b> [<code>#{signal.signal_id}</code>]\n"
                f"📍 Vùng đón: <code>{signal.entry_zone_low:.1f} – {signal.entry_zone_high:.1f}</code> đã được thị trường test chuẩn xác!\n"
                f"❌ SL: <code>{signal.stop_loss:.1f}</code> | ✅ TP1: <code>{signal.take_profit_1:.1f}</code>\n"
                "👉 Kế hoạch Limit đã chuyển thành Vị Thế Hoạt Động. Lãi 5 giá dời SL về BE!\n"
                f"⏰ <i>{time_str} (VN)</i>"
            )
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


def format_momentum_exhaustion_alert(
    signal: TradingSignal,
    current_price: float,
    pnl_points: float,
    exhaustion_reason: str,
) -> str:
    """
    Định dạng cảnh báo động lượng suy yếu / nến từ chối (Rejection Wick / Exhaustion) khi lệnh đang có lãi.
    Khuyến nghị chốt lời chủ động (Early Profit Take) thay vì gồng về hòa vốn.
    """
    action = signal.direction.value.upper()
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol
    time_str = _to_vn_time_str()
    pnl_pips = round(pnl_points * 10.0, 1)

    return (
        f"⚡ <b>CẢNH BÁO ĐỘNG LƯỢNG SUY YẾU (CHỐT LÃI SỚM): {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n\n"
        f"💰 <b>Lãi hiện tại:</b> <code>+{pnl_points:.2f} giá</code> (+{pnl_pips:.1f} pips) @ <code>{current_price:.2f}</code>\n"
        f"🔍 <b>Tín hiệu suy yếu:</b> {exhaustion_reason}\n\n"
        f"💡 <b>Khuyến nghị chốt lời chủ động:</b>\n"
        f"  • Chốt lời <b>50% – 70%</b> vị thế quanh <code>{current_price:.2f}</code> để bỏ túi lợi nhuận chắc chắn!\n"
        f"  • Phần còn lại giữ SL tại <code>{signal.stop_loss:.2f}</code> (Đã kéo hòa vốn) để gồng nuôi TP2 an toàn.\n"
        f"⏰ <i>{time_str} (VN) | Quản lý lợi nhuận thông minh</i>"
    )


def format_time_stagnation_alert(
    signal: TradingSignal,
    current_price: float,
    pnl_points: float,
    minutes_open: int,
) -> str:
    """
    Định dạng cảnh báo lệnh ứ đọng (Time Decay) khi lệnh ngâm lâu mà không bứt phá tới TP.
    """
    action = signal.direction.value.upper()
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol
    time_str = _to_vn_time_str()
    pnl_pips = round(pnl_points * 10.0, 1)

    return (
        f"⏳ <b>CẢNH BÁO LỆNH Ứ ĐỌNG (TIME DECAY): {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n\n"
        f"⏱ <b>Thời gian ngâm lệnh:</b> <code>{minutes_open} phút</code> (~{minutes_open // 5} cây nến M5)\n"
        f"💰 <b>Lãi hiện tại:</b> <code>+{pnl_points:.2f} giá</code> (+{pnl_pips:.1f} pips) @ <code>{current_price:.2f}</code>\n"
        f"⚠️ <b>Hiện tượng:</b> Giá dao động đi ngang trong biên độ hẹp, lực đẩy về phía TP1 (<code>{signal.take_profit_1:.2f}</code>) đã chững lại.\n\n"
        f"💡 <b>Khuyến nghị:</b> Nên chốt lãi đút túi quanh <code>{current_price:.2f}</code> hoặc kéo SL sát về <code>{signal.entry_price:.2f}</code>, tránh giữ lệnh qua phiên giao dịch tiếp theo.\n"
        f"⏰ <i>{time_str} (VN) | Kỷ luật quản lý vốn</i>"
    )


def format_trailing_stop_update(
    signal: TradingSignal,
    current_price: float,
    old_sl: float,
    new_sl: float,
    locked_points: float,
) -> str:
    """
    Định dạng thông báo tự động nâng Stop Loss theo Trailing Stop để khóa lợi nhuận.
    """
    action = signal.direction.value.upper()
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol
    time_str = _to_vn_time_str()
    locked_pips = round(locked_points * 10.0, 1)

    return (
        f"🛡️ <b>BẢO VỆ LỢI NHUẬN (TRAILING STOP): {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n\n"
        f"📈 <b>Giá thị trường:</b> <code>{current_price:.2f}</code> (Đang trong sóng sinh lời)\n"
        f"🔄 <b>Dời Stop Loss:</b> <code>{old_sl:.2f}</code> ➔ <code>{new_sl:.2f}</code>\n"
        f"🔒 <b>Khóa lợi nhuận an toàn:</b> Tối thiểu <b>+{locked_points:.2f} giá</b> (+{locked_pips:.1f} pips)\n"
        f"🎯 <b>Mục tiêu TP2 tiếp theo:</b> <code>{signal.take_profit_2:.2f}</code>\n"
        f"💡 <i>Nếu giá bất ngờ quay đầu, lệnh vẫn kết thúc với LÃI LỚN tại {new_sl:.2f}!</i>\n"
        f"⏰ <i>{time_str} (VN) | Dynamic Trailing Protection</i>"
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


def format_trade_outcome_summary(
    signal_or_data: Any,
    exit_price: float,
    pnl_points: float,
    duration_str: Optional[str] = None,
    stats: Optional[dict] = None,
) -> str:
    """
    Định dạng tin nhắn thông báo tổng hợp kết quả lệnh vừa khớp / vừa đóng.
    Báo cáo rõ ràng: LỜI hay LỖ bao nhiêu PIP, bao nhiêu giá, quy đổi USD và thống kê hiệu suất tài khoản.
    """
    if hasattr(signal_or_data, "signal_id"):
        sig_id = signal_or_data.signal_id
        direction = signal_or_data.direction.value if hasattr(signal_or_data.direction, "value") else str(signal_or_data.direction)
        symbol = signal_or_data.symbol
        entry_price = float(signal_or_data.entry_price or 0.0)
        stop_loss = float(signal_or_data.stop_loss or 0.0)
        take_profit_1 = float(signal_or_data.take_profit_1 or 0.0)
        risk_reward = float(signal_or_data.risk_reward_ratio or 0.0)
    elif isinstance(signal_or_data, dict):
        sig_id = signal_or_data.get("signal_id", "N/A")
        direction = str(signal_or_data.get("direction", "BUY"))
        symbol = signal_or_data.get("symbol", "XAUUSD")
        entry_price = float(signal_or_data.get("entry_price") or 0.0)
        stop_loss = float(signal_or_data.get("stop_loss") or 0.0)
        take_profit_1 = float(signal_or_data.get("take_profit_1") or 0.0)
        risk_reward = float(signal_or_data.get("risk_reward_ratio") or 0.0)
    else:
        sig_id = "N/A"
        direction = "BUY"
        symbol = "XAUUSD"
        entry_price = 0.0
        stop_loss = 0.0
        take_profit_1 = 0.0
        risk_reward = 0.0

    action = direction.upper()
    sym = "Gold" if "XAU" in symbol.upper() else symbol
    time_str = _to_vn_time_str()

    pnl_pips = round(pnl_points * 10.0, 1)
    abs_pts = abs(pnl_points)
    abs_pips = abs(pnl_pips)

    # Quy đổi tiền ước tính ($1/pip với 0.1 lot, $10/pip với 1.0 lot chuẩn vàng)
    usd_01lot = abs_pips * 1.0
    usd_1lot = abs_pips * 10.0

    if pnl_pips > 0:
        header = f"🎉 <b>TỔNG HỢP LỆNH VỪA KHỚP: CHỐT LÃI (+{abs_pips:.1f} PIPS)</b>"
        badge = f"🟢 <b>KẾT QUẢ: LÃI +{abs_pips:.1f} PIPS (+{abs_pts:.2f} GIÁ)</b>"
        status_note = f"✅ <b>Chốt lời thành công!</b> Tỷ lệ đạt được: <b>+{risk_reward:.1f}R</b>"
        profit_usd_str = f"+${usd_01lot:,.2f} (0.1 lot) | +${usd_1lot:,.2f} (1.0 lot)"
    elif pnl_pips < 0:
        header = f"❌ <b>TỔNG HỢP LỆNH VỪA KHỚP: CẮT LỖ (-{abs_pips:.1f} PIPS)</b>"
        badge = f"🔴 <b>KẾT QUẢ: LỖ -{abs_pips:.1f} PIPS (-{abs_pts:.2f} GIÁ)</b>"
        status_note = "🛡 <b>Dừng lỗ bảo toàn vốn!</b> Tuân thủ kỷ luật giao dịch."
        profit_usd_str = f"-${usd_01lot:,.2f} (0.1 lot) | -${usd_1lot:,.2f} (1.0 lot)"
    else:
        header = "⚖️ <b>TỔNG HỢP LỆNH VỪA KHỚP: HÒA VỐN (BREAKEVEN)</b>"
        badge = "🟡 <b>KẾT QUẢ: HÒA VỐN 0.0 PIPS (0.00 GIÁ)</b>"
        status_note = "⚖️ <b>Dời SL hòa vốn thành công</b>, bảo vệ toàn vẹn tài khoản."
        profit_usd_str = "$0.00"

    lines = [
        header,
        f"⏱ <i>{time_str} (VN)</i> | Mã lệnh: <code>#{sig_id}</code>",
        "───────────────────────────────",
        badge,
        status_note,
        "",
        f"📌 <b>Sản phẩm:</b> <code>{symbol} ({sym})</code> | Vị thế: <b>{action}</b>",
        f"🎯 <b>Điểm vào (Entry):</b> <code>{entry_price:.2f}</code>",
        f"🏁 <b>Điểm đóng (Exit):</b> <code>{exit_price:.2f}</code>",
        f"🛡 <b>Ngưỡng SL/TP:</b> SL <code>{stop_loss:.2f}</code> | TP1 <code>{take_profit_1:.2f}</code>",
        f"💵 <b>Ước tính PnL:</b> <code>{profit_usd_str}</code>",
    ]

    if duration_str:
        lines.append(f"⏳ <b>Thời gian giữ lệnh:</b> <code>{duration_str}</code>")

    if stats and stats.get("total", 0) > 0:
        tot = stats.get("total", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        wr = stats.get("win_rate", 0.0)
        pf = stats.get("profit_factor", 0.0)
        net_pips = stats.get("net_pips", 0.0)
        net_pts = stats.get("net_points", 0.0)
        sign_pips = "+" if net_pips > 0 else ""
        sign_pts = "+" if net_pts > 0 else ""

        lines.extend([
            "",
            "───────────────────────────────",
            "📊 <b>HIỆU SUẤT TỔNG HỢP TÀI KHOẢN:</b>",
            f"• Tổng lệnh đã đóng: <b>{tot} lệnh</b> ({wins} Thắng - {losses} Thua)",
            f"• Tỷ lệ thắng (Winrate): <b>{wr:.1f}%</b> | Profit Factor: <b>{pf:.2f}</b>",
            f"• Tổng Net Pips: <b>{sign_pips}{net_pips:.1f} Pips</b> ({sign_pts}{net_pts:.2f} giá)",
        ])

    lines.extend([
        "",
        "🏆 <i>VietKey Gold AI Terminal — Quản trị rủi ro định lượng</i>",
    ])

    return "\n".join(lines)


def format_scaled_exit_alert(
    signal: TradingSignal,
    current_price: float,
    tier_name: str,
    close_ratio: float,
    pnl_points: float,
    pnl_r: float,
    new_sl: Optional[float] = None,
) -> str:
    """
    Định dạng tin nhắn cảnh báo chốt lời từng phần (Tier 1: 50% / Tier 2: 30%) và bảo vệ phần còn lại.
    """
    action = signal.direction.value.upper()
    sym = "Gold" if "XAU" in signal.symbol.upper() else signal.symbol
    time_str = _to_vn_time_str()
    pnl_pips = round(pnl_points * 10.0, 1)
    close_percent = int(close_ratio * 100)

    lines = [
        f"🎯 <b>KHUYẾN NGHỊ CHỐT LỜI TỪNG PHẦN ({tier_name}): {action} {sym}</b> [<code>#{signal.signal_id}</code>]\n",
        f"📊 <b>Giá hiện tại:</b> <code>{current_price:.2f}</code> | Lợi nhuận: <b>+{pnl_points:.2f} giá</b> (+{pnl_pips:.1f} pips | <b>+{pnl_r:.1f}R</b>)",
        f"💰 <b>Hành động khuyến nghị:</b> Đóng <b>{close_percent}% khối lượng</b> để hiện thực hóa lợi nhuận!",
    ]
    if new_sl is not None:
        lines.append(f"🛡️ <b>Bảo vệ vốn:</b> Dời Stop Loss về <code>{new_sl:.2f}</code> (Khóa hòa vốn bù phí sàn).")
    lines.extend([
        f"🏃 <b>Khối lượng còn lại:</b> Tiếp tục thả trôi nuôi sóng lớn tới mục tiêu TP tiếp theo.",
        f"⏰ <i>{time_str} (VN) | VietKey Scaled Profit Engine</i>",
    ])
    return "\n".join(lines)

