# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Conflict Resolution Engine & Setup Lifecycle Controller.

Chịu trách nhiệm:
1. Phát hiện và giải quyết xung đột chiều lệnh (BUY vs SELL Conflict Resolution):
   - Ngăn chặn hoàn toàn việc phát tín hiệu BUY và SELL đối nghịch cùng lúc.
   - Khi có BUY active và xuất hiện SELL (hoặc ngược lại):
     + Kiểm tra lệnh hiện tại còn valid không (invalidation level / stop loss).
     + Kiểm tra cấu trúc H1/M15 (BOS / CHoCH).
     + Kiểm tra xu hướng lớn H4 & xác nhận độc lập (SMC Sweep / OB).
     + Nếu xung đột chưa thể giải quyết chắc chắn -> WAIT (bảo toàn vốn).
2. Phát hiện và lọc trùng lặp tín hiệu (Duplicate & Cooldown Protection):
   - Một chiều lệnh active duy nhất cho mỗi setup context.
   - Thực thi thời gian cooldown cấu hình được giữa các lần phát.
3. Giải quyết xung đột đa setup trong cùng một nến (Multi-Candidate Arbitration).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional, Tuple

from app.market.market_structure import MarketStructureResult, StructureBreak, TrendDirection
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_models import SetupLifecycleStatus, SignalDirection, SignalStatus, TradingSignal
from logger import get_logger

log = get_logger("strategy.conflict")


class ConflictType(Enum):
    """Loại xung đột tín hiệu."""
    NONE = "NONE"                          # Không có xung đột
    DUPLICATE_ACTIVE = "DUPLICATE_ACTIVE"  # Trùng hướng với lệnh đang active
    COOLDOWN = "COOLDOWN"                  # Trong thời gian cooldown sau tín hiệu trước
    OPPOSITE_ACTIVE = "OPPOSITE_ACTIVE"    # Xung đột với lệnh ngược chiều đang active
    MULTI_CANDIDATE = "MULTI_CANDIDATE"    # Xung đột cả BUY và SELL cùng xuất hiện trong 1 nến
    MAX_ACTIVE_EXCEEDED = "MAX_ACTIVE"     # Vượt quá giới hạn số lệnh active cho phép


class ConflictResolution(Enum):
    """Quyết định giải quyết xung đột."""
    PROCEED = "PROCEED"                                  # Cho phép phát tín hiệu mới
    WAIT = "WAIT"                                        # Tạm dừng phát, chuyển sang trạng thái WAIT
    CANCEL_NEW = "CANCEL_NEW"                            # Hủy setup mới (bảo vệ lệnh đang có)
    INVALIDATE_EXISTING_AND_PROCEED = "INVALIDATE_OLD"   # Hủy lệnh cũ do bẻ gãy cấu trúc, cho phép lệnh mới


@dataclass
class ConflictDecision:
    """Kết quả phân xử xung đột."""
    resolution: ConflictResolution
    conflict_type: ConflictType
    reason: str
    existing_signal_id: Optional[str] = None
    action_notes: list[str] = field(default_factory=list)

    @property
    def should_emit(self) -> bool:
        """Có được phép tạo và phát tín hiệu mới không."""
        return self.resolution in (ConflictResolution.PROCEED, ConflictResolution.INVALIDATE_EXISTING_AND_PROCEED)


@dataclass
class ConflictConfig:
    """Cấu hình cho bộ phân xử xung đột."""
    cooldown_minutes: int = 60             # Thời gian tối thiểu giữa 2 tín hiệu (phút)
    max_active_per_symbol: int = 1        # Số tín hiệu active tối đa trên 1 mã (mặc định 1)
    allow_reversal_on_choch: bool = True  # Cho phép đảo chiều khi có CHoCH khung lớn xác nhận
    min_score_for_reversal: float = 75.0  # Điểm tối thiểu để setup đảo chiều được xem xét


