# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Signal Filter.

Bộ lọc và tinh chỉnh tín hiệu giao dịch dựa trên Machine Learning:
- Nếu mô hình ML dự đoán xác suất thành công cao (confidence >= 0.60): Tăng điểm Confluence Score.
- Nếu mô hình ML dự đoán xác suất thành công thấp (confidence < 0.35): Chuyển trạng thái sang WAIT để bảo toàn vốn.
- Tự động Fallback: Nếu chưa có mô hình ML trong production, hệ thống rule-based tiếp tục hoạt động 100% bình thường.
"""

from typing import Optional
import pandas as pd

from app.ml.features import FeatureExtractor
from app.ml.model import SignalQualityClassifier
from app.strategy.signal_models import SignalDirection, TradingSignal
from logger import get_logger

log = get_logger("ml.filter")


class MLSignalFilter:
    """Bộ lọc thông minh hỗ trợ Signal Engine bằng Machine Learning."""

    def __init__(
        self,
        classifier: Optional[SignalQualityClassifier] = None,
        min_confidence_to_pass: float = 0.35,
        high_confidence_threshold: float = 0.60,
    ):
        self.classifier = classifier
        self.min_confidence = min_confidence_to_pass
        self.high_confidence = high_confidence_threshold

    @property
    def is_active(self) -> bool:
        """Kiểm tra mô hình ML đã sẵn sàng hoạt động hay chưa."""
        return self.classifier is not None and getattr(self.classifier, "is_trained", False)

    def apply(
        self,
        signal: TradingSignal,
        df_exec: Optional[pd.DataFrame] = None,
        spread: float = 0.3,
        df: Optional[pd.DataFrame] = None,
    ) -> TradingSignal:
        """
        Áp dụng bộ lọc ML lên tín hiệu giao dịch candidate.
        """
        target_df = df_exec if df_exec is not None else df
        if target_df is None:
            return signal

        # Nếu là WAIT hoặc mô hình ML chưa được tải -> giữ nguyên tín hiệu rule-based
        if signal.direction == SignalDirection.WAIT or not self.is_active or self.classifier is None:
            return signal

        regime_val = signal.market_regime if signal.market_regime != "UNKNOWN" else None
        session_val = None
        volume_surge_val = None
        setup_hist_wr_val = None
        if signal.score_breakdown:
            session_val = signal.score_breakdown.get("session_name")
            volume_surge_val = signal.score_breakdown.get("volume_surge")
            setup_hist_wr_val = signal.score_breakdown.get("setup_historical_wr")

        features = FeatureExtractor.extract_features(
            df_exec=target_df,
            candle_idx=-1,
            spread=spread,
            h4_trend=signal.trend_h4,
            h1_trend=signal.trend_h1,
            swing_high=signal.entry_zone_high + 5.0,
            swing_low=signal.entry_zone_low - 5.0,
            regime=regime_val,
            session_name=session_val,
            volume_surge=volume_surge_val,
            risk_reward=signal.risk_reward_ratio,
            setup_historical_wr=setup_hist_wr_val,
        )

        confidence = self.classifier.predict_confidence(features)
        log.info(
            "ML Filter đánh giá tín hiệu [%s]: Confidence = %.1f%%",
            signal.signal_id, confidence * 100,
        )

        # 1. Nếu xác suất thắng quá thấp -> Lọc bỏ (chuyển sang WAIT)
        if confidence < self.min_confidence:
            log.warning(
                "Tín hiệu [%s] bị ML Filter từ chối (Confidence: %.1f%% < %.1f%%)",
                signal.signal_id, confidence * 100, self.min_confidence * 100,
            )
            score_breakdown = dict(signal.score_breakdown) if signal.score_breakdown else {}
            score_breakdown["ml_confidence"] = round(confidence, 3)
            score_breakdown["ml_rejected"] = True

            structure_context = dict(signal.structure_context) if signal.structure_context else {}
            structure_context["ml_confidence"] = round(confidence, 3)
            structure_context["ml_rejected"] = True

            return TradingSignal(
                signal_id=signal.signal_id,
                strategy_version=f"{signal.strategy_version}+ML",
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=SignalDirection.WAIT,
                entry_price=0.0,
                entry_zone_low=0.0,
                entry_zone_high=0.0,
                stop_loss=0.0,
                take_profit_1=0.0,
                take_profit_2=0.0,
                risk_reward_ratio=0.0,
                sl_distance=0.0,
                tp_distance=0.0,
                score=round(signal.score * confidence, 1),
                confidence="LOW",
                reasons=[f"ML Filter lọc bỏ: Xác suất thắng dự báo thấp ({confidence*100:.1f}%)"],
                invalidation="Chờ setup mới có xác suất cao hơn",
                trend_h4=signal.trend_h4,
                trend_h1=signal.trend_h1,
                created_at=signal.created_at,
                setup_id=signal.setup_id,
                setup_type=signal.setup_type,
                market_regime=signal.market_regime,
                lifecycle_status=signal.lifecycle_status,
                invalidation_level=signal.invalidation_level,
                structure_context=structure_context,
                score_breakdown=score_breakdown,
            )

        # 2. Nếu xác suất thắng cao -> Thưởng thêm điểm Score và ghi chú
        new_score = signal.score
        reasons = list(signal.reasons)
        if confidence >= self.high_confidence:
            bonus = int((confidence - self.high_confidence) * 25.0)
            new_score = min(99.0, signal.score + bonus)
            reasons.append(f"ML Confirmation: Xác suất thắng cao ({confidence*100:.1f}%)")

        conf_str = "HIGH" if confidence >= 0.70 else ("MEDIUM" if confidence >= 0.50 else "LOW")

        score_breakdown = dict(signal.score_breakdown) if signal.score_breakdown else {}
        score_breakdown["ml_confidence"] = round(confidence, 3)
        score_breakdown["ml_approved"] = True

        structure_context = dict(signal.structure_context) if signal.structure_context else {}
        structure_context["ml_confidence"] = round(confidence, 3)
        structure_context["ml_approved"] = True

        return TradingSignal(
            signal_id=signal.signal_id,
            strategy_version=f"{signal.strategy_version}+ML",
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction,
            status=signal.status,
            entry_price=signal.entry_price,
            entry_zone_low=signal.entry_zone_low,
            entry_zone_high=signal.entry_zone_high,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            risk_reward_ratio=signal.risk_reward_ratio,
            sl_distance=signal.sl_distance,
            tp_distance=signal.tp_distance,
            score=new_score,
            confidence=conf_str,
            reasons=reasons,
            setup_type=signal.setup_type,
            invalidation=signal.invalidation,
            trend_h4=signal.trend_h4,
            trend_h1=signal.trend_h1,
            created_at=signal.created_at,
            expires_at=signal.expires_at,
            setup_id=signal.setup_id,
            market_regime=signal.market_regime,
            lifecycle_status=signal.lifecycle_status,
            invalidation_level=signal.invalidation_level,
            structure_context=structure_context,
            score_breakdown=score_breakdown,
        )
