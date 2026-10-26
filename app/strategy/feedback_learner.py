# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Self-Learning Feedback Engine & Root Cause Analysis (Phase 8).

Tự học và thích ứng từ kết quả các lệnh đã hoàn tất:
- Phân loại nguyên nhân thành công / thất bại (Root Cause Analysis).
- Nhận diện các mẫu hình SL do biến động tin tức (News Spike), bẻ gãy cấu trúc (Structural Break)
  hay do giãn Spread phiên giao dịch (Spread Widening).
- Tự động điều chỉnh trọng số Confluence Score cho từng cặp (Setup Type, Market Regime).
- Thích ứng hệ số khoảng đệm Cushion khi phát hiện SL thường xuyên bị quét do giãn spread.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Optional

import pandas as pd

from app.strategy.signal_models import SignalDirection, TradingSignal
from logger import get_logger

log = get_logger("strategy.feedback")


class RootCause(str, Enum):
    """Phân loại nguyên nhân kết quả của lệnh."""
    # Nguyên nhân thua lỗ (SL / Invalidation)
    NEWS_SPIKE = "NEWS_SPIKE"                       # Quét do bão tin tức USD / nến biến động lớn > 2.5x ATR
    STRUCTURAL_FAILURE = "STRUCTURAL_FAILURE"       # Cấu trúc thị trường bị phá vỡ (ChoCH / BOS ngược hướng)
    MOMENTUM_EXHAUSTION = "MOMENTUM_EXHAUSTION"     # Động lượng cạn kiệt / phân kỳ giá (RSI divergence)
    SPREAD_WIDENING = "SPREAD_WIDENING"             # Bị quét do giãn spread phiên (SL quá sát)
    TIMEOUT_EXPIRED = "TIMEOUT_EXPIRED"             # Hết thời gian chờ / nến không chạm vùng entry
    NORMAL_LOSS = "NORMAL_LOSS"                     # Thua lỗ bình thường trong phương sai xác suất cho phép

    # Nguyên nhân thành công (TP)
    CLEAN_TREND_RUN = "CLEAN_TREND_RUN"             # Đi đúng xu hướng mượt mà, đạt TP không cản trở
    LIQUIDITY_REVERSAL = "LIQUIDITY_REVERSAL"       # Đảo chiều chuẩn xác sau quét thanh khoản SMC
    MOMENTUM_SURGE = "MOMENTUM_SURGE"               # Bùng nổ khối lượng đẩy nhanh tới mục tiêu


@dataclass
class TradeOutcomeAnalysis:
    """Báo cáo phân tích chuyên sâu nguyên nhân kết quả lệnh."""
    signal_id: str
    final_status: str
    root_cause: RootCause
    pnl_points: float
    pnl_r: float
    duration_seconds: int
    mfe_points: float = 0.0     # Maximum Favorable Excursion (Khoảng giá chạy lời tối đa)
    mae_points: float = 0.0     # Maximum Adverse Excursion (Khoảng giá chạy ngược tối đa)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "final_status": self.final_status,
            "root_cause": self.root_cause.value,
            "pnl_points": round(self.pnl_points, 2),
            "pnl_r": round(self.pnl_r, 2),
            "duration_seconds": self.duration_seconds,
            "mfe_points": round(self.mfe_points, 2),
            "mae_points": round(self.mae_points, 2),
            "explanation": self.explanation,
        }


