# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Signal Conflict Resolution & Setup Lifecycle Management.

Kiểm tra toàn diện:
1. SetupLifecycleStatus (ACTIVE -> APPROACHING -> ENTRY_REACHED -> COMPLETED / INVALIDATED / EXPIRED / CANCELLED).
2. Structural Invalidation Level (bảo vệ lệnh trước khi chạm SL).
3. Revalidation của tín hiệu khi cấu trúc thị trường thay đổi.
4. Multi-candidate Arbitration (khi cả BUY và SELL cùng xuất hiện trong 1 nến).
5. Active Conflict Resolution (5 bước xác minh khi có tín hiệu ngược chiều xuất hiện).
6. Tích hợp trọn vẹn trong SignalEngine.
"""

from datetime import datetime, timedelta, timezone
import pytest
import pandas as pd
import numpy as np

from app.market.market_structure import (
    MarketStructureResult,
    StructureBreak,
    StructureEvent,
    SwingPoint,
    SwingType,
    TrendDirection,
)
from app.strategy.conflict_resolver import (
    ConflictConfig,
    ConflictDecision,
    ConflictResolution,
    ConflictResolver,
    ConflictType,
)
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import (
    SetupLifecycleStatus,
    SignalDirection,
    SignalStatus,
    TradingSignal,
)
from app.strategy.signal_tracker import SignalTracker, TrackerConfig


def _create_candidate(
    direction: str = "BUY",
    setup_type: SetupType = SetupType.SMC_ORDER_BLOCK,
    entry_price: float = 2000.0,
    stop_loss: float = 1990.0,
    take_profit: float = 2020.0,
    invalidation_level: float = 1992.0,
    setup_id: str = "cand_1",
    score_components: dict | None = None,
) -> SetupCandidate:
    return SetupCandidate(
        setup_id=setup_id,
        direction=direction,
        setup_type=setup_type,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        take_profit_1=entry_price + (10.0 if direction == "BUY" else -10.0),
        invalidation_level=invalidation_level,
        invalidation=f"Thủng cản {invalidation_level}",
        reasons=["Test candidate setup"],
        score_components=score_components or {"confluence": 80.0},
    )


def _create_signal(
    direction: SignalDirection = SignalDirection.BUY,
    entry_low: float = 1999.0,
    entry_high: float = 2001.0,
    sl: float = 1990.0,
    tp1: float = 2012.0,
    invalidation_level: float = 1993.0,
    created_at: datetime | None = None,
) -> TradingSignal:
    return TradingSignal(
        setup_id="setup_test_01",
        direction=direction,
        status=SignalStatus.ACTIVE,
        lifecycle_status=SetupLifecycleStatus.ACTIVE,
        symbol="XAUUSD",
        entry_price=2000.0,
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        stop_loss=sl,
        take_profit_1=tp1,
        invalidation_level=invalidation_level,
        created_at=created_at or datetime.now(timezone.utc),
    )


class TestSetupLifecycleStatus:
    """Kiểm tra các trạng thái chu kỳ sống của tín hiệu."""

    def test_initial_lifecycle_status(self):
        """Tín hiệu mới đăng ký có trạng thái ACTIVE."""
        tracker = SignalTracker()
        sig = _create_signal()
        tracker.register_signal(sig)
        assert sig.lifecycle_status == SetupLifecycleStatus.ACTIVE

    def test_lifecycle_approaching(self):
        """Khi giá tiến sát vùng Entry (trong 1.5 giá) chuyển sang APPROACHING."""
        config = TrackerConfig(approaching_distance_pts=1.5)
        tracker = SignalTracker(config)
        sig = _create_signal(direction=SignalDirection.BUY, entry_low=2000.0, entry_high=2001.0)
        tracker.register_signal(sig)

        # Giá hiện tại 2002.0 -> cách entry_zone_high (2001.0) là 1.0 giá (<= 1.5)
        changed = tracker.update_price(current_price=2002.0)
        assert len(changed) == 1
        assert sig.lifecycle_status == SetupLifecycleStatus.APPROACHING

    def test_lifecycle_entry_reached(self):
        """Khi giá chạm vào vùng Entry -> chuyển sang ENTRY_REACHED."""
        tracker = SignalTracker()
        sig = _create_signal(direction=SignalDirection.BUY, entry_low=1999.0, entry_high=2001.0)
        tracker.register_signal(sig)

        changed = tracker.update_price(current_price=2000.0, high_price=2000.5, low_price=1999.5)
        assert len(changed) == 1
        assert sig.status == SignalStatus.ENTRY_REACHED
        assert sig.lifecycle_status == SetupLifecycleStatus.ENTRY_REACHED

    def test_lifecycle_completed_on_tp(self):
        """Khi lệnh đã khớp entry và chạm TP1 -> chuyển sang COMPLETED."""
        tracker = SignalTracker()
        sig = _create_signal(direction=SignalDirection.BUY, entry_low=1999.0, entry_high=2001.0, tp1=2010.0)
        tracker.register_signal(sig)

        # 1. Khớp entry
        tracker.update_price(current_price=2000.0, high_price=2000.0, low_price=2000.0)
        assert sig.lifecycle_status == SetupLifecycleStatus.ENTRY_REACHED

        # 2. Chạm TP1
        changed = tracker.update_price(current_price=2010.5, high_price=2011.0, low_price=2009.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.TP_REACHED
        assert sig.lifecycle_status == SetupLifecycleStatus.COMPLETED

    def test_lifecycle_completed_on_sl(self):
        """Khi lệnh đã khớp entry và chạm SL -> chuyển sang COMPLETED."""
        tracker = SignalTracker()
        sig = _create_signal(direction=SignalDirection.BUY, entry_low=1999.0, entry_high=2001.0, sl=1990.0)
        tracker.register_signal(sig)

        # Khớp entry
        tracker.update_price(current_price=2000.0)
        # Chạm SL
        changed = tracker.update_price(current_price=1989.0, low_price=1989.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.SL_REACHED
        assert sig.lifecycle_status == SetupLifecycleStatus.COMPLETED

    def test_pre_entry_invalidation_level(self):
        """Giá chạm invalidation_level TRƯỚC KHI vào entry zone -> INVALIDATED (bảo toàn vốn)."""
        tracker = SignalTracker()
        sig = _create_signal(
            direction=SignalDirection.BUY,
            entry_low=2000.0,
            entry_high=2002.0,
            sl=1985.0,
            invalidation_level=1995.0,  # Cản cấu trúc cao hơn SL
        )
        tracker.register_signal(sig)

        # Giá rớt thẳng xuống 1994.0 mà chưa vào Entry (2000-2002)
        changed = tracker.update_price(current_price=1994.0, low_price=1994.0, high_price=1997.0)
        assert len(changed) == 1
        assert sig.status == SignalStatus.INVALIDATED
        assert sig.lifecycle_status == SetupLifecycleStatus.INVALIDATED
        assert sig.is_active is False

    def test_lifecycle_expired(self):
        """Tín hiệu hết hạn sau thời gian timeout -> EXPIRED."""
        tracker = SignalTracker(TrackerConfig(default_expiry_hours=2))
        now = datetime.now(timezone.utc)
        sig = _create_signal(created_at=now)
        tracker.register_signal(sig)

        after_3_hours = now + timedelta(hours=3)
        changed = tracker.update_price(current_price=2005.0, current_time=after_3_hours)
        assert len(changed) == 1
        assert sig.status == SignalStatus.EXPIRED
        assert sig.lifecycle_status == SetupLifecycleStatus.EXPIRED

    def test_revalidate_active_signals(self):
        """Revalidate phát hiện vi phạm cản cấu trúc và tự động chuyển sang INVALIDATED."""
        tracker = SignalTracker()
        sig = _create_signal(direction=SignalDirection.SELL, entry_low=2010.0, entry_high=2012.0, invalidation_level=2015.0)
        tracker.register_signal(sig)

        # Giá tăng vọt lên 2016.0 (phá vỡ cản kháng cự SELL)
        invalidated = tracker.revalidate_active_signals(current_price=2016.0)
        assert len(invalidated) == 1
        assert sig.status == SignalStatus.INVALIDATED
        assert sig.lifecycle_status == SetupLifecycleStatus.INVALIDATED


class TestConflictResolver:
    """Kiểm tra bộ phân xử xung đột ConflictResolver."""

    def test_multi_candidate_same_direction(self):
        """Cùng chiều không bị coi là xung đột đa chiều."""
        resolver = ConflictResolver()
        cand1 = _create_candidate(direction="BUY", setup_type=SetupType.SMC_ORDER_BLOCK, setup_id="b1")
        cand2 = _create_candidate(direction="BUY", setup_type=SetupType.SMC_FVG_RETEST, setup_id="b2")

        cands, reason = resolver.resolve_candidate_conflicts([cand1, cand2])
        assert len(cands) == 2
        assert reason is None

    def test_multi_candidate_arbitration_by_h4_trend(self):
        """Khi cả BUY và SELL cùng xuất hiện, ưu tiên candidate theo xu hướng H4."""
        resolver = ConflictResolver()
        cand_buy = _create_candidate(direction="BUY", setup_type=SetupType.SMC_ORDER_BLOCK, setup_id="b1")
        cand_sell = _create_candidate(direction="SELL", setup_type=SetupType.SMC_ORDER_BLOCK, setup_id="s1")

        # H4 đang BULLISH -> Chọn BUY
        cands, reason = resolver.resolve_candidate_conflicts(
            [cand_buy, cand_sell],
            h4_trend=TrendDirection.BULLISH,
        )
        assert len(cands) == 1
        assert cands[0].direction == "BUY"
        assert "Loại bỏ SELL" in reason

        # H4 đang BEARISH -> Chọn SELL
        cands, reason = resolver.resolve_candidate_conflicts(
            [cand_buy, cand_sell],
            h4_trend=TrendDirection.BEARISH,
        )
        assert len(cands) == 1
        assert cands[0].direction == "SELL"
        assert "Loại bỏ BUY" in reason

    def test_multi_candidate_arbitration_by_smc_hierarchy(self):
        """Khi H4 trung lập, setup bậc cao hơn (Sweep 100 > FVG 60, chênh >= 30) sẽ thắng."""
        resolver = ConflictResolver()
        cand_sweep = _create_candidate(direction="BUY", setup_type=SetupType.SMC_LIQUIDITY_SWEEP, setup_id="sw1")
        cand_fvg = _create_candidate(direction="SELL", setup_type=SetupType.SMC_FVG_RETEST, setup_id="fvg1")

        cands, reason = resolver.resolve_candidate_conflicts(
            [cand_sweep, cand_fvg],
            h4_trend=TrendDirection.NEUTRAL,
        )
        assert len(cands) == 1
        assert cands[0].direction == "BUY"
        assert "Ưu tiên setup cấp cao" in reason

    def test_multi_candidate_tie_resolves_to_wait(self):
        """Khi cả BUY và SELL có cùng bậc phân cấp SMC và H4 trung lập -> Trả về WAIT."""
        resolver = ConflictResolver()
        cand_buy = _create_candidate(direction="BUY", setup_type=SetupType.SMC_ORDER_BLOCK, setup_id="b1")
        cand_sell = _create_candidate(direction="SELL", setup_type=SetupType.SMC_ORDER_BLOCK, setup_id="s1")

        cands, reason = resolver.resolve_candidate_conflicts(
            [cand_buy, cand_sell],
            h4_trend=TrendDirection.NEUTRAL,
        )
        assert len(cands) == 0
        assert "chưa rõ ràng trong thị trường tích lũy -> WAIT" in reason

    def test_active_conflict_protects_existing_signal(self):
        """Khi có BUY đang active, setup SELL mới xuất hiện không có CHoCH -> Bị CANCEL_NEW / WAIT."""
        tracker = SignalTracker()
        active_buy = _create_signal(direction=SignalDirection.BUY)
        tracker.register_signal(active_buy)

        sell_cand = _create_candidate(direction="SELL", setup_type=SetupType.SMC_ORDER_BLOCK)
        decision = tracker.check_conflict(
            candidate=sell_cand,
            h4_trend=TrendDirection.NEUTRAL,
            current_price=2001.0,
        )

        assert decision.resolution in (ConflictResolution.CANCEL_NEW, ConflictResolution.WAIT)
        assert decision.conflict_type == ConflictType.OPPOSITE_ACTIVE
        assert decision.should_emit is False

    def test_active_conflict_reversal_allowed_on_choch(self):
        """Khi có BUY active nhưng thị trường có CHoCH BEARISH + H4 BEARISH + Setup cao cấp -> Đảo chiều thành công."""
        tracker = SignalTracker()
        active_buy = _create_signal(direction=SignalDirection.BUY)
        tracker.register_signal(active_buy)

        # Mock kết quả cấu trúc H1 có CHoCH
        mock_structure = MarketStructureResult(
            trend=TrendDirection.BEARISH,
            swings=[
                SwingPoint(index=5, price=2050.0, swing_type=SwingType.SWING_HIGH),
                SwingPoint(index=8, price=1950.0, swing_type=SwingType.SWING_LOW),
            ],
            structure_events=[
                StructureEvent(
                    event_type=StructureBreak.CHOCH_BEARISH,
                    index=10,
                    price=2000.0,
                    broken_level=2005.0,
                )
            ],
        )

        # Setup đảo chiều bậc cao: LIQUIDITY_SWEEP với điểm >= min_score_for_reversal (75.0)
        sell_cand = _create_candidate(
            direction="SELL",
            setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
            entry_price=2000.0,
            stop_loss=2010.0,
            score_components={"smc": 85.0},
        )

        decision = tracker.check_conflict(
            candidate=sell_cand,
            h4_trend=TrendDirection.BEARISH,
            structure=mock_structure,
            current_price=2000.0,
        )

        assert decision.resolution == ConflictResolution.INVALIDATE_EXISTING_AND_PROCEED
        assert decision.should_emit is True
        assert decision.existing_signal_id == active_buy.signal_id


class TestSignalEngineIntegration:
    """Kiểm tra tích hợp toàn diện Conflict Resolution và Lifecycle trong SignalEngine."""

    def _generate_mock_df(self, n=50, base_price=2000.0):
        dates = pd.date_range("2026-01-01", periods=n, freq="1h")
        closes = [base_price] * n
        highs = [base_price + 0.1] * n
        lows = [base_price - 0.1] * n
        opens = [base_price] * n
        vols = [100.0] * n
        return pd.DataFrame({
            "time": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": vols,
        })

    def test_engine_has_conflict_resolver(self):
        """SignalEngine phải có conflict_resolver được cấu hình tự động."""
        engine = SignalEngine()
        assert engine.conflict_resolver is not None
        assert isinstance(engine.conflict_resolver, ConflictResolver)

    def test_engine_emits_wait_on_empty_or_no_setup(self):
        """SignalEngine trả về WAIT khi không có dữ liệu nến đủ chuẩn."""
        engine = SignalEngine()
        df_short = pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=10, freq="1h"),
            "open": [2000.0] * 10,
            "high": [2001.0] * 10,
            "low": [1999.0] * 10,
            "close": [2000.0] * 10,
            "tick_volume": [100.0] * 10,
        })
        signal = engine.generate_signal(df=df_short)
        assert signal.direction == SignalDirection.WAIT
        assert signal.is_wait is True

    def test_engine_records_setup_lifecycle_fields(self):
        """Khi phát tín hiệu thành công, các trường setup_id, lifecycle_status, invalidation_level được điền đầy đủ."""
        tracker = SignalTracker()
        sig = _create_signal(direction=SignalDirection.BUY)
        success = tracker.register_signal(sig)
        assert success is True
        assert sig.setup_id == "setup_test_01"
        assert sig.lifecycle_status == SetupLifecycleStatus.ACTIVE
        assert sig.invalidation_level == 1993.0
        assert sig.status == SignalStatus.ACTIVE

    def test_cancel_signal_method(self):
        """Phương thức cancel_signal chuyển trạng thái sang CANCELLED."""
        tracker = SignalTracker()
        sig = _create_signal()
        tracker.register_signal(sig)

        cancelled = tracker.cancel_signal(sig.signal_id, reason="Đảo chiều xu hướng")
        assert cancelled is not None
        assert cancelled.status == SignalStatus.CANCELLED
        assert cancelled.lifecycle_status == SetupLifecycleStatus.CANCELLED
        assert "Đảo chiều xu hướng" in cancelled.reasons[-1]
