# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Signal Models.

Định nghĩa các data models cho tín hiệu giao dịch:
- SignalDirection (BUY/SELL/WAIT).
- SignalStatus (ACTIVE/TP_REACHED/SL_REACHED/...).
- TradingSignal (tín hiệu đầy đủ).

KHÔNG có chức năng đặt lệnh.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class SignalDirection(Enum):
    """Hướng tín hiệu."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class SignalStatus(Enum):
    """Trạng thái tín hiệu."""
    ACTIVE = "ACTIVE"                 # Đang chờ giá vào entry zone
    ENTRY_REACHED = "ENTRY_REACHED"   # Giá đã vào entry zone
    TP_REACHED = "TP_REACHED"         # Chạm Take Profit
    SL_REACHED = "SL_REACHED"         # Chạm Stop Loss
    INVALIDATED = "INVALIDATED"       # Điều kiện bị phá vỡ
    EXPIRED = "EXPIRED"               # Hết hạn
    UNRESOLVED = "UNRESOLVED"         # Không xác định được kết quả


@dataclass
class TradingSignal:
    """
    Tín hiệu giao dịch đầy đủ.

    Đây là OUTPUT chính của Signal Engine.
    KHÔNG chứa chức năng đặt lệnh.
    """

    # Identification
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy_version: str = "v1.0"

    # Direction & Status
    direction: SignalDirection = SignalDirection.WAIT
    status: SignalStatus = SignalStatus.ACTIVE

    # Symbol & Timeframe
    symbol: str = "XAUUSD"
    timeframe: str = "H1"

    # Price Levels
    entry_price: float = 0.0
    entry_zone_high: float = 0.0    # Vùng entry trên
    entry_zone_low: float = 0.0     # Vùng entry dưới
    stop_loss: float = 0.0
    take_profit_1: float = 0.0      # TP1 (chính)
    take_profit_2: float = 0.0      # TP2 (mở rộng, tùy chọn)

    # Risk Management
    risk_reward_ratio: float = 0.0   # R:R ratio
    sl_distance: float = 0.0        # Khoảng cách SL (points)
    tp_distance: float = 0.0        # Khoảng cách TP (points)

    # Scoring (KHÔNG phải xác suất thắng)
    score: float = 0.0              # Điểm setup (0-100)
    confidence: str = "LOW"         # LOW / MEDIUM / HIGH

    # Analysis Context
    trend_h4: str = ""
    trend_h1: str = ""
    setup_type: str = ""            # Loại setup (ví dụ: "BOS_RETEST", "LIQUIDITY_SWEEP")
    reasons: list[str] = field(default_factory=list)
    invalidation: str = ""          # Điều kiện vô hiệu hóa tín hiệu

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Tín hiệu còn active không."""
        return self.status in (SignalStatus.ACTIVE, SignalStatus.ENTRY_REACHED)

    @property
    def is_buy(self) -> bool:
        return self.direction == SignalDirection.BUY

    @property
    def is_sell(self) -> bool:
        return self.direction == SignalDirection.SELL

    @property
    def is_wait(self) -> bool:
        return self.direction == SignalDirection.WAIT

    def summary(self) -> str:
        """Tóm tắt tín hiệu dạng text."""
        if self.is_wait:
            return f"[{self.signal_id}] WAIT — {', '.join(self.reasons) or 'No setup'}"

        return (
            f"[{self.signal_id}] {self.direction.value} {self.symbol}\n"
            f"  Entry: {self.entry_zone_low:.2f} – {self.entry_zone_high:.2f}\n"
            f"  SL: {self.stop_loss:.2f} ({self.sl_distance:.1f} pts)\n"
            f"  TP1: {self.take_profit_1:.2f} ({self.tp_distance:.1f} pts)\n"
            f"  R:R: 1:{self.risk_reward_ratio:.1f}\n"
            f"  Score: {self.score:.0f}/100 ({self.confidence})\n"
            f"  Setup: {self.setup_type}\n"
            f"  Reasons: {', '.join(self.reasons)}\n"
            f"  Invalidation: {self.invalidation}"
        )

    @classmethod
    def from_dict(cls, data: dict) -> "TradingSignal":
        """Khôi phục TradingSignal từ dictionary hoặc DB row."""
        direction_val = data.get("direction", "WAIT")
        try:
            direction = SignalDirection(direction_val)
        except ValueError:
            direction = SignalDirection.WAIT

        status_val = data.get("status", "ACTIVE")
        try:
            status = SignalStatus(status_val)
        except ValueError:
            status = SignalStatus.ACTIVE

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = datetime.now(timezone.utc)
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)

        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None

        reasons = data.get("reasons", [])
        if isinstance(reasons, str):
            try:
                import json
                reasons = json.loads(reasons)
            except Exception:
                reasons = [reasons]

        return cls(
            signal_id=str(data.get("signal_id", "")),
            strategy_version=str(data.get("strategy_version", "v1.0")),
            direction=direction,
            status=status,
            symbol=str(data.get("symbol", "XAUUSD")),
            timeframe=str(data.get("timeframe", "M5")),
            entry_price=float(data.get("entry_price") or 0.0),
            entry_zone_high=float(data.get("entry_zone_high") or 0.0),
            entry_zone_low=float(data.get("entry_zone_low") or 0.0),
            stop_loss=float(data.get("stop_loss") or 0.0),
            take_profit_1=float(data.get("take_profit_1") or 0.0),
            take_profit_2=float(data.get("take_profit_2") or 0.0),
            risk_reward_ratio=float(data.get("risk_reward_ratio") or 0.0),
            sl_distance=float(data.get("sl_distance") or 0.0),
            tp_distance=float(data.get("tp_distance") or 0.0),
            score=float(data.get("score") or 0.0),
            confidence=str(data.get("confidence", "MEDIUM")),
            trend_h4=str(data.get("trend_h4", "")),
            trend_h1=str(data.get("trend_h1", "")),
            setup_type=str(data.get("setup_type", "")),
            reasons=list(reasons),
            invalidation=str(data.get("invalidation", "")),
            created_at=created_at,
            expires_at=expires_at,
        )