class TradeOutcomeAnalyzer:
    """Bộ phân tích nguyên nhân và đo lường sâu kết quả lệnh đã đóng."""

    @staticmethod
    def analyze(
        signal: TradingSignal,
        final_status: str,
        exit_price: float,
        duration_seconds: int = 0,
        current_candle_range: Optional[float] = None,
        atr_value: Optional[float] = None,
        current_spread: Optional[float] = None,
        is_near_news: bool = False,
        news_title: Optional[str] = None,
    ) -> TradeOutcomeAnalysis:
        """
        Phân tích và xác định nguyên nhân đóng lệnh dựa trên dữ liệu thị trường thực tế.
        """
        # 1. Tính PnL points và PnL R
        if signal.direction == SignalDirection.BUY:
            pnl_pts = exit_price - signal.entry_price
        else:
            pnl_pts = signal.entry_price - exit_price

        sl_dist = signal.sl_distance if signal.sl_distance > 0 else 5.0
        pnl_r = pnl_pts / sl_dist if sl_dist > 0 else 0.0

        is_tp = "TP" in final_status.upper() or pnl_pts > 0.5
        is_sl = "SL" in final_status.upper() or pnl_pts < -0.5

        # 2. Phân loại nguyên nhân thắng (TP)
        if is_tp:
            if "LIQUIDITY" in signal.setup_type.upper():
                cause = RootCause.LIQUIDITY_REVERSAL
                expl = "Giá đảo chiều chuẩn xác sau pha quét thanh khoản SMC và chạm TP."
            elif duration_seconds < 900:  # Đạt TP dưới 15 phút
                cause = RootCause.MOMENTUM_SURGE
                expl = "Động lượng bùng nổ mạnh mẽ, đẩy giá chạm Take Profit trong thời gian ngắn."
            else:
                cause = RootCause.CLEAN_TREND_RUN
                expl = "Giá di chuyển mượt mà theo cấu trúc xu hướng, đạt mục tiêu lợi nhuận."

            return TradeOutcomeAnalysis(
                signal_id=signal.signal_id,
                final_status=final_status,
                root_cause=cause,
                pnl_points=pnl_pts,
                pnl_r=pnl_r,
                duration_seconds=duration_seconds,
                explanation=expl,
            )

        # 3. Phân loại nguyên nhân thua lỗ (SL hoặc Invalidation)
        if is_near_news:
            cause = RootCause.NEWS_SPIKE
            expl = f"Dính Stop Loss do biến động mạnh gần khung giờ tin tức USD: {news_title or 'Tin vĩ mô'}."
        elif current_candle_range and atr_value and current_candle_range > (2.5 * atr_value):
            cause = RootCause.NEWS_SPIKE
            expl = f"Cây nến đóng lệnh có biên độ bất thường ({current_candle_range:.1f} > 2.5x ATR {atr_value:.1f}), nghi ngờ biến động tin tức."
        elif current_spread and sl_dist > 0 and (current_spread / sl_dist) > 0.40:
            cause = RootCause.SPREAD_WIDENING
            expl = f"Khoảng SL ({sl_dist:.1f}) quá sát so với mức giãn spread ({current_spread:.1f}), bị quét trước khi giá chạy."
        elif final_status.upper() in ("CANCELLED", "INVALIDATED", "EXPIRED"):
            cause = RootCause.STRUCTURAL_FAILURE
            expl = "Tín hiệu bị hủy sớm do cấu trúc bị bẻ gãy trước khi chạm entry hoặc lệnh ứ đọng quá lâu."
        else:
            cause = RootCause.NORMAL_LOSS
            expl = "Lệnh chạm Stop Loss trong biên độ dao động thị trường thông thường (phương sai rủi ro)."

        return TradeOutcomeAnalysis(
            signal_id=signal.signal_id,
            final_status=final_status,
            root_cause=cause,
            pnl_points=pnl_pts,
            pnl_r=pnl_r,
            duration_seconds=duration_seconds,
            explanation=expl,
        )


