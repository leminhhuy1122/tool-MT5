# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Signal Tracker & Duplicate Filter.

Quản lý vòng đời tín hiệu:
- ACTIVE: Tín hiệu vừa phát, chờ giá vào entry zone.
- ENTRY_REACHED: Giá đã chạm/vào vùng entry.
- TP_REACHED: Giá chạm mức Take Profit.
- SL_REACHED: Giá chạm mức Stop Loss.
- INVALIDATED: Tín hiệu bị hủy do vi phạm điều kiện trước khi khớp entry.
- EXPIRED: Hết thời gian hiệu lực mà chưa hoàn thành.
- UNRESOLVED: Không thể xác định kết quả rõ ràng.

Bộ lọc trùng lặp (Duplicate Protection):
- Ngăn phát tín hiệu trùng lặp trong cùng một khoảng thời gian cooldown.
- Tránh spam thông báo cho cùng một hướng trade khi setup trước chưa kết thúc.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from logger import get_logger

log = get_logger("strategy.tracker")


@dataclass
class TrackerConfig:
    """Cấu hình cho Signal Tracker."""
    cooldown_minutes: int = 60          # Thời gian tối thiểu giữa 2 tín hiệu cùng hướng
    max_active_signals: int = 3         # Tối đa số tín hiệu active đồng thời
    default_expiry_hours: int = 12      # Thời gian hết hạn mặc định (giờ)


