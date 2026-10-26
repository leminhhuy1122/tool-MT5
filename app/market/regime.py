# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Market Regime Detector.

Module phân loại trạng thái thị trường (Market Regime):
1. TRENDING_BULLISH: Xu hướng tăng mạnh (ADX cao, +DI > -DI, EMA20 > EMA50 > EMA200).
2. TRENDING_BEARISH: Xu hướng giảm mạnh (ADX cao, -DI > +DI, EMA20 < EMA50 < EMA200).
3. RANGING: Thị trường đi ngang / tích lũy (ADX thấp, EMA đan xen, giá dao động biên độ hẹp).
4. HIGH_VOLATILITY_EXPANSION: Biến động giãn nở cực mạnh / tin tức (ATR percentile cao, BB mở rộng).
5. COMPRESSION_SQUEEZE: Thị trường nén biên độ (Bollinger Bands nằm trong Keltner Channel, BB width thấp).

Tác vụ định lượng:
- Gán trọng số thích ứng theo từng Regime.
- Xác định danh sách setup được phép vào (Allowed Setups).
- Điều chỉnh cushion đệm giá và ngưỡng điểm Confluence tối thiểu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.market.indicators import (
    add_adx,
    add_all_indicators,
    add_bollinger_bands,
    calc_adx,
    calc_atr,
    calc_bollinger_bands,
    calc_keltner_channels,
)
from logger import get_logger

if TYPE_CHECKING:
    from app.strategy.setup_detector import SetupType

log = get_logger("market.regime")


class MarketRegime(Enum):
    """Trạng thái chế độ thị trường."""
    TRENDING_BULLISH = "TRENDING_BULLISH"                     # Xu hướng tăng mạnh
    TRENDING_BEARISH = "TRENDING_BEARISH"                     # Xu hướng giảm mạnh
    RANGING = "RANGING"                                       # Đi ngang / Tích lũy
    HIGH_VOLATILITY_EXPANSION = "HIGH_VOLATILITY_EXPANSION"   # Giãn nở biến động mạnh
    COMPRESSION_SQUEEZE = "COMPRESSION_SQUEEZE"               # Nén biên độ (Chuẩn bị bùng nổ)


