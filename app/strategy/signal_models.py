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
    CANCELLED = "CANCELLED"           # Bị hủy do xuất hiện xung đột
    EXPIRED = "EXPIRED"               # Hết hạn
    UNRESOLVED = "UNRESOLVED"         # Không xác định được kết quả


class SetupLifecycleStatus(Enum):
    """Trạng thái chu kỳ sống (Lifecycle) của Setup giao dịch."""
    DISCOVERED = "DISCOVERED"         # Vừa phát hiện từ nến / cấu trúc
    VALIDATED = "VALIDATED"           # Đã qua RiskFilter và Scoring
    ACTIVE = "ACTIVE"                 # Đang phát và theo dõi, chờ giá về entry
    APPROACHING = "APPROACHING"       # Giá đang tiến sát vùng entry
    ENTRY_REACHED = "ENTRY_REACHED"   # Đã khớp vào vùng entry (In-Trade)
    INVALIDATED = "INVALIDATED"       # Bị vô hiệu hóa do phá vỡ cấu trúc
    EXPIRED = "EXPIRED"               # Hết hạn thời gian chờ mà chưa khớp
    CANCELLED = "CANCELLED"           # Bị hủy do xuất hiện xung đột (Conflict)
    COMPLETED = "COMPLETED"           # Đã hoàn tất (chạm TP hoặc SL)