class SignalTracker:
    """
    Theo dõi và cập nhật trạng thái các tín hiệu giao dịch.
    """

    def __init__(self, config: Optional[TrackerConfig] = None):
        self.config = config or TrackerConfig()
        self._signals: dict[str, TradingSignal] = {}

    @property
    def all_signals(self) -> list[TradingSignal]:
        """Tất cả tín hiệu đã lưu."""
        return list(self._signals.values())

    @property
    def active_signals(self) -> list[TradingSignal]:
        """Các tín hiệu đang ACTIVE hoặc ENTRY_REACHED."""
        return [s for s in self._signals.values() if s.is_active]

    def is_duplicate(
        self,
        symbol: str,
        direction: SignalDirection,
        check_time: Optional[datetime] = None,
    ) -> bool:
        """
        Kiểm tra xem có tín hiệu trùng lặp đang hoạt động hoặc trong cooldown không.

        Args:
            symbol: Mã giao dịch (e.g. XAUUSD).
            direction: BUY hoặc SELL.
            check_time: Thời điểm kiểm tra (mặc định hiện tại UTC).

        Returns:
            True nếu bị xem là trùng lặp (không nên phát thêm).
        """
        if direction == SignalDirection.WAIT:
            return False

        if check_time is None:
            check_time = datetime.now(timezone.utc)

        # 1. Kiểm tra số lượng active signals
        if len(self.active_signals) >= self.config.max_active_signals:
            log.warning(
                "Đã đạt giới hạn tối đa %d tín hiệu active.",
                self.config.max_active_signals,
            )
            return True

        cooldown = timedelta(minutes=self.config.cooldown_minutes)

        for sig in self._signals.values():
            if sig.symbol != symbol or sig.direction != direction:
                continue

            # Còn active -> coi như trùng lặp
            if sig.is_active:
                log.info(
                    "Trùng lặp: Đã có tín hiệu %s %s [%s] đang active.",
                    symbol, direction.value, sig.signal_id,
                )
                return True

            # Trong thời gian cooldown tính từ lúc tạo
            created = sig.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            if check_time - created < cooldown:
                log.info(
                    "Cooldown: Tín hiệu %s %s phát cách đây %.1f phút (< %d phút).",
                    symbol, direction.value,
                    (check_time - created).total_seconds() / 60.0,
                    self.config.cooldown_minutes,
                )
                return True

        return False

    def register_signal(self, signal: TradingSignal) -> bool:
        """
        Đăng ký một tín hiệu mới vào tracker.

        Args:
            signal: TradingSignal cần theo dõi.

        Returns:
            True nếu đăng ký thành công, False nếu trùng lặp hoặc là WAIT.
        """
        if signal.is_wait:
            return False

        if self.is_duplicate(signal.symbol, signal.direction, signal.created_at):
            return False

        if signal.expires_at is None:
            created = signal.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            signal.expires_at = created + timedelta(hours=self.config.default_expiry_hours)

        self._signals[signal.signal_id] = signal
        log.info(
            "Đã đăng ký tín hiệu [%s] %s %s | Entry: %.2f - %.2f | SL: %.2f | TP: %.2f",
            signal.signal_id, signal.direction.value, signal.symbol,
            signal.entry_zone_low, signal.entry_zone_high,
            signal.stop_loss, signal.take_profit_1,
        )
        return True

    def update_price(
        self,
        current_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        current_time: Optional[datetime] = None,
    ) -> list[TradingSignal]:
        """
        Cập nhật trạng thái các tín hiệu active dựa trên giá thị trường.

        Args:
            current_price: Giá hiện tại (close/bid/ask).
            high_price: Giá cao nhất của nến (nếu có).
            low_price: Giá thấp nhất của nến (nếu có).
            current_time: Thời điểm cập nhật (UTC).

        Returns:
            Danh sách các tín hiệu vừa có sự thay đổi trạng thái.
        """
        if high_price is None:
            high_price = current_price
        if low_price is None:
            low_price = current_price
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        changed_signals: list[TradingSignal] = []

        for sig in self.active_signals:
            prev_status = sig.status

            # Kiểm tra hết hạn (Expired)
            if sig.expires_at is not None:
                exp = sig.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if current_time >= exp:
                    sig.status = SignalStatus.EXPIRED
                    changed_signals.append(sig)
                    log.info("Tín hiệu [%s] đã HẾT HẠN (EXPIRED)", sig.signal_id)
                    continue

            # Xử lý theo từng trạng thái
            if sig.status == SignalStatus.ACTIVE:
                # Kiểm tra giá vào Entry Zone
                in_entry = (low_price <= sig.entry_zone_high and high_price >= sig.entry_zone_low)
                if in_entry:
                    sig.status = SignalStatus.ENTRY_REACHED
                    changed_signals.append(sig)
                    log.info("Tín hiệu [%s] ĐÃ KHỚP VÙNG ENTRY (%.2f - %.2f)",
                             sig.signal_id, sig.entry_zone_low, sig.entry_zone_high)
                else:
                    # Nếu giá vi phạm SL trước khi vào entry -> INVALIDATED
                    if sig.is_buy and low_price <= sig.stop_loss:
                        sig.status = SignalStatus.INVALIDATED
                        changed_signals.append(sig)
                        log.info("Tín hiệu BUY [%s] bị INVALIDATED (giá chạm SL trước khi khớp)", sig.signal_id)
                    elif sig.is_sell and high_price >= sig.stop_loss:
                        sig.status = SignalStatus.INVALIDATED
                        changed_signals.append(sig)
                        log.info("Tín hiệu SELL [%s] bị INVALIDATED (giá chạm SL trước khi khớp)", sig.signal_id)

            elif sig.status == SignalStatus.ENTRY_REACHED:
                # Kiểm tra Take Profit & Stop Loss
                if sig.is_buy:
                    if high_price >= sig.take_profit_1:
                        sig.status = SignalStatus.TP_REACHED
                        # Tự động kéo SL về hòa vốn (Breakeven) bảo vệ vốn và lợi nhuận
                        sig.stop_loss = sig.entry_price
                        changed_signals.append(sig)
                        log.info(
                            "Tín hiệu BUY [%s] ĐẠT TAKE PROFIT 1 (%.2f) -> Ăn TP thành công! Dời SL về hòa vốn (%.2f)",
                            sig.signal_id, sig.take_profit_1, sig.entry_price,
                        )
                    elif low_price <= sig.stop_loss:
                        sig.status = SignalStatus.SL_REACHED
                        changed_signals.append(sig)
                        log.info("Tín hiệu BUY [%s] CHẠM STOP LOSS (%.2f)", sig.signal_id, sig.stop_loss)

                elif sig.is_sell:
                    if low_price <= sig.take_profit_1:
                        sig.status = SignalStatus.TP_REACHED
                        # Tự động kéo SL về hòa vốn (Breakeven) bảo vệ vốn và lợi nhuận
                        sig.stop_loss = sig.entry_price
                        changed_signals.append(sig)
                        log.info(
                            "Tín hiệu SELL [%s] ĐẠT TAKE PROFIT 1 (%.2f) -> Ăn TP thành công! Dời SL về hòa vốn (%.2f)",
                            sig.signal_id, sig.take_profit_1, sig.entry_price,
                        )
                    elif high_price >= sig.stop_loss:
                        sig.status = SignalStatus.SL_REACHED
                        changed_signals.append(sig)
                        log.info("Tín hiệu SELL [%s] CHẠM STOP LOSS (%.2f)", sig.signal_id, sig.stop_loss)

        return changed_signals

    def get_signal(self, signal_id: str) -> Optional[TradingSignal]:
        """Lấy thông tin tín hiệu theo ID."""
        return self._signals.get(signal_id)

    def clear(self) -> None:
        """Xóa toàn bộ tín hiệu trong bộ nhớ."""
        self._signals.clear()
