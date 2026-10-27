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

from app.market.market_structure import MarketStructureResult, TrendDirection
from app.strategy.conflict_resolver import ConflictConfig, ConflictDecision, ConflictResolver
from app.strategy.setup_detector import SetupCandidate
from app.strategy.signal_models import SetupLifecycleStatus, SignalDirection, SignalStatus, TradingSignal
from logger import get_logger

log = get_logger("strategy.tracker")


@dataclass
class TrackerConfig:
    """Cấu hình cho Signal Tracker & Lifecycle Controller."""
    cooldown_minutes: int = 60             # Thời gian tối thiểu giữa 2 tín hiệu (phút)
    max_active_signals: int = 1            # Tối đa số tín hiệu active đồng thời trên 1 symbol
    default_expiry_hours: int = 4          # Thời gian hết hạn mặc định (giờ)
    approaching_distance_pts: float = 1.5  # Khoảng cách (giá) để chuyển sang trạng thái APPROACHING
    max_unfilled_distance_pts: float = 8.0 # Hủy lệnh chờ nếu giá chạy xa >= 8 giá theo hướng TP mà không khớp
    unfilled_expiry_minutes: int = 45      # Hủy lệnh chờ nếu sau 45 phút chưa khớp entry


class SignalTracker:
    """
    Theo dõi và cập nhật trạng thái chu kỳ sống (Lifecycle) của các tín hiệu giao dịch.
    """

    def __init__(self, config: Optional[TrackerConfig] = None):
        self.config = config or TrackerConfig()
        self._signals: dict[str, TradingSignal] = {}
        self.conflict_resolver = ConflictResolver(
            ConflictConfig(
                cooldown_minutes=self.config.cooldown_minutes,
                max_active_per_symbol=self.config.max_active_signals,
            )
        )

    @property
    def all_signals(self) -> list[TradingSignal]:
        """Tất cả tín hiệu đã lưu."""
        return list(self._signals.values())

    @property
    def active_signals(self) -> list[TradingSignal]:
        """Các tín hiệu đang ACTIVE, APPROACHING hoặc ENTRY_REACHED."""
        return [s for s in self._signals.values() if s.is_active]

    def load_active_signals(self, signals: list[TradingSignal]) -> None:
        """Nạp các tín hiệu active từ cơ sở dữ liệu để tiếp tục quản lý và chống trùng lặp qua các lần khởi động lại."""
        count = 0
        for sig in signals:
            if sig.is_active:
                self._signals[sig.signal_id] = sig
                count += 1
        log.info("SignalTracker đã khôi phục %d tín hiệu active từ bộ nhớ lưu trữ.", count)

    def is_duplicate(
        self,
        symbol: str,
        direction: SignalDirection,
        check_time: Optional[datetime] = None,
    ) -> bool:
        """
        Kiểm tra xem có tín hiệu trùng lặp đang hoạt động hoặc trong cooldown không.
        """
        if direction == SignalDirection.WAIT:
            return False

        if check_time is None:
            check_time = datetime.now(timezone.utc)
        elif check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=timezone.utc)

        # 1. Kiểm tra số lượng active signals
        if len(self.active_signals) >= self.config.max_active_signals:
            log.warning(
                "Đã đạt giới hạn tối đa %d tín hiệu active trên %s.",
                self.config.max_active_signals, symbol,
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

    def check_conflict(
        self,
        candidate: SetupCandidate,
        h4_trend: TrendDirection = TrendDirection.NEUTRAL,
        structure: Optional[MarketStructureResult] = None,
        current_price: float = 0.0,
        current_time: Optional[datetime] = None,
    ) -> ConflictDecision:
        """
        Phân xử xung đột toàn diện (trùng lặp, cooldown, lệnh ngược chiều BUY vs SELL).
        """
        return self.conflict_resolver.resolve_active_conflict(
            new_candidate=candidate,
            active_signals=self.active_signals,
            h4_trend=h4_trend,
            structure=structure,
            current_price=current_price,
            current_time=current_time,
        )

    def register_signal(self, signal: TradingSignal) -> bool:
        """
        Đăng ký một tín hiệu mới vào tracker với đầy đủ lifecycle metadata.
        """
        if signal.is_wait:
            return False

        if signal.signal_id in self._signals:
            # Đã đăng ký rồi (idempotent), không từ chối nhưng cũng không duplicate
            return True

        if not getattr(signal, "is_dca", False) and self.is_duplicate(signal.symbol, signal.direction, signal.created_at):
            return False

        # Anti-Hedging Guard: Không cho phép đăng ký lệnh ngược chiều khi đang có lệnh active trên cùng symbol
        for sig in self._signals.values():
            if sig.symbol == signal.symbol and sig.is_active and sig.direction != signal.direction:
                log.warning(
                    "⛔ Anti-Hedging Tracker: Đã có tín hiệu %s %s [%s] đang active. Chặn tín hiệu ngược chiều %s [%s].",
                    sig.symbol, sig.direction.value, sig.signal_id, signal.direction.value, signal.signal_id,
                )
                return False

        if signal.expires_at is None:
            created = signal.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            signal.expires_at = created + timedelta(hours=self.config.default_expiry_hours)

        if not signal.setup_id:
            signal.setup_id = f"setup_{signal.signal_id}"

        # Đảm bảo trạng thái ban đầu là ACTIVE
        signal.status = SignalStatus.ACTIVE
        signal.lifecycle_status = SetupLifecycleStatus.ACTIVE

        self._signals[signal.signal_id] = signal
        log.info(
            "Đã đăng ký tín hiệu [%s] (Setup: %s) %s %s | Entry: %.2f - %.2f | SL: %.2f | TP: %.2f",
            signal.signal_id, signal.setup_id, signal.direction.value, signal.symbol,
            signal.entry_zone_low, signal.entry_zone_high,
            signal.stop_loss, signal.take_profit_1,
        )
        return True

    def revalidate_active_signals(
        self,
        structure: Optional[MarketStructureResult] = None,
        current_price: float = 0.0,
        current_time: Optional[datetime] = None,
    ) -> list[TradingSignal]:
        """
        Tái kiểm tra (Revalidation) cấu trúc của các tín hiệu đang ACTIVE/APPROACHING chưa khớp lệnh:
        - Nếu mức cản bảo vệ invalidation_level bị phá vỡ -> chuyển sang INVALIDATED.
        - Nếu còn hợp lệ -> đánh dấu revalidated_at.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        invalidated_signals: list[TradingSignal] = []

        for sig in self.active_signals:
            if sig.status == SignalStatus.ENTRY_REACHED:
                # Lệnh đã khớp thì để update_price và Trailing Stop quản lý
                continue

            inval_p = sig.invalidation_level or sig.stop_loss
            is_breached = False

            if current_price > 0:
                if sig.is_buy and current_price <= inval_p:
                    is_breached = True
                elif sig.is_sell and current_price >= inval_p:
                    is_breached = True

            if is_breached:
                sig.status = SignalStatus.INVALIDATED
                sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                invalidated_signals.append(sig)
                log.info(
                    "Revalidation thất bại: Tín hiệu %s [%s] bị vi phạm cấu trúc cản @ %.2f -> INVALIDATED",
                    sig.direction.value, sig.signal_id, current_price,
                )
            else:
                sig.revalidated_at = current_time

        return invalidated_signals

    def update_price(
        self,
        current_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        current_time: Optional[datetime] = None,
    ) -> list[TradingSignal]:
        """
        Cập nhật trạng thái các tín hiệu active dựa trên giá thị trường và chu kỳ sống SetupLifecycleStatus.
        """
        if high_price is None:
            high_price = current_price
        if low_price is None:
            low_price = current_price
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        changed_signals: list[TradingSignal] = []

        for sig in self.active_signals:
            # 1. Kiểm tra hết hạn (EXPIRED)
            if sig.expires_at is not None:
                exp = sig.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if current_time >= exp:
                    sig.status = SignalStatus.EXPIRED
                    sig.lifecycle_status = SetupLifecycleStatus.EXPIRED
                    changed_signals.append(sig)
                    log.info("Tín hiệu [%s] đã HẾT HẠN (EXPIRED)", sig.signal_id)
                    continue

            # 2. Xử lý các tín hiệu chưa khớp (ACTIVE hoặc APPROACHING)
            if sig.status == SignalStatus.ACTIVE:
                # 2a. Kiểm tra khớp Entry Zone
                in_entry = (low_price <= sig.entry_zone_high and high_price >= sig.entry_zone_low)
                if in_entry:
                    sig.status = SignalStatus.ENTRY_REACHED
                    sig.lifecycle_status = SetupLifecycleStatus.ENTRY_REACHED
                    changed_signals.append(sig)
                    log.info("Tín hiệu [%s] ĐÃ KHỚP VÙNG ENTRY (%.2f - %.2f)",
                             sig.signal_id, sig.entry_zone_low, sig.entry_zone_high)
                    continue

                # 2b. Kiểm tra vi phạm Invalidation Level / Stop Loss trước khi vào entry -> INVALIDATED
                inval_level = sig.invalidation_level or sig.stop_loss
                if sig.is_buy and low_price <= inval_level:
                    sig.status = SignalStatus.INVALIDATED
                    sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                    sig.invalidation = f"Giá chạm mức cản SL @ {low_price:.2f} trước khi khớp Entry"
                    changed_signals.append(sig)
                    log.info("Tín hiệu BUY [%s] bị INVALIDATED (giá %.2f chạm mức cản %.2f)",
                             sig.signal_id, low_price, inval_level)
                    continue
                elif sig.is_sell and high_price >= inval_level:
                    sig.status = SignalStatus.INVALIDATED
                    sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                    sig.invalidation = f"Giá chạm mức cản SL @ {high_price:.2f} trước khi khớp Entry"
                    changed_signals.append(sig)
                    log.info("Tín hiệu SELL [%s] bị INVALIDATED (giá %.2f chạm mức cản %.2f)",
                             sig.signal_id, high_price, inval_level)
                    continue

                # 2c. Kiểm tra Missed Move: Giá đã chạm/vượt Take Profit 1 trước khi khớp Entry -> INVALIDATED
                if sig.is_buy and sig.take_profit_1 > 0 and high_price >= sig.take_profit_1:
                    sig.status = SignalStatus.INVALIDATED
                    sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                    sig.invalidation = f"Giá đã đạt mục tiêu TP1 @ {high_price:.2f} mà không hồi về Entry (Kèo đã chạy xong)"
                    changed_signals.append(sig)
                    log.info("Tín hiệu BUY [%s] bị INVALIDATED (Giá %.2f đã đạt TP1 %.2f trước khi khớp Entry - Kèo đã chạy mất)",
                             sig.signal_id, high_price, sig.take_profit_1)
                    continue
                elif sig.is_sell and sig.take_profit_1 > 0 and low_price <= sig.take_profit_1:
                    sig.status = SignalStatus.INVALIDATED
                    sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                    sig.invalidation = f"Giá đã đạt mục tiêu TP1 @ {low_price:.2f} mà không hồi về Entry (Kèo đã chạy xong)"
                    changed_signals.append(sig)
                    log.info("Tín hiệu SELL [%s] bị INVALIDATED (Giá %.2f đã đạt TP1 %.2f trước khi khớp Entry - Kèo đã chạy mất)",
                             sig.signal_id, low_price, sig.take_profit_1)
                    continue

                # 2d. Kiểm tra Out-of-Reach: Giá đi quá xa vùng Entry theo hướng kỳ vọng mà không khớp
                max_unfilled_dist = getattr(self.config, "max_unfilled_distance_pts", 8.0)
                if sig.is_buy:
                    dist_away = current_price - sig.entry_zone_high
                    if dist_away >= max_unfilled_dist:
                        sig.status = SignalStatus.INVALIDATED
                        sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                        sig.invalidation = f"Giá đi quá xa vùng Entry (+{dist_away:.1f} giá), hủy lệnh chờ để quét setup mới"
                        changed_signals.append(sig)
                        log.info("Tín hiệu BUY [%s] bị INVALIDATED do đi quá xa vùng Entry (+%.2f giá >= %.1f giá)",
                                 sig.signal_id, dist_away, max_unfilled_dist)
                        continue
                elif sig.is_sell:
                    dist_away = sig.entry_zone_low - current_price
                    if dist_away >= max_unfilled_dist:
                        sig.status = SignalStatus.INVALIDATED
                        sig.lifecycle_status = SetupLifecycleStatus.INVALIDATED
                        sig.invalidation = f"Giá đi quá xa vùng Entry (-{dist_away:.1f} giá), hủy lệnh chờ để quét setup mới"
                        changed_signals.append(sig)
                        log.info("Tín hiệu SELL [%s] bị INVALIDATED do đi quá xa vùng Entry (-%.2f giá >= %.1f giá)",
                                 sig.signal_id, dist_away, max_unfilled_dist)
                        continue

                # 2e. Kiểm tra Timeout cho lệnh chưa khớp Entry (Mặc định sau 45 phút chưa khớp -> EXPIRED)
                unfilled_exp_min = getattr(self.config, "unfilled_expiry_minutes", 45)
                if sig.created_at:
                    sig_time = sig.created_at if sig.created_at.tzinfo else sig.created_at.replace(tzinfo=timezone.utc)
                    age_minutes = (current_time - sig_time).total_seconds() / 60.0
                    if age_minutes >= unfilled_exp_min:
                        sig.status = SignalStatus.EXPIRED
                        sig.lifecycle_status = SetupLifecycleStatus.EXPIRED
                        sig.invalidation = f"Quá thời gian chờ {unfilled_exp_min} phút mà chưa khớp Entry, hủy để đón nhịp mới"
                        changed_signals.append(sig)
                        log.info("Tín hiệu [%s] đã HẾT HẠN (Chờ %.1f phút >= %d phút chưa khớp Entry)",
                                 sig.signal_id, age_minutes, unfilled_exp_min)
                        continue

                # 2c. Kiểm tra trạng thái đang tiến sát vùng entry (APPROACHING)
                if sig.is_buy:
                    dist_to_entry = current_price - sig.entry_zone_high
                    if 0 < dist_to_entry <= self.config.approaching_distance_pts:
                        if sig.lifecycle_status != SetupLifecycleStatus.APPROACHING:
                            sig.lifecycle_status = SetupLifecycleStatus.APPROACHING
                            changed_signals.append(sig)
                            log.info("Tín hiệu BUY [%s] chuyển sang APPROACHING (Cách %.2f giá)",
                                     sig.signal_id, dist_to_entry)
                elif sig.is_sell:
                    dist_to_entry = sig.entry_zone_low - current_price
                    if 0 < dist_to_entry <= self.config.approaching_distance_pts:
                        if sig.lifecycle_status != SetupLifecycleStatus.APPROACHING:
                            sig.lifecycle_status = SetupLifecycleStatus.APPROACHING
                            changed_signals.append(sig)
                            log.info("Tín hiệu SELL [%s] chuyển sang APPROACHING (Cách %.2f giá)",
                                     sig.signal_id, dist_to_entry)

            # 3. Xử lý các tín hiệu ĐÃ KHỚP (ENTRY_REACHED / IN-TRADE)
            elif sig.status == SignalStatus.ENTRY_REACHED:
                if sig.is_buy:
                    if high_price >= sig.take_profit_1:
                        sig.status = SignalStatus.TP_REACHED
                        sig.lifecycle_status = SetupLifecycleStatus.COMPLETED
                        sig.stop_loss = sig.entry_price  # Kéo BE
                        changed_signals.append(sig)
                        log.info("Tín hiệu BUY [%s] ĐẠT TP1 (%.2f) -> COMPLETED!", sig.signal_id, sig.take_profit_1)
                    elif low_price <= sig.stop_loss:
                        sig.status = SignalStatus.SL_REACHED
                        sig.lifecycle_status = SetupLifecycleStatus.COMPLETED
                        changed_signals.append(sig)
                        log.info("Tín hiệu BUY [%s] CHẠM SL (%.2f) -> COMPLETED!", sig.signal_id, sig.stop_loss)

                elif sig.is_sell:
                    if low_price <= sig.take_profit_1:
                        sig.status = SignalStatus.TP_REACHED
                        sig.lifecycle_status = SetupLifecycleStatus.COMPLETED
                        sig.stop_loss = sig.entry_price  # Kéo BE
                        changed_signals.append(sig)
                        log.info("Tín hiệu SELL [%s] ĐẠT TP1 (%.2f) -> COMPLETED!", sig.signal_id, sig.take_profit_1)
                    elif high_price >= sig.stop_loss:
                        sig.status = SignalStatus.SL_REACHED
                        sig.lifecycle_status = SetupLifecycleStatus.COMPLETED
                        changed_signals.append(sig)
                        log.info("Tín hiệu SELL [%s] CHẠM SL (%.2f) -> COMPLETED!", sig.signal_id, sig.stop_loss)

        return changed_signals

    def get_signal(self, signal_id: str) -> Optional[TradingSignal]:
        """Lấy thông tin tín hiệu theo ID."""
        return self._signals.get(signal_id)

    def cancel_signal(self, signal_id: str, reason: str = "") -> Optional[TradingSignal]:
        """
        Hủy tín hiệu thủ công hoặc do xung đột đảo chiều (chuyển sang CANCELLED).
        """
        sig = self._signals.get(signal_id)
        if sig and sig.is_active:
            sig.status = SignalStatus.CANCELLED
            sig.lifecycle_status = SetupLifecycleStatus.CANCELLED
            if reason:
                sig.reasons.append(f"Hủy do: {reason}")
            log.info("Tín hiệu [%s] đã bị HỦY (CANCELLED): %s", signal_id, reason)
            return sig
        return None

    def cleanup_old_signals(self, max_age_hours: int = 48) -> int:
        """
        Dọn dẹp các tín hiệu đã hoàn tất (TP, SL, EXPIRED, CANCELLED) cũ hơn max_age_hours
        để giải phóng RAM và giữ tốc độ xử lý is_duplicate() luôn nhanh nhất.
        """
        now = datetime.now(timezone.utc)
        to_delete: list[str] = []

        for sig_id, sig in list(self._signals.items()):
            if sig.is_active:
                continue

            created = sig.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            age_hours = (now - created).total_seconds() / 3600.0
            if age_hours > max_age_hours:
                to_delete.append(sig_id)

        for sig_id in to_delete:
            self._signals.pop(sig_id, None)

        if to_delete:
            log.info(
                "SignalTracker đã dọn dẹp %d tín hiệu cũ (>%d giờ) khỏi RAM.",
                len(to_delete),
                max_age_hours,
            )
        return len(to_delete)

    def clear(self) -> None:
        """Xóa toàn bộ tín hiệu trong bộ nhớ."""
        self._signals.clear()