@dataclass
class TradingSignal:
    """
    Tín hiệu giao dịch đầy đủ.

    Đây là OUTPUT chính của Signal Engine.
    KHÔNG chứa chức năng đặt lệnh.
    """

    # Identification & Lifecycle
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    setup_id: str = ""
    strategy_version: str = "v1.0"
    lifecycle_status: SetupLifecycleStatus = SetupLifecycleStatus.ACTIVE

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
    invalidation_level: Optional[float] = None  # Mức giá cụ thể làm vô hiệu hóa cấu trúc

    # Risk Management
    risk_reward_ratio: float = 0.0   # R:R ratio
    sl_distance: float = 0.0        # Khoảng cách SL (points)
    tp_distance: float = 0.0        # Khoảng cách TP (points)

    # Scoring (KHÔNG phải xác suất thắng)
    score: float = 0.0              # Điểm setup (0-100)
    confidence: str = "LOW"         # LOW / MEDIUM / HIGH
    score_breakdown: dict = field(default_factory=dict)  # Chi tiết thành phần điểm & trọng số động

    # Analysis Context & Regime
    trend_h4: str = ""
    trend_h1: str = ""
    setup_type: str = ""            # Loại setup (ví dụ: "BOS_RETEST", "LIQUIDITY_SWEEP")
    market_regime: str = "UNKNOWN"  # Regime thị trường tại thời điểm phát
    structure_context: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    invalidation: str = ""          # Mô tả điều kiện vô hiệu hóa tín hiệu

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    revalidated_at: Optional[datetime] = None

    # Adaptive Exit Tracking (Phase 12)
    tier_reached: int = 0                  # 0: Chưa chốt, 1: Đã chốt Tier 1 (50%), 2: Đã chốt Tier 2 (30%)
    max_favorable_pnl: float = 0.0         # Mức lãi lớn nhất từng đạt được (points)
    trailing_mode: str = "NONE"            # ATR_DYNAMIC, SWING_STRUCTURE, BREAKEVEN

    def __post_init__(self):
        if not self.setup_id and self.signal_id:
            self.setup_id = f"setup_{self.signal_id}"

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

    @property
    def is_predictive(self) -> bool:
        """Kiểm tra xem đây có phải kế hoạch dự đoán từ xa (Limit Setup) không."""
        return self.setup_type == "PREDICTIVE_LIMIT"

    def summary(self) -> str:
        """Tóm tắt tín hiệu dạng text."""
        if self.is_wait:
            return f"[{self.signal_id}] WAIT — {', '.join(self.reasons) or 'No setup'}"

        return (
            f"[{self.signal_id}] {self.direction.value} {self.symbol}\n"
            f"  Entry: {self.entry_zone_low:.2f} – {self.entry_zone_high:.2f}\n"
            f"  SL: {self.stop_loss:.2f} ({self.sl_distance:.1f} giá)\n"
            f"  TP1: {self.take_profit_1:.2f} ({self.tp_distance:.1f} giá - Tỷ lệ ăn cao)\n"
            f"  TP2: {self.take_profit_2:.2f} (Kỳ vọng mở rộng)\n"
            f"  R:R: 1:{self.risk_reward_ratio:.1f}\n"
            f"  Score: {self.score:.0f}/100 ({self.confidence})\n"
            f"  Setup: {self.setup_type}\n"
            f"  Reasons: {', '.join(self.reasons)}\n"
            f"  Invalidation: {self.invalidation}"
        )

    def to_dict(self) -> dict:
        """Chuyển đổi TradingSignal thành dict để lưu trữ hoặc truyền qua API."""
        return {
            "signal_id": self.signal_id,
            "setup_id": self.setup_id,
            "strategy_version": self.strategy_version,
            "lifecycle_status": self.lifecycle_status.value,
            "direction": self.direction.value,
            "status": self.status.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "entry_price": self.entry_price,
            "entry_zone_high": self.entry_zone_high,
            "entry_zone_low": self.entry_zone_low,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "invalidation_level": self.invalidation_level,
            "risk_reward_ratio": self.risk_reward_ratio,
            "sl_distance": self.sl_distance,
            "tp_distance": self.tp_distance,
            "score": self.score,
            "confidence": self.confidence,
            "score_breakdown": self.score_breakdown,
            "trend_h4": self.trend_h4,
            "trend_h1": self.trend_h1,
            "setup_type": self.setup_type,
            "market_regime": self.market_regime,
            "structure_context": self.structure_context,
            "is_predictive": self.is_predictive,
            "reasons": self.reasons,
            "invalidation": self.invalidation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revalidated_at": self.revalidated_at.isoformat() if self.revalidated_at else None,
        }

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

        lifecycle_val = data.get("lifecycle_status", "ACTIVE")
        try:
            lifecycle_status = SetupLifecycleStatus(lifecycle_val)
        except ValueError:
            lifecycle_status = SetupLifecycleStatus.ACTIVE

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

        revalidated_at = data.get("revalidated_at")
        if isinstance(revalidated_at, str):
            try:
                revalidated_at = datetime.fromisoformat(revalidated_at)
            except Exception:
                revalidated_at = None

        reasons = data.get("reasons", [])
        if isinstance(reasons, str):
            try:
                import json
                reasons = json.loads(reasons)
            except Exception:
                reasons = [reasons]

        inval_level = data.get("invalidation_level")
        if inval_level is not None:
            try:
                inval_level = float(inval_level)
            except (ValueError, TypeError):
                inval_level = None

        struct_ctx = data.get("structure_context", {})
        if isinstance(struct_ctx, str):
            try:
                import json
                struct_ctx = json.loads(struct_ctx)
            except Exception:
                struct_ctx = {}

        sig_id = str(data.get("signal_id", ""))
        setup_id = str(data.get("setup_id", "") or f"setup_{sig_id}")

        score_bd = data.get("score_breakdown", {})
        if isinstance(score_bd, str):
            try:
                import json
                score_bd = json.loads(score_bd)
            except Exception:
                score_bd = {}

        return cls(
            signal_id=sig_id,
            setup_id=setup_id,
            strategy_version=str(data.get("strategy_version", "v1.0")),
            lifecycle_status=lifecycle_status,
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
            invalidation_level=inval_level,
            risk_reward_ratio=float(data.get("risk_reward_ratio") or 0.0),
            sl_distance=float(data.get("sl_distance") or 0.0),
            tp_distance=float(data.get("tp_distance") or 0.0),
            score=float(data.get("score") or 0.0),
            confidence=str(data.get("confidence", "MEDIUM")),
            score_breakdown=score_bd if isinstance(score_bd, dict) else {},
            trend_h4=str(data.get("trend_h4", "")),
            trend_h1=str(data.get("trend_h1", "")),
            setup_type=str(data.get("setup_type", "")),
            market_regime=str(data.get("market_regime", "UNKNOWN")),
            structure_context=struct_ctx if isinstance(struct_ctx, dict) else {},
            reasons=list(reasons),
            invalidation=str(data.get("invalidation", "")),
            created_at=created_at,
            expires_at=expires_at,
            revalidated_at=revalidated_at,
        )
