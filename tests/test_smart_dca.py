# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests cho Chiến lược Smart DCA Cứu Lệnh Về Hòa & X2 Lợi Nhuận.
"""

from datetime import datetime, timezone
import pytest

from app.strategy.conflict_resolver import (
    ConflictConfig,
    ConflictDecision,
    ConflictResolution,
    ConflictResolver,
    ConflictType,
)
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.telegram.formatter import format_signal_message
from config import DCAConfig, Settings


def test_dca_config_defaults():
    cfg = DCAConfig()
    assert cfg.enabled is True
    assert cfg.max_dca_steps == 1
    assert cfg.min_drawdown_distance == 3.5
    assert cfg.volume_multiplier == 1.0
    assert cfg.target_mode == "DOUBLE_PROFIT"
    assert cfg.breakeven_buffer == 0.5


def test_conflict_resolver_activates_dca_on_drawdown():
    resolver = ConflictResolver(config=ConflictConfig(allow_smart_dca=True, min_dca_distance_points=3.5))

    parent_sig = TradingSignal(
        signal_id="sig_buy1",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        entry_price=2740.0,
        stop_loss=2730.0,
        take_profit_1=2750.0,
        created_at=datetime.now(timezone.utc),
    )

    # Candidate BUY mới ở giá 2735.0 (âm 5.0 giá >= 3.5 giá)
    cand = SetupCandidate(
        setup_id="cand_dca",
        setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
        direction="BUY",
        entry_price=2735.0,
        stop_loss=2728.0,
        take_profit=2745.0,
    )

    decision = resolver.resolve_active_conflict(
        new_candidate=cand,
        active_signals=[parent_sig],
        current_price=2735.0,
    )

    assert decision.should_emit is True
    assert decision.resolution == ConflictResolution.PROCEED
    assert decision.conflict_type == ConflictType.DCA_RECOVERY
    assert decision.is_dca is True
    assert decision.parent_signal_id == "sig_buy1"
    assert decision.breakeven_price == 2737.5  # (2740 + 2735) / 2


def test_conflict_resolver_blocks_dca_if_too_close():
    resolver = ConflictResolver(config=ConflictConfig(allow_smart_dca=True, min_dca_distance_points=3.5))

    parent_sig = TradingSignal(
        signal_id="sig_buy1",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        entry_price=2740.0,
        stop_loss=2730.0,
        take_profit_1=2750.0,
        created_at=datetime.now(timezone.utc),
    )

    # Candidate BUY ở 2738.5 (chỉ âm 1.5 giá < 3.5 giá) -> Phải chặn trùng lặp
    cand = SetupCandidate(
        setup_id="cand_too_close",
        setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
        direction="BUY",
        entry_price=2738.5,
        stop_loss=2730.0,
        take_profit=2748.0,
    )

    decision = resolver.resolve_active_conflict(
        new_candidate=cand,
        active_signals=[parent_sig],
        current_price=2738.5,
    )

    assert decision.should_emit is False
    assert decision.resolution == ConflictResolution.CANCEL_NEW
    assert decision.conflict_type == ConflictType.DUPLICATE_ACTIVE


def test_conflict_resolver_blocks_second_dca():
    resolver = ConflictResolver(config=ConflictConfig(allow_smart_dca=True, min_dca_distance_points=3.5))

    parent_sig = TradingSignal(
        signal_id="sig_buy1",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        entry_price=2740.0,
        created_at=datetime.now(timezone.utc),
    )
    dca1_sig = TradingSignal(
        signal_id="sig_dca1",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        entry_price=2735.0,
        is_dca=True,
        parent_signal_id="sig_buy1",
        created_at=datetime.now(timezone.utc),
    )

    # Candidate thứ 3 ở 2730.0 -> Đã có DCA1 rồi nên không được DCA thêm lệnh thứ 2
    cand = SetupCandidate(
        setup_id="cand_dca2",
        setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
        direction="BUY",
        entry_price=2730.0,
        stop_loss=2724.0,
        take_profit=2740.0,
    )

    decision = resolver.resolve_active_conflict(
        new_candidate=cand,
        active_signals=[parent_sig, dca1_sig],
        current_price=2730.0,
    )

    assert decision.should_emit is False
    assert decision.conflict_type == ConflictType.DUPLICATE_ACTIVE


def test_dca_signal_formatting_telegram():
    sig = TradingSignal(
        signal_id="dca_1234",
        direction=SignalDirection.BUY,
        symbol="XAUUSD",
        timeframe="M5",
        entry_price=2735.0,
        stop_loss=2728.0,
        take_profit_1=2738.0,  # Hòa vốn + đệm
        take_profit_2=2748.0,  # TP gốc x2 lãi
        sl_distance=7.0,
        tp_distance=3.0,
        risk_reward_ratio=1.5,
        score=82.0,
        confidence="HIGH",
        setup_type="DCA_SMC_LIQUIDITY_SWEEP",
        is_dca=True,
        parent_signal_id="orig_5678",
        dca_breakeven_price=2737.5,
        reasons=["Hạ giá vốn vị thế tại vùng cản cứng SSL"],
    )

    text = format_signal_message(sig)
    assert "TÍN HIỆU DCA CỨU LỆNH — GỠ HÒA & X2 LỢI NHUẬN" in text
    assert "HÒA VỐN GIỎ LỆNH" in text
    assert "2737.5" in text
    assert "TP1 (Hòa vốn an toàn):" in text
    assert "TP2 (Kỳ vọng X2 Lãi):" in text
    assert "orig_567" in text
