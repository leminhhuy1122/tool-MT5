# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Realtime AI Trading Copilot Companion.

Đóng vai trò người bạn đồng hành AI trò chuyện tự nhiên, gần gũi với anh em trader:
1. Lệnh bắt đầu xanh (+3 đến +5 giá): Dặn dò ae chuẩn bị canh dời SL về hòa vốn (BE) hoặc tỉa bớt lời.
2. Lệnh đang âm nhẹ (-1 đến -4 giá) nhưng cản vẫn giữ: Động viên ae kiên nhẫn gồng qua cơn sóng rung lắc, xíu nữa sẽ quay lại xanh.
3. Lệnh bị lệch xu thế / phá cản bảo vệ: Khuyên ae dứt khoát chủ động cắt lệnh sớm để bảo toàn vốn, không cố chấp gồng lỗ.

Có cơ chế chống spam nghiêm ngặt: Mỗi trạng thái chỉ gửi 1 lần duy nhất cho mỗi mã lệnh,
khoảng cách giữa các tin nhắn tối thiểu 15 phút.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.telegram.formatter import _to_vn_time_str
from logger import get_logger

log = get_logger("strategy.ai_companion")


class AITradingCopilot:
    """Động cơ Copilot AI trò chuyện và đồng hành theo dõi lệnh thời gian thực."""

    def __init__(self, min_message_interval_minutes: float = 15.0):
        self.min_interval = timedelta(minutes=min_message_interval_minutes)
        self.last_sent_time: Optional[datetime] = None

        # Trạng thái gửi tin cho từng signal: signal_id -> dict
        self._sent_state: Dict[str, Dict[str, bool]] = {}

    def _get_signal_state(self, signal_id: str) -> Dict[str, bool]:
        if signal_id not in self._sent_state:
            self._sent_state[signal_id] = {
                "green_sent": False,
                "reassurance_sent": False,
                "cut_warning_sent": False,
            }
        return self._sent_state[signal_id]

    def clear_signal(self, signal_id: str) -> None:
        """Xóa trạng thái khi lệnh kết thúc."""
        self._sent_state.pop(signal_id, None)

    def evaluate(
        self,
        signal: TradingSignal,
        current_price: float,
        now_utc: Optional[datetime] = None,
        invalidation_level: Optional[float] = None,
    ) -> Optional[str]:
        """
        Đánh giá trạng thái lệnh đang chạy và sinh tin nhắn đàm đạo tự nhiên nếu đúng thời điểm.
        
        Returns:
            Nội dung tin nhắn HTML gửi Telegram (hoặc None nếu chưa đến lúc gửi).
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        elif now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # Chỉ áp dụng cho lệnh đã khớp và đang chạy (ENTRY_REACHED)
        if signal.status != SignalStatus.ENTRY_REACHED or signal.entry_price <= 0:
            return None

        # Kiểm tra khoảng cách giãn cách thời gian giữa các tin nhắn AI Copilot (Chống spam)
        if self.last_sent_time is not None and (now_utc - self.last_sent_time) < self.min_interval:
            return None

        state = self._get_signal_state(signal.signal_id)
        is_buy = (signal.direction == SignalDirection.BUY)
        direction_str = "BUY" if is_buy else "SELL"
        symbol = signal.symbol

        # Tính lợi nhuận thả nổi theo giá (gain > 0 là xanh, gain < 0 là âm)
        gain = (current_price - signal.entry_price) if is_buy else (signal.entry_price - current_price)
        pips = gain * 10.0
        time_str = _to_vn_time_str(now_utc)
        inval_price = invalidation_level or signal.invalidation_level or (
            signal.stop_loss + 2.0 if is_buy else signal.stop_loss - 2.0
        )

        # ---------------------------------------------------------------------
        # TÌNH HUỐNG 3: LỆNH BỊ LỆCH XU THẾ / PHÁ CẢN BẢO VỆ -> KHUYÊN CẮT SỚM
        # ---------------------------------------------------------------------
        is_trend_broken = False
        if is_buy and current_price < inval_price:
            is_trend_broken = True
        elif not is_buy and current_price > inval_price:
            is_trend_broken = True
        elif gain <= -5.0:  # Âm sâu hơn 5 giá và chưa có dấu hiệu rút râu
            is_trend_broken = True

        if is_trend_broken and not state["cut_warning_sent"]:
            state["cut_warning_sent"] = True
            self.last_sent_time = now_utc
            msg = (
                f"💬 <b>AI COPILOT: CẢNH BÁO LỆCH XU HƯỚNG THỊ TRƯỜNG</b> ⚠️\n"
                f"⏱ <i>{time_str} (VN)</i> | Mã: <code>#{signal.signal_id}</code>\n"
                f"───────────────────────────────\n"
                f"Lệnh <b>{direction_str} {symbol}</b> đang có dấu hiệu lệch pha xu thế rõ rệt!\n"
                f"• Giá vào: <code>{signal.entry_price:.2f}</code> | Giá hiện tại: <code>{current_price:.2f}</code> (<b>-{abs(gain):.1f} giá</b>)\n"
                f"• Mức cản bảo vệ: <code>{inval_price:.2f}</code> đang bị đe dọa/phá vỡ.\n\n"
                f"💡 <b>Lời khuyên chân thành từ Bot AI:</b>\n"
                f"Thị trường xuất hiện áp lực đảo chiều mạnh ngược xu thế rồi ae ơi. Bot khuyên ae nên <b>chủ động cắt lệnh sớm quanh mốc này</b> (hoặc hạ 80% volume) để bảo toàn vốn, tuyệt đối đừng cố chấp gồng lỗ nha!\n"
                f"Bảo toàn tài khoản là trên hết, giữ tiền để canh kèo mới đẹp hơn vào lại ae nhé! 🚨\n"
                f"───────────────────────────────\n"
                f"🏆 <i>VietKey AI Trading Copilot — Kỷ luật là sức mạnh</i>"
            )
            log.info("🤖 AI Copilot phát cảnh báo lệch xu hướng cho lệnh %s", signal.signal_id)
            return msg

        # ---------------------------------------------------------------------
        # TÌNH HUỐNG 1: LỆNH BẮT ĐẦU XANH MƯỚT (+3 đến +5 giá trở lên)
        # ---------------------------------------------------------------------
        if gain >= 3.0 and not state["green_sent"]:
            state["green_sent"] = True
            self.last_sent_time = now_utc
            msg = (
                f"💬 <b>AI COPILOT: LỆNH BẮT ĐẦU XANH MƯỚT (+{gain:.1f} GIÁ)</b> 🟢\n"
                f"⏱ <i>{time_str} (VN)</i> | Mã: <code>#{signal.signal_id}</code>\n"
                f"───────────────────────────────\n"
                f"Lệnh <b>{direction_str} {symbol}</b> bắt đầu chạy mượt đúng bài rồi ae ơi!\n"
                f"• Giá vào (Entry): <code>{signal.entry_price:.2f}</code>\n"
                f"• Giá hiện tại: <code>{current_price:.2f}</code> (<b>+{gain:.1f} giá / +{pips:.1f} pips</b>)\n\n"
                f"💡 <b>Lời dặn dò từ Bot AI:</b>\n"
                f"Lệnh bắt đầu xanh rồi ae canh chuẩn bị dời <b>Stop Loss về Hòa Vốn (BE)</b> để khóa rủi ro bảo toàn túi tiền nha!\n"
                f"Ai muốn chắc cú bỏ túi có thể tỉa bớt 1 phần lợi nhuận, phần còn lại cứ tự tin gồng thẳng về TP1 nhé! 🚀\n"
                f"───────────────────────────────\n"
                f"🏆 <i>VietKey AI Trading Copilot — Đồng hành cùng anh em</i>"
            )
            log.info("🤖 AI Copilot phát lời dặn lệnh xanh mướt cho lệnh %s (+%.1f giá)", signal.signal_id, gain)
            return msg

        # ---------------------------------------------------------------------
        # TÌNH HUỐNG 2: LỆNH ĐANG ÂM NHẸ (-1 đến -4 giá) NHƯNG CẤU TRÚC VẪN VỮNG
        # ---------------------------------------------------------------------
        if -4.5 <= gain <= -1.2 and not state["reassurance_sent"] and not is_trend_broken:
            state["reassurance_sent"] = True
            self.last_sent_time = now_utc
            msg = (
                f"💬 <b>AI COPILOT: NHỊP RUNG LẮC QUÉT THANH KHOẢN</b> 🌊\n"
                f"⏱ <i>{time_str} (VN)</i> | Mã: <code>#{signal.signal_id}</code>\n"
                f"───────────────────────────────\n"
                f"Lệnh <b>{direction_str} {symbol}</b> đang chịu nhịp giật quét nhẹ ngược chiều (đang âm <b>-{abs(gain):.1f} giá</b>).\n"
                f"• Điểm vào: <code>{signal.entry_price:.2f}</code> | Giá hiện tại: <code>{current_price:.2f}</code>\n"
                f"• Mức cản bảo vệ: <code>{inval_price:.2f}</code> (Vẫn đang giữ vững rất đẹp)\n\n"
                f"💡 <b>Lời nhắn nhủ từ Bot AI:</b>\n"
                f"Cấu trúc khung lớn vẫn đang ủng hộ, đây chỉ là pha rung lắc rũ hàng của Market trước khi vào đà thôi.\n"
                f"Ae vững tâm gồng qua cơn sóng này xíu nữa nó sẽ quay lại xanh thôi nha! Kỷ luật tuân thủ mốc SL đã cài, không việc gì phải hoảng loạn out non ae nhé! 🛡️\n"
                f"───────────────────────────────\n"
                f"🏆 <i>VietKey AI Trading Copilot — Đồng hành cùng anh em</i>"
            )
            log.info("🤖 AI Copilot phát lời trấn an rung lắc cho lệnh %s (-%.1f giá)", signal.signal_id, abs(gain))
            return msg

        return None