class RegimeBias(Enum):
    """Thiên kiến hướng thị trường."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class VolatilityState(Enum):
    """Mức độ biến động."""
    COMPRESSED = "COMPRESSED"  # Nén chặt
    NORMAL = "NORMAL"          # Bình thường
    EXPANDED = "EXPANDED"      # Giãn nở
    EXTREME = "EXTREME"        # Cực đại


@dataclass
class RegimeMetrics:
    """Các chỉ số định lượng đo lường Regime."""
    adx: float
    plus_di: float
    minus_di: float
    atr_value: float
    atr_percentile: float
    bb_width: float
    bb_width_percentile: float
    is_squeeze: bool
    ema_alignment: str          # "BULLISH", "BEARISH", "FLAT", "MIXED"
    ema_slope_20: float


@dataclass
class MarketRegimeResult:
    """Kết quả phân loại chế độ thị trường đầy đủ."""
    regime: MarketRegime
    confidence: float
    bias: RegimeBias
    metrics: RegimeMetrics
    h4_regime: Optional[MarketRegime] = None
    allowed_setups: list[Any] = field(default_factory=list)
    cushion_multiplier: float = 1.0
    min_confluence_score: float = 65.0
    reasons: list[str] = field(default_factory=list)

    def is_setup_allowed(self, setup_type: Any) -> bool:
        """Kiểm tra setup có phù hợp với chế độ thị trường hiện tại không."""
        if not self.allowed_setups:
            return True
        setup_val = getattr(setup_type, "value", str(setup_type))
        allowed_vals = {getattr(s, "value", str(s)) for s in self.allowed_setups}
        return setup_val in allowed_vals

    def get_score_adjustment(self, setup_type: Any) -> float:
        """Tính điểm cộng/trừ thích ứng theo Regime."""
        setup_val = getattr(setup_type, "value", str(setup_type))

        # Thị trường có xu hướng: Ưu tiên tiếp diễn xu hướng
        if self.regime in (MarketRegime.TRENDING_BULLISH, MarketRegime.TRENDING_BEARISH):
            if setup_val in ("TREND_CONTINUATION", "BOS_RETEST", "EMA_BOUNCE"):
                return +10.0
            elif setup_val == "RSI_DIVERGENCE":
                return -15.0  # Phạt nặng bắt đỉnh đáy ngược xu hướng mạnh

        # Thị trường đi ngang: Ưu tiên bẫy quét thanh khoản và Order Block
        elif self.regime == MarketRegime.RANGING:
            if setup_val in ("SMC_LIQUIDITY_SWEEP", "SMC_ORDER_BLOCK", "SMC_FVG_RETEST"):
                return +10.0
            elif setup_val == "TREND_CONTINUATION":
                return -15.0  # Phạt tiếp diễn xu hướng khi thị trường đang sideway

        # Thị trường nén biên độ: Ưu tiên chuẩn bị Limit Breakout
        elif self.regime == MarketRegime.COMPRESSION_SQUEEZE:
            if setup_val == "PREDICTIVE_LIMIT":
                return +15.0

        return 0.0


class MarketRegimeDetector:
    """
    Bộ phân loại trạng thái thị trường dựa trên định lượng đa khung thời gian.
    """

    def __init__(
        self,
        adx_period: int = 14,
        adx_trend_threshold: float = 22.0,
        lookback_percentile: int = 50,
        volatility_expansion_percentile: float = 80.0,
        squeeze_bb_percentile: float = 25.0,
    ):
        self.adx_period = adx_period
        self.adx_trend_threshold = adx_trend_threshold
        self.lookback_percentile = lookback_percentile
        self.volatility_expansion_percentile = volatility_expansion_percentile
        self.squeeze_bb_percentile = squeeze_bb_percentile

    def _calc_percentile(self, series: pd.Series, current_val: float, lookback: int = 50) -> float:
        """Tính bách phân vị (percentile 0 - 100%) của giá trị hiện tại so với lịch sử."""
        window = series.dropna().iloc[-lookback:] if len(series.dropna()) >= lookback else series.dropna()
        if len(window) < 5:
            return 50.0
        return float((window < current_val).mean() * 100.0)

    def _detect_single_tf(self, df: pd.DataFrame) -> Tuple[MarketRegime, float, RegimeBias, RegimeMetrics, list[str]]:
        """Phân tích và phân loại chế độ thị trường trên 1 khung thời gian."""
        reasons: list[str] = []

        # 1. Tính toán hoặc lấy các indicators cần thiết
        working_df = df.copy()
        if f"adx_{self.adx_period}" not in working_df.columns:
            adx_s, p_di_s, m_di_s = calc_adx(working_df, period=self.adx_period)
            working_df[f"adx_{self.adx_period}"] = adx_s
            working_df[f"plus_di_{self.adx_period}"] = p_di_s
            working_df[f"minus_di_{self.adx_period}"] = m_di_s
        else:
            adx_s = working_df[f"adx_{self.adx_period}"]
            p_di_s = working_df[f"plus_di_{self.adx_period}"]
            m_di_s = working_df[f"minus_di_{self.adx_period}"]

        if "bb_width" not in working_df.columns:
            _, _, _, bb_width_s = calc_bollinger_bands(working_df, period=20, std_dev=2.0)
            working_df["bb_width"] = bb_width_s
        else:
            bb_width_s = working_df["bb_width"]

        if "atr_14" not in working_df.columns:
            atr_s = calc_atr(working_df, period=14)
            working_df["atr_14"] = atr_s
        else:
            atr_s = working_df["atr_14"]

        # Keltner Channels để xác định Squeeze (BB co gọn nằm trọn trong Keltner)
        bb_upper, _, bb_lower, _ = calc_bollinger_bands(working_df, period=20, std_dev=2.0)
        kc_upper, _, kc_lower = calc_keltner_channels(working_df, ema_period=20, atr_period=10, multiplier=1.5)

        last_candle = working_df.iloc[-1]
        close = float(last_candle["close"])
        adx_val = float(last_candle.get(f"adx_{self.adx_period}", 0.0))
        if pd.isna(adx_val):
            adx_val = 15.0

        plus_di_val = float(last_candle.get(f"plus_di_{self.adx_period}", 0.0))
        minus_di_val = float(last_candle.get(f"minus_di_{self.adx_period}", 0.0))
        atr_val = float(last_candle.get("atr_14", 1.0))
        bb_width_val = float(last_candle.get("bb_width", 1.0))

        # Tính bách phân vị và tỷ lệ giãn nở ATR
        atr_pct = self._calc_percentile(atr_s, atr_val, self.lookback_percentile)
        bb_width_pct = self._calc_percentile(bb_width_s, bb_width_val, self.lookback_percentile)

        window_atr = atr_s.dropna().iloc[-self.lookback_percentile:] if len(atr_s.dropna()) >= self.lookback_percentile else atr_s.dropna()
        avg_atr = float(window_atr.mean()) if len(window_atr) > 0 else atr_val
        atr_ratio = atr_val / avg_atr if avg_atr > 0 else 1.0

        # Squeeze khi BB co hẹp nằm trọn trong Keltner HOẶC độ rộng dải ở mức đáy
        is_squeeze = bool(
            (not pd.isna(bb_lower.iloc[-1]) and not pd.isna(kc_lower.iloc[-1]) and
             (bb_lower.iloc[-1] > kc_lower.iloc[-1]) and (bb_upper.iloc[-1] < kc_upper.iloc[-1]))
            or (bb_width_pct <= self.squeeze_bb_percentile and atr_pct <= 35.0)
        )

        # Đánh giá cấu trúc EMA
        ema_20 = float(last_candle.get("ema_20", close))
        ema_50 = float(last_candle.get("ema_50", close))
        ema_200 = float(last_candle.get("ema_200", close))

        # Độ dốc EMA20 (so với 3 nến trước)
        prev_ema_20 = float(working_df["ema_20"].iloc[-4]) if len(working_df) >= 4 and "ema_20" in working_df.columns else ema_20
        ema_slope_20 = ema_20 - prev_ema_20

        # Kiểm tra sắp xếp EMA
        if ema_20 > ema_50 > ema_200 and close > ema_20:
            ema_alignment = "BULLISH"
        elif ema_20 < ema_50 < ema_200 and close < ema_20:
            ema_alignment = "BEARISH"
        elif abs(ema_20 - ema_50) < (atr_val * 0.2):
            ema_alignment = "FLAT"
        else:
            ema_alignment = "MIXED"

        metrics = RegimeMetrics(
            adx=round(adx_val, 1),
            plus_di=round(plus_di_val, 1),
            minus_di=round(minus_di_val, 1),
            atr_value=round(atr_val, 2),
            atr_percentile=round(atr_pct, 1),
            bb_width=round(bb_width_val, 2),
            bb_width_percentile=round(bb_width_pct, 1),
            is_squeeze=is_squeeze,
            ema_alignment=ema_alignment,
            ema_slope_20=round(ema_slope_20, 2),
        )

        # ── THUẬT TOÁN PHÂN LOẠI CHẾ ĐỘ THỊ TRƯỜNG ──

        # Ưu tiên 1: Biến động giãn nở cực mạnh (High Volatility Expansion)
        # Phải có ATR ratio >= 1.6 VÀ (ATR percentile >= 85% hoặc BB Width percentile >= 85%)
        is_vol_expansion = (atr_ratio >= 1.6 and (atr_pct >= 85.0 or bb_width_pct >= 85.0))
        if is_vol_expansion:
            regime = MarketRegime.HIGH_VOLATILITY_EXPANSION
            confidence = min(0.95, (atr_pct / 100.0))
            bias = RegimeBias.BULLISH if close > ema_20 else (RegimeBias.BEARISH if close < ema_20 else RegimeBias.NEUTRAL)
            reasons.append(f"Biến động giãn nở mạnh: ATR gấp {atr_ratio:.2f}x trung bình, đạt bách phân vị {atr_pct:.1f}%")
            if bb_width_pct >= 85.0:
                reasons.append(f"Bollinger Band Width mở rộng cực đại ({bb_width_pct:.1f}%)")
            return regime, confidence, bias, metrics, reasons

        # Ưu tiên 2: Nén biên độ (Compression Squeeze)
        # Bollinger Bands nằm trọn trong Keltner Channel HOẶC BB Width percentile <= 25%
        if is_squeeze:
            regime = MarketRegime.COMPRESSION_SQUEEZE
            confidence = 0.85
            bias = RegimeBias.NEUTRAL
            reasons.append("Thị trường nén biên độ (Squeeze): BB co hẹp bên trong Keltner Channel")
            reasons.append(f"Độ rộng dải BB ở mức đáy {bb_width_pct:.1f}%")
            return regime, confidence, bias, metrics, reasons

        # Ưu tiên 3: Xu hướng rõ rệt (Trending Bullish / Bearish)
        # ADX >= threshold VÀ có sự đồng thuận giữa DI và EMA
        is_trending_adx = adx_val >= self.adx_trend_threshold
        if is_trending_adx or (adx_val >= 18.0 and ema_alignment in ("BULLISH", "BEARISH")):
            if plus_di_val > minus_di_val and (ema_alignment == "BULLISH" or close >= ema_50):
                regime = MarketRegime.TRENDING_BULLISH
                confidence = min(0.95, 0.65 + (adx_val / 100.0))
                bias = RegimeBias.BULLISH
                reasons.append(f"Xu hướng tăng mạnh: ADX={adx_val:.1f} >= {self.adx_trend_threshold}, +DI ({plus_di_val:.1f}) > -DI ({minus_di_val:.1f})")
                reasons.append(f"Cấu trúc EMA {ema_alignment}, giá nằm trên EMA50")
                return regime, confidence, bias, metrics, reasons

            elif minus_di_val > plus_di_val and (ema_alignment == "BEARISH" or close <= ema_50):
                regime = MarketRegime.TRENDING_BEARISH
                confidence = min(0.95, 0.65 + (adx_val / 100.0))
                bias = RegimeBias.BEARISH
                reasons.append(f"Xu hướng giảm mạnh: ADX={adx_val:.1f} >= {self.adx_trend_threshold}, -DI ({minus_di_val:.1f}) > +DI ({plus_di_val:.1f})")
                reasons.append(f"Cấu trúc EMA {ema_alignment}, giá nằm dưới EMA50")
                return regime, confidence, bias, metrics, reasons

        # Ưu tiên 4: Mặc định là Đi ngang / Tích lũy (Ranging)
        regime = MarketRegime.RANGING
        confidence = 0.80 if adx_val < 20.0 else 0.65
        bias = RegimeBias.NEUTRAL
        reasons.append(f"Thị trường tích lũy / đi ngang (Ranging): ADX={adx_val:.1f} thấp (<{self.adx_trend_threshold})")
        reasons.append(f"EMA ở trạng thái {ema_alignment}, giá dao động quanh trung bình")
        return regime, confidence, bias, metrics, reasons

    def detect_regime(
        self,
        df: pd.DataFrame,
        h4_df: Optional[pd.DataFrame] = None,
    ) -> MarketRegimeResult:
        """
        Phân tích và tổng hợp chế độ thị trường đa khung thời gian.

        Args:
            df: DataFrame khung thời gian thực thi (vd H1).
            h4_df: DataFrame khung lớn H4 (tùy chọn).

        Returns:
            MarketRegimeResult chứa đầy đủ thông tin regime và các quy tắc tương thích.
        """
        if df is None or len(df) < 20:
            default_metrics = RegimeMetrics(
                adx=15.0, plus_di=20.0, minus_di=20.0, atr_value=1.0,
                atr_percentile=50.0, bb_width=1.0, bb_width_percentile=50.0,
                is_squeeze=False, ema_alignment="FLAT", ema_slope_20=0.0,
            )
            return MarketRegimeResult(
                regime=MarketRegime.RANGING,
                confidence=0.5,
                bias=RegimeBias.NEUTRAL,
                metrics=default_metrics,
                reasons=["Dữ liệu không đủ để phân loại chế độ thị trường (mặc định RANGING)"],
            )

        # 1. Phân loại khung chính (H1)
        h1_regime, confidence, bias, metrics, reasons = self._detect_single_tf(df)

        # 2. Phân loại khung lớn (H4) nếu có
        h4_regime: Optional[MarketRegime] = None
        if h4_df is not None and len(h4_df) >= 20:
            h4_regime, _, h4_bias, _, h4_reasons = self._detect_single_tf(h4_df)
            reasons.append(f"Khung lớn H4: {h4_regime.value} ({h4_bias.value})")

            # Đồng thuận đa khung thời gian làm tăng độ tin cậy
            if h1_regime == h4_regime:
                confidence = min(0.98, confidence + 0.10)
                reasons.append("✓ Đồng thuận đa khung thời gian H4 và H1 (High Confidence)")
            elif h1_regime == MarketRegime.COMPRESSION_SQUEEZE and h4_regime in (MarketRegime.TRENDING_BULLISH, MarketRegime.TRENDING_BEARISH):
                reasons.append(f"✓ H1 Squeeze nằm trong xu hướng lớn H4 {h4_regime.value} -> Tiềm năng bùng nổ xu hướng")

        # 3. Xác định danh sách Setup được phép và thông số quản lý vốn theo Regime
        from app.strategy.setup_detector import SetupType

        allowed_setups: list[SetupType] = []
        cushion_multiplier = 1.0
        min_confluence_score = 65.0

        if h1_regime == MarketRegime.TRENDING_BULLISH:
            allowed_setups = [
                SetupType.TREND_CONTINUATION,
                SetupType.BOS_RETEST,
                SetupType.EMA_BOUNCE,
                SetupType.SMC_ORDER_BLOCK,
                SetupType.PREDICTIVE_LIMIT,
            ]
            cushion_multiplier = 1.0
            min_confluence_score = 65.0

        elif h1_regime == MarketRegime.TRENDING_BEARISH:
            allowed_setups = [
                SetupType.TREND_CONTINUATION,
                SetupType.BOS_RETEST,
                SetupType.EMA_BOUNCE,
                SetupType.SMC_ORDER_BLOCK,
                SetupType.PREDICTIVE_LIMIT,
            ]
            cushion_multiplier = 1.0
            min_confluence_score = 65.0

        elif h1_regime == MarketRegime.RANGING:
            allowed_setups = [
                SetupType.SMC_LIQUIDITY_SWEEP,
                SetupType.SMC_ORDER_BLOCK,
                SetupType.SMC_FVG_RETEST,
                SetupType.RSI_DIVERGENCE,
                SetupType.PREDICTIVE_LIMIT,
            ]
            cushion_multiplier = 1.1
            min_confluence_score = 70.0

        elif h1_regime == MarketRegime.HIGH_VOLATILITY_EXPANSION:
            # Khi biến động cực mạnh: Chỉ cho phép các setup có cản SMC vững chắc và tăng đệm Cushion
            allowed_setups = [
                SetupType.SMC_LIQUIDITY_SWEEP,
                SetupType.SMC_ORDER_BLOCK,
                SetupType.BOS_RETEST,
            ]
            cushion_multiplier = 1.5
            min_confluence_score = 75.0  # Đòi hỏi độ hội tụ cao hơn để tránh false breakout

        elif h1_regime == MarketRegime.COMPRESSION_SQUEEZE:
            # Khi nén biên độ: Ưu tiên Limit đón sóng bứt phá và săn thanh khoản
            allowed_setups = [
                SetupType.PREDICTIVE_LIMIT,
                SetupType.SMC_LIQUIDITY_SWEEP,
                SetupType.SMC_ORDER_BLOCK,
                SetupType.SMC_FVG_RETEST,
            ]
            cushion_multiplier = 0.8
            min_confluence_score = 68.0

        return MarketRegimeResult(
            regime=h1_regime,
            confidence=round(confidence, 2),
            bias=bias,
            metrics=metrics,
            h4_regime=h4_regime,
            allowed_setups=allowed_setups,
            cushion_multiplier=cushion_multiplier,
            min_confluence_score=min_confluence_score,
            reasons=reasons,
        )