class SelfLearningFeedbackEngine:
    """
    Động cơ tự học và thích ứng đa chiều từ kết quả các lệnh đã hoàn tất.
    """

    def __init__(
        self,
        repository: Optional[Any] = None,
        min_samples_for_learning: int = 5,
    ):
        self.repository = repository
        self.min_samples = min_samples_for_learning
        self.cached_stats: dict[str, Any] = {}
        self.last_refresh: Optional[datetime] = None

    def refresh(self) -> dict[str, Any]:
        """Tải dữ liệu từ database và tính toán ma trận thích ứng."""
        if not self.repository:
            return {}

        outcomes = self.repository.get_historical_outcomes()
        if not outcomes:
            self.cached_stats = {}
            return {}

        # 1. Thống kê theo Setup Type
        setup_stats: dict[str, dict] = {}
        # 2. Thống kê theo cặp (Setup Type, Market Regime)
        pair_stats: dict[tuple[str, str], dict] = {}
        # 3. Phân bổ Root Causes
        root_causes: dict[str, int] = {}

        for row in outcomes:
            st = row.get("setup_type") or "UNKNOWN"
            regime = row.get("market_regime") or "UNKNOWN"
            final_status = row.get("final_status", "")
            is_win = "TP" in final_status.upper() or float(row.get("pnl_points") or 0.0) > 0.5

            # Setup tổng quát
            if st not in setup_stats:
                setup_stats[st] = {"total": 0, "wins": 0, "losses": 0}
            setup_stats[st]["total"] += 1
            if is_win:
                setup_stats[st]["wins"] += 1
            else:
                setup_stats[st]["losses"] += 1

            # Cặp (Setup, Regime)
            pair_key = (st, regime)
            if pair_key not in pair_stats:
                pair_stats[pair_key] = {"total": 0, "wins": 0, "losses": 0}
            pair_stats[pair_key]["total"] += 1
            if is_win:
                pair_stats[pair_key]["wins"] += 1
            else:
                pair_stats[pair_key]["losses"] += 1

            # Root cause trong notes (nếu có)
            notes_raw = row.get("notes")
            if notes_raw:
                try:
                    notes_dict = json.loads(notes_raw) if isinstance(notes_raw, str) else notes_raw
                    rc = notes_dict.get("root_cause")
                    if rc:
                        root_causes[rc] = root_causes.get(rc, 0) + 1
                except Exception:
                    pass

        # Tính win rate
        for st, data in setup_stats.items():
            tot = data["total"]
            data["win_rate"] = round(data["wins"] / tot * 100.0, 1) if tot > 0 else 0.0

        pair_summary: dict[str, dict] = {}
        for (st, regime), data in pair_stats.items():
            tot = data["total"]
            wr = round(data["wins"] / tot * 100.0, 1) if tot > 0 else 0.0
            pair_summary[f"{st}::{regime}"] = {
                "setup_type": st,
                "regime": regime,
                "total": tot,
                "wins": data["wins"],
                "losses": data["losses"],
                "win_rate": wr,
            }

        # Đánh giá tỷ lệ SL do giãn spread
        total_sl = sum(v for k, v in root_causes.items() if "SPREAD" in k or "SPIKE" in k or "LOSS" in k)
        spread_sl_count = root_causes.get(RootCause.SPREAD_WIDENING.value, 0)
        spread_ratio = (spread_sl_count / total_sl) if total_sl > 0 else 0.0

        cushion_multiplier = 1.15 if spread_ratio >= 0.25 else 1.0

        self.cached_stats = {
            "total_outcomes": len(outcomes),
            "setup_stats": setup_stats,
            "pair_stats": pair_summary,
            "root_causes": root_causes,
            "recommended_cushion_multiplier": cushion_multiplier,
            "spread_sl_ratio": round(spread_ratio * 100.0, 1),
        }
        self.last_refresh = datetime.now(timezone.utc)
        return self.cached_stats

    def get_feedback_adjustment(
        self,
        setup_type: str,
        regime: str = "UNKNOWN",
    ) -> dict[str, Any]:
        """
        Tính toán điểm phạt/thưởng tự học dựa trên lịch sử thực chiến của setup trong regime tương ứng.

        Returns:
            {
                "score_adjustment": float,    # Điểm cộng/trừ (-20 đến +5)
                "cushion_multiplier": float,  # Hệ số nới rộng khoảng đệm SL
                "reason": str,                # Lý do điều chỉnh
            }
        """
        if not self.cached_stats:
            self.refresh()

        pair_key = f"{setup_type}::{regime}"
        pair_data = self.cached_stats.get("pair_stats", {}).get(pair_key)
        setup_data = self.cached_stats.get("setup_stats", {}).get(setup_type)
        cushion_mult = self.cached_stats.get("recommended_cushion_multiplier", 1.0)

        # 1. Đánh giá ưu tiên cặp (Setup, Regime) nếu đủ mẫu
        if pair_data and pair_data["total"] >= self.min_samples:
            wr = pair_data["win_rate"]
            tot = pair_data["total"]
            if wr < 20.0:
                return {
                    "score_adjustment": -20.0,
                    "cushion_multiplier": cushion_mult,
                    "reason": f"Self-Learning: Phạt nặng -20 điểm ({setup_type} trong {regime} có WR chỉ {wr:.1f}% qua {tot} lệnh)",
                }
            if wr < 35.0:
                return {
                    "score_adjustment": -10.0,
                    "cushion_multiplier": cushion_mult,
                    "reason": f"Self-Learning: Phạt -10 điểm ({setup_type} trong {regime} hiệu suất thấp {wr:.1f}%)",
                }
            if wr >= 65.0:
                return {
                    "score_adjustment": 5.0,
                    "cushion_multiplier": cushion_mult,
                    "reason": f"Self-Learning: Thưởng +5 điểm ({setup_type} trong {regime} hoạt động xuất sắc {wr:.1f}%)",
                }

        # 2. Đánh giá tổng thể setup nếu chưa đủ mẫu theo regime
        if setup_data and setup_data["total"] >= self.min_samples:
            wr = setup_data["win_rate"]
            if wr < 30.0:
                return {
                    "score_adjustment": -10.0,
                    "cushion_multiplier": cushion_mult,
                    "reason": f"Self-Learning: Phạt -10 điểm ({setup_type} tổng thể có WR kém {wr:.1f}%)",
                }
            if wr >= 65.0:
                return {
                    "score_adjustment": 5.0,
                    "cushion_multiplier": cushion_mult,
                    "reason": f"Self-Learning: Thưởng +5 điểm ({setup_type} tổng thể có WR cao {wr:.1f}%)",
                }

        return {
            "score_adjustment": 0.0,
            "cushion_multiplier": cushion_mult,
            "reason": "Self-Learning: Chưa đủ mẫu hoặc hiệu suất trong ngưỡng trung tính",
        }

    def get_diagnostic_report(self) -> dict[str, Any]:
        """Báo cáo chuẩn đoán tự học cho Dashboard."""
        if not self.cached_stats:
            self.refresh()
        return self.cached_stats