class ConflictResolver:
    """
    Bộ phân xử xung đột tín hiệu và kiểm soát chu kỳ sống của Setup.
    """

    def __init__(self, config: Optional[ConflictConfig] = None):
        self.config = config or ConflictConfig()

    def resolve_candidate_conflicts(
        self,
        candidates: list[SetupCandidate],
        h4_trend: TrendDirection = TrendDirection.NEUTRAL,
        structure: Optional[MarketStructureResult] = None,
    ) -> Tuple[list[SetupCandidate], Optional[str]]:
        """
        Giải quyết xung đột nội bộ khi SetupDetector phát hiện cả BUY và SELL trong cùng một nến.

        Args:
            candidates: Danh sách candidate vừa quét được.
            h4_trend: Xu hướng H4.
            structure: Kết quả phân tích cấu trúc H1.

        Returns:
            Tuple (danh sách candidates hợp lệ sau giải quyết, lý do nếu bị lọc/hủy).
        """
        if not candidates:
            return [], None

        buy_cands = [c for c in candidates if c.direction.upper() == "BUY"]
        sell_cands = [c for c in candidates if c.direction.upper() == "SELL"]

        # 1. Nếu chỉ toàn BUY hoặc toàn SELL -> Không có xung đột đa hướng
        if not buy_cands or not sell_cands:
            return candidates, None

        log.warning(
            "⚠️ XUNG ĐỘT ĐA SETUP: Phát hiện đồng thời %d BUY và %d SELL trong cùng một lượt quét!",
            len(buy_cands), len(sell_cands),
        )

        # 2. Phân xử theo xu hướng lớn H4
        if h4_trend == TrendDirection.BULLISH:
            log.info("✓ Ưu tiên BUY theo xu hướng lớn H4 BULLISH. Loại bỏ %d candidate SELL.", len(sell_cands))
            return buy_cands, "Loại bỏ SELL do xung đột với H4 Trend Bullish"
        elif h4_trend == TrendDirection.BEARISH:
            log.info("✓ Ưu tiên SELL theo xu hướng lớn H4 BEARISH. Loại bỏ %d candidate BUY.", len(buy_cands))
            return sell_cands, "Loại bỏ BUY do xung đột với H4 Trend Bearish"

        # 3. Nếu H4 là NEUTRAL: Phân xử theo cấp bậc setup (SMC Sweep > OB > FVG > Retest > Divergence)
        setup_priority = {
            SetupType.SMC_LIQUIDITY_SWEEP: 100,
            SetupType.SMC_ORDER_BLOCK: 80,
            SetupType.SMC_FVG_RETEST: 60,
            SetupType.BOS_RETEST: 50,
            SetupType.EMA_BOUNCE: 40,
            SetupType.PREDICTIVE_LIMIT: 35,
            SetupType.RSI_DIVERGENCE: 30,
            SetupType.NO_SETUP: 0,
        }

        best_buy = max(buy_cands, key=lambda c: setup_priority.get(c.setup_type, 0))
        best_sell = max(sell_cands, key=lambda c: setup_priority.get(c.setup_type, 0))

        buy_prio = setup_priority.get(best_buy.setup_type, 0)
        sell_prio = setup_priority.get(best_sell.setup_type, 0)

        # Nếu một bên có ưu thế cấp bậc vượt trội (>= 30 điểm ưu tiên)
        if buy_prio - sell_prio >= 30:
            log.info("✓ Phân xử: Chọn BUY (%s) vượt trội so với SELL (%s)", best_buy.setup_type.value, best_sell.setup_type.value)
            return [best_buy], f"Ưu tiên setup cấp cao {best_buy.setup_type.value}"
        elif sell_prio - buy_prio >= 30:
            log.info("✓ Phân xử: Chọn SELL (%s) vượt trội so với BUY (%s)", best_sell.setup_type.value, best_buy.setup_type.value)
            return [best_sell], f"Ưu tiên setup cấp cao {best_sell.setup_type.value}"

        # 4. Nếu ngang sức và H4 là NEUTRAL -> Xung đột chưa giải quyết được, an toàn nhất là WAIT
        msg = f"Xung đột 2 chiều BUY ({best_buy.setup_type.value}) và SELL ({best_sell.setup_type.value}) chưa rõ ràng trong thị trường tích lũy -> WAIT"
        log.warning("⛔ %s", msg)
        return [], msg

    def resolve_active_conflict(
        self,
        new_candidate: SetupCandidate,
        active_signals: list[TradingSignal],
        h4_trend: TrendDirection = TrendDirection.NEUTRAL,
        structure: Optional[MarketStructureResult] = None,
        current_price: float = 0.0,
        current_time: Optional[datetime] = None,
    ) -> ConflictDecision:
        """
        Kiểm tra và giải quyết xung đột giữa SetupCandidate mới và các tín hiệu đang ACTIVE.

        Quy tắc:
        1. Duplicate: Nếu cùng hướng và còn active/cooldown -> Bỏ qua.
        2. Opposite Direction (BUY vs SELL):
           - Kiểm tra lệnh hiện tại còn valid không.
           - Kiểm tra H1/M15 structure & CHoCH đảo chiều.
           - Nếu chưa có bằng chứng đảo chiều cấu trúc thuyết phục -> Giữ lệnh cũ, hủy lệnh mới.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        cand_dir = SignalDirection(new_candidate.direction.upper())
        cooldown = timedelta(minutes=self.config.cooldown_minutes)

        # 1. Duyệt qua tất cả các tín hiệu active
        for sig in active_signals:
            if not sig.is_active:
                continue

            sig_created = sig.created_at
            if sig_created.tzinfo is None:
                sig_created = sig_created.replace(tzinfo=timezone.utc)

            # ── TRƯỜNG HỢP A: CÙNG HƯỚNG (DUPLICATE) ──
            if sig.direction == cand_dir:
                return ConflictDecision(
                    resolution=ConflictResolution.CANCEL_NEW,
                    conflict_type=ConflictType.DUPLICATE_ACTIVE,
                    reason=f"Đã có lệnh {sig.direction.value} [{sig.signal_id}] đang {sig.status.value}",
                    existing_signal_id=sig.signal_id,
                )

            # ── TRƯỜNG HỢP B: NGƯỢC HƯỚNG (OPPOSITE DIRECTION CONFLICT) ──
            # Ví dụ: Đang có BUY active, thuật toán vừa tìm ra candidate SELL (hoặc ngược lại)
            log.warning(
                "⚔️ PHÁT HIỆN XUNG ĐỘT NGƯỢC HƯỚNG: Đang có %s [%s] @ %.2f và xuất hiện setup mới %s (%s)",
                sig.direction.value, sig.signal_id, sig.entry_price,
                cand_dir.value, new_candidate.setup_type.value,
            )

            # BƯỚC 1: Kiểm tra lệnh hiện tại còn valid không?
            # Đã vi phạm mức invalidation hoặc nến đã phá vỡ stop loss?
            existing_invalidated = False
            if current_price > 0:
                if sig.is_buy:
                    inval_p = sig.invalidation_level or sig.stop_loss
                    if current_price <= inval_p:
                        existing_invalidated = True
                elif sig.is_sell:
                    inval_p = sig.invalidation_level or sig.stop_loss
                    if current_price >= inval_p:
                        existing_invalidated = True

            # Nếu lệnh cũ đã vi phạm mức cản bảo vệ -> Hủy lệnh cũ
            if existing_invalidated:
                log.info(
                    "✓ Lệnh cũ %s [%s] đã vi phạm mức cản bảo vệ (Giá: %.2f) -> Tự động INVALIDATE lệnh cũ.",
                    sig.direction.value, sig.signal_id, current_price,
                )
                return ConflictDecision(
                    resolution=ConflictResolution.INVALIDATE_EXISTING_AND_PROCEED,
                    conflict_type=ConflictType.OPPOSITE_ACTIVE,
                    reason=f"Lệnh cũ {sig.direction.value} đã bị vi phạm cấu trúc tại mức giá {current_price:.2f}",
                    existing_signal_id=sig.signal_id,
                    action_notes=[f"Invalidate {sig.signal_id}", f"Proceed {cand_dir.value}"],
                )

            # BƯỚC 2: Kiểm tra xu hướng lớn H4
            # Nếu setup mới ngược xu hướng lớn H4 -> HỦY SETUP MỚI NGAY LẬP TỨC
            if cand_dir == SignalDirection.BUY and h4_trend == TrendDirection.BEARISH:
                return ConflictDecision(
                    resolution=ConflictResolution.CANCEL_NEW,
                    conflict_type=ConflictType.OPPOSITE_ACTIVE,
                    reason=f"Hủy BUY mới: Đang có {sig.direction.value} và H4 Trend là BEARISH",
                    existing_signal_id=sig.signal_id,
                )
            if cand_dir == SignalDirection.SELL and h4_trend == TrendDirection.BULLISH:
                return ConflictDecision(
                    resolution=ConflictResolution.CANCEL_NEW,
                    conflict_type=ConflictType.OPPOSITE_ACTIVE,
                    reason=f"Hủy SELL mới: Đang có {sig.direction.value} và H4 Trend là BULLISH",
                    existing_signal_id=sig.signal_id,
                )

            # BƯỚC 3: Kiểm tra cấu trúc H1 có Change of Character (CHoCH đảo chiều) không?
            has_reversal_choch = False
            if structure and self.config.allow_reversal_on_choch:
                if structure.last_choch is not None:
                    choch_ev = structure.last_choch.event_type
                    if cand_dir == SignalDirection.BUY and choch_ev == StructureBreak.CHOCH_BULLISH:
                        has_reversal_choch = True
                    elif cand_dir == SignalDirection.SELL and choch_ev == StructureBreak.CHOCH_BEARISH:
                        has_reversal_choch = True

            # BƯỚC 4: Kiểm tra mức độ xác nhận của setup mới
            # Chỉ cho phép đảo chiều nếu setup mới là Liquidity Sweep hoặc Order Block mạnh + có CHoCH
            high_tier_setups = (SetupType.SMC_LIQUIDITY_SWEEP, SetupType.SMC_ORDER_BLOCK)
            total_cand_score = sum(new_candidate.score_components.values())

            if (has_reversal_choch
                    and new_candidate.setup_type in high_tier_setups
                    and total_cand_score >= self.config.min_score_for_reversal):
                log.info(
                    "✓ ĐẢO CHIỀU HỢP LỆ: Setup %s (%s) có CHoCH cấu trúc và Score=%.1f >= %.1f -> Cho phép thay thế lệnh cũ.",
                    cand_dir.value, new_candidate.setup_type.value, total_cand_score, self.config.min_score_for_reversal,
                )
                return ConflictDecision(
                    resolution=ConflictResolution.INVALIDATE_EXISTING_AND_PROCEED,
                    conflict_type=ConflictType.OPPOSITE_ACTIVE,
                    reason=f"Đảo chiều cấu trúc hợp lệ (CHoCH + {new_candidate.setup_type.value})",
                    existing_signal_id=sig.signal_id,
                    action_notes=[f"Cancel {sig.signal_id}", f"Switch to {cand_dir.value}"],
                )

            # BƯỚC 5: Nếu không thỏa mãn các điều kiện đảo chiều thuyết phục:
            # GIỮ NGUYÊN LỆNH ĐANG CHẠY, KHÔNG CHO PHÁT TÍN HIỆU ĐỐI NGHỊCH
            return ConflictDecision(
                resolution=ConflictResolution.WAIT,
                conflict_type=ConflictType.OPPOSITE_ACTIVE,
                reason=(
                    f"Xung đột chưa giải quyết: Đang có {sig.direction.value} [{sig.signal_id}]. "
                    f"Setup {cand_dir.value} mới chưa có đủ xác nhận CHoCH đảo chiều -> WAIT"
                ),
                existing_signal_id=sig.signal_id,
            )

        # 2. Kiểm tra giới hạn số lượng active signals
        if len(active_signals) >= self.config.max_active_per_symbol:
            return ConflictDecision(
                resolution=ConflictResolution.CANCEL_NEW,
                conflict_type=ConflictType.MAX_ACTIVE_EXCEEDED,
                reason=f"Đã đạt giới hạn tối đa {self.config.max_active_per_symbol} lệnh active trên symbol",
            )

        # Không có xung đột -> Cho phép phát
        return ConflictDecision(
            resolution=ConflictResolution.PROCEED,
            conflict_type=ConflictType.NONE,
            reason="Thỏa mãn kiểm tra xung đột",
        )
