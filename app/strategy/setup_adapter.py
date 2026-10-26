# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Setup Adaptation Engine (Phase 9).

Định nghĩa đặc tả chuẩn hóa (SetupSpecification) và cơ chế thích ứng (SetupAdapterEngine)
cho tất cả các setup giao dịch:
1. Order Block Retest (SMC)
2. Liquidity Sweep (SMC)
3. FVG Retest (SMC)
4. EMA Bounce (Trend Continuation)
5. Predictive Limit (Advanced SMC Limit Setup)
6. Reversal (RSI Extreme + Support/Resistance)
7. Trend Continuation / BOS Retest

Mỗi setup sở hữu đặc tả đầy đủ:
- Definition & Entry condition
- Confirmation rules & Invalidation rules
- Expiry timeline (theo số nến)
- Stop methodology & Target methodology
- Market Regime tương thích và cấm kỵ (Applicable Market Regimes)
- Ngưỡng tối thiểu ADX và ngưỡng tối đa ATR Ratio để tránh bẫy whipsaw
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import pandas as pd

from app.market.regime import MarketRegime, MarketRegimeResult
from app.strategy.setup_detector import SetupCandidate, SetupType
from logger import get_logger

log = get_logger("strategy.setup_adapter")


@dataclass
class SetupSpecification:
    """Đặc tả kỹ thuật chuẩn hóa cho một setup giao dịch."""
    setup_type: SetupType
    name: str
    definition: str
    entry_condition: str
    confirmation_rules: str
    invalidation_rules: str
    expiry_bars: int
    stop_methodology: str
    target_methodology: str
    compatible_regimes: list[MarketRegime]
    incompatible_regimes: list[MarketRegime]
    min_adx: float = 0.0
    max_atr_ratio: float = 999.0
    min_rr: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Chuyển đổi thành từ điển phục vụ API và kiểm toán."""
        return {
            "setup_type": self.setup_type.value,
            "name": self.name,
            "definition": self.definition,
            "entry_condition": self.entry_condition,
            "confirmation_rules": self.confirmation_rules,
            "invalidation_rules": self.invalidation_rules,
            "expiry_bars": self.expiry_bars,
            "stop_methodology": self.stop_methodology,
            "target_methodology": self.target_methodology,
            "compatible_regimes": [r.value for r in self.compatible_regimes],
            "incompatible_regimes": [r.value for r in self.incompatible_regimes],
            "min_adx": self.min_adx,
            "max_atr_ratio": self.max_atr_ratio,
            "min_rr": self.min_rr,
        }


# ─────────────────────────────────────────────────────────────────────────────
# TẬP HỢP ĐẶC TẢ CHUẨN CHO 7 SETUP CỐT LÕI
# ─────────────────────────────────────────────────────────────────────────────
SETUP_SPECIFICATIONS: dict[SetupType, SetupSpecification] = {
    SetupType.SMC_ORDER_BLOCK: SetupSpecification(
        setup_type=SetupType.SMC_ORDER_BLOCK,
        name="SMC Order Block Retest",
        definition="Vùng nến tổ chức bảo vệ vị thế trước con sóng phá vỡ cấu trúc (BOS) hoặc mở rộng Imbalance.",
        entry_condition="Giá pullback chạm vào vùng thân hoặc 50% khối Order Block hợp lệ chưa bị khai thác (Unmitigated).",
        confirmation_rules="Nến phản ứng rút râu từ chối (wick rejection) và đóng cửa giữ vững bên trong/bên trên vùng OB.",
        invalidation_rules="Giá đóng cửa (Close) xuyên thủng hoàn toàn đáy OB (BUY) hoặc vượt hoàn toàn đỉnh OB (SELL).",
        expiry_bars=30,
        stop_methodology="Đặt ngoài biên đối diện của OB + 1.0 giá đệm, khống chế trong dải chuẩn Vàng 10.0 - 12.0 giá.",
        target_methodology="TP1 = 1.0x SL (10-12 giá) để khóa 50% vốn và dời SL hòa vốn; TP2 = 2.0x SL (20-24 giá).",
        compatible_regimes=[
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
            MarketRegime.RANGING,
            MarketRegime.COMPRESSION_SQUEEZE,
        ],
        incompatible_regimes=[],
        min_adx=0.0,
        max_atr_ratio=2.5,
    ),

    SetupType.SMC_LIQUIDITY_SWEEP: SetupSpecification(
        setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
        name="SMC Liquidity Sweep (Stop Hunt / Fakeout)",
        definition="Bẫy quét thanh khoản đỉnh/đáy then chốt (BSL/SSL) tạo phá vỡ giả rồi rút chân đảo chiều mạnh mẽ.",
        entry_condition="Nến đâm xuyên đỉnh/đáy swing then chốt với râu nến (wick) >= 0.6 giá rồi đóng nến thụt lùi lại bên trong.",
        confirmation_rules="Nến hiện tại hoặc nến trước đó có râu từ chối rõ rệt, thân nến đảo chiều về hướng ngược lại.",
        invalidation_rules="Giá đóng cửa vượt qua đỉnh cao nhất (SELL) hoặc thủng đáy thấp nhất (BUY) của râu quét thanh khoản.",
        expiry_bars=5,
        stop_methodology="Đặt ngoài đỉnh/đáy cực đại của râu nến quét + 1.0 giá đệm, khống chế 10.0 - 12.0 giá.",
        target_methodology="TP1 = 1.0x SL (10-12 giá) khóa lợi nhuận; TP2 = 2.0x SL (20-24 giá) hướng về vùng thanh khoản đối diện.",
        compatible_regimes=[
            MarketRegime.RANGING,
            MarketRegime.HIGH_VOLATILITY_EXPANSION,
            MarketRegime.COMPRESSION_SQUEEZE,
        ],
        incompatible_regimes=[],
        min_adx=0.0,
        max_atr_ratio=3.5,
    ),

    SetupType.SMC_FVG_RETEST: SetupSpecification(
        setup_type=SetupType.SMC_FVG_RETEST,
        name="SMC Fair Value Gap Retest",
        definition="Retest khoảng trống mất cân bằng giá (Imbalance 3 nến) tạo bởi áp lực mua/bán tổ chức.",
        entry_condition="Giá hồi quy retest vào vùng FVG chưa bị lấp (đặc biệt chạm mức cân bằng Consequent Encroachment 50%).",
        confirmation_rules="Nến chạm vùng FVG và có tín hiệu giảm tốc (nến thân nhỏ hoặc rút râu cùng chiều xu hướng).",
        invalidation_rules="Giá đóng cửa đâm xuyên quá 100% biên độ FVG, triệt tiêu hoàn toàn khoảng trống giá.",
        expiry_bars=25,
        stop_methodology="Đặt sau biên ngoài FVG + 1.0 giá đệm, chuẩn hóa 10.0 - 12.0 giá.",
        target_methodology="TP1 = 10-12 giá; TP2 = 20-24 giá mở rộng sóng đẩy theo xu hướng.",
        compatible_regimes=[
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
            MarketRegime.COMPRESSION_SQUEEZE,
        ],
        incompatible_regimes=[
            MarketRegime.HIGH_VOLATILITY_EXPANSION,  # Biến động cực đại dễ đâm thủng FVG tạo false signal
        ],
        min_adx=15.0,
        max_atr_ratio=2.0,
    ),

    SetupType.EMA_BOUNCE: SetupSpecification(
        setup_type=SetupType.EMA_BOUNCE,
        name="EMA Momentum Bounce",
        definition="Đón sóng hồi quy tiếp diễn xu hướng từ đường trung bình động động lượng EMA20 trong cấu trúc đồng thuận.",
        entry_condition="Xu hướng H4/H1 đồng thuận rõ ràng (EMA20 > EMA50 hoặc EMA20 < EMA50), giá pullback chạm hoặc rút chân tại EMA20.",
        confirmation_rules="Nến phản ứng bật nảy từ EMA20 và đóng nến giữ vững phía trên (BUY) hoặc phía dưới (SELL) EMA20, RSI nằm trong 35-65.",
        invalidation_rules="Giá đóng cửa vi phạm xuyên thủng qua đường EMA50.",
        expiry_bars=4,
        stop_methodology="Đặt ngoài đường EMA50 + 1.0 giá đệm, khống chế trong dải 10.0 - 12.0 giá.",
        target_methodology="TP1 = 10-12 giá (1.0x SL); TP2 = 20-24 giá tiếp diễn con sóng đẩy.",
        compatible_regimes=[
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
        ],
        incompatible_regimes=[
            MarketRegime.RANGING,                   # Nghiêm cấm trong Sideway do EMA liên tục cắt nhau tạo whipsaw
            MarketRegime.COMPRESSION_SQUEEZE,       # Nghiêm cấm trong nén biên độ vì EMA phẳng lì
            MarketRegime.HIGH_VOLATILITY_EXPANSION, # Rủi ro cao vì nến biến động lớn dễ đâm xuyên EMA
        ],
        min_adx=22.0,                               # Bắt buộc ADX >= 22 để chứng minh có trend đủ mạnh
        max_atr_ratio=1.8,
    ),

    SetupType.PREDICTIVE_LIMIT: SetupSpecification(
        setup_type=SetupType.PREDICTIVE_LIMIT,
        name="Predictive Limit Setup",
        definition="Kế hoạch đón trước từ xa (6.0 - 25.0 giá) tại các vùng cản then chốt SMC giúp Trader chủ động đặt lệnh Limit.",
        entry_condition="Phát hiện vùng Order Block chưa khai thác hoặc Strong S/R nằm cách giá hiện tại từ 6.0 đến 25.0 giá.",
        confirmation_rules="Khi giá tiến sát vùng entry (APPROACHING), cấu trúc vi mô không xuất hiện nến bùng nổ phá vỡ ngược chiều.",
        invalidation_rules="Giá phá vỡ cấu trúc cản trước khi đảo chiều, hoặc xuất hiện tin tức giật nến vượt quá mức invalidation level.",
        expiry_bars=48,                             # Hiệu lực dài hơn (2-4 giờ) cho kế hoạch đón đầu
        stop_methodology="Đặt ngoài biên cản + 1.0 giá đệm, khống chế 10.0 - 12.0 giá.",
        target_methodology="TP1 = 10-12 giá; TP2 = 20-24 giá đón trọn con sóng bật nảy từ cản.",
        compatible_regimes=[
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
            MarketRegime.RANGING,
            MarketRegime.COMPRESSION_SQUEEZE,
        ],
        incompatible_regimes=[
            MarketRegime.HIGH_VOLATILITY_EXPANSION,  # Không đặt Limit khi thị trường đang giãn nở biến động cực đại
        ],
        min_adx=0.0,
        max_atr_ratio=2.2,
    ),

    SetupType.RSI_DIVERGENCE: SetupSpecification(
        setup_type=SetupType.RSI_DIVERGENCE,
        name="Reversal (RSI Extreme + Support/Resistance)",
        definition="Bắt phản ứng đảo chiều khi động lượng rơi vào trạng thái quá bán cực đại (RSI < 30) hoặc quá mua cực đại (RSI > 70) tại cản.",
        entry_condition="RSI chạm vùng cực đại (<30 hoặc >70) đồng thời giá nằm sát mức Hỗ trợ hoặc Kháng cự quan trọng.",
        confirmation_rules="Xuất hiện mô hình nến đảo chiều (Pinbar rút chân hoặc Bullish/Bearish Engulfing) tại vùng cản.",
        invalidation_rules="RSI tiếp tục trôi sâu (< 20 hoặc > 80) và giá đóng cửa phá vỡ hoàn toàn mức cản.",
        expiry_bars=5,
        stop_methodology="Đặt ngoài vùng Hỗ trợ/Kháng cự + 1.0 giá đệm, chuẩn hóa 10.0 - 12.0 giá.",
        target_methodology="TP1 = 10-12 giá; TP2 = 20-24 giá nhắm vào vùng cân bằng RSI trung tính (RSI 50).",
        compatible_regimes=[
            MarketRegime.RANGING,
            MarketRegime.COMPRESSION_SQUEEZE,
        ],
        incompatible_regimes=[
            MarketRegime.HIGH_VOLATILITY_EXPANSION, # Dễ dính hiện tượng bắt dao rơi khi trend dốc đứng
        ],
        min_adx=0.0,
        max_atr_ratio=2.0,
    ),

    SetupType.BOS_RETEST: SetupSpecification(
        setup_type=SetupType.BOS_RETEST,
        name="Break of Structure Retest (Trend Continuation)",
        definition="Đón sóng tiếp diễn sau khi giá phá vỡ đỉnh/đáy cấu trúc (BOS) và quay trở lại kiểm tra vùng giá vừa phá.",
        entry_condition="Vừa xuất hiện BOS_BULLISH hoặc BOS_BEARISH, giá hồi quy về kiểm tra mức giá bị phá vỡ trong phạm vi ±0.3%.",
        confirmation_rules="Nến retest từ chối mức cản cũ và đóng cửa tiếp diễn theo hướng xu hướng chính.",
        invalidation_rules="Giá tái thâm nhập sâu vào vùng cấu trúc cũ và đóng cửa vi phạm mức Stop Loss.",
        expiry_bars=12,
        stop_methodology="Đặt dưới swing low gần nhất (BUY) hoặc trên swing high gần nhất (SELL) + 1.0 giá đệm, 10.0 - 12.0 giá.",
        target_methodology="TP1 = 10-12 giá; TP2 = 20-24 giá mở rộng con sóng đẩy.",
        compatible_regimes=[
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
        ],
        incompatible_regimes=[
            MarketRegime.RANGING,                   # Dễ dính False Breakout trong vùng đi ngang
        ],
        min_adx=18.0,
        max_atr_ratio=2.5,
    ),

    SetupType.TREND_CONTINUATION: SetupSpecification(
        setup_type=SetupType.TREND_CONTINUATION,
        name="General Trend Continuation",
        definition="Tiếp diễn xu hướng chính khi cấu trúc đa khung thời gian H4/H1 đồng thuận mạnh.",
        entry_condition="Cấu trúc đa khung thời gian xác nhận xu hướng rõ rệt và xuất hiện nhịp hồi quy đạt chuẩn.",
        confirmation_rules="Nến đóng cửa xác nhận đà tiếp diễn xu hướng.",
        invalidation_rules="Giá phá vỡ mức hỗ trợ/kháng cự cấu trúc gần nhất.",
        expiry_bars=10,
        stop_methodology="Đặt theo cấu trúc hỗ trợ/kháng cự + 1.0 giá đệm, 10.0 - 12.0 giá.",
        target_methodology="TP1 = 10-12 giá; TP2 = 20-24 giá.",
        compatible_regimes=[
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.TRENDING_BEARISH,
        ],
        incompatible_regimes=[
            MarketRegime.RANGING,
        ],
        min_adx=20.0,
        max_atr_ratio=2.2,
    ),
}


@dataclass
class SetupValidationResult:
    """Kết quả kiểm tra tính tương thích và thích ứng của setup candidate."""
    is_valid: bool
    setup_type: SetupType
    reasons: list[str] = field(default_factory=list)
    adapted_candidate: Optional[SetupCandidate] = None
    warning_messages: list[str] = field(default_factory=list)


class SetupAdapterEngine:
    """
    Động cơ thích ứng Setup theo Market Regime và vi cấu trúc nến.

    Nhiệm vụ:
    1. Kiểm tra tính tương thích của từng setup với Market Regime hiện tại.
    2. Kiểm tra các điều kiện định lượng bổ sung (ADX tối thiểu, độ giãn nở ATR).
    3. Thẩm định nến xác nhận (Confirmation Check).
    4. Tinh chỉnh SL/TP thích ứng (Cushion Adaptation) để hạn chế râu quét.
    """

    def __init__(self, specs: Optional[dict[SetupType, SetupSpecification]] = None):
        self.specs = specs or SETUP_SPECIFICATIONS

    def get_specification(self, setup_type: SetupType) -> Optional[SetupSpecification]:
        """Lấy đặc tả chuẩn của một loại setup."""
        return self.specs.get(setup_type)

    def get_all_specifications(self) -> dict[str, dict[str, Any]]:
        """Trả về toàn bộ đặc tả chuẩn hóa của 7 setup phục vụ API/Dashboard."""
        return {st.value: spec.to_dict() for st, spec in self.specs.items()}

    def validate_and_adapt(
        self,
        candidate: SetupCandidate,
        df: Optional[pd.DataFrame] = None,
        regime_result: Optional[MarketRegimeResult] = None,
    ) -> SetupValidationResult:
        """
        Kiểm tra tính hợp lệ và thích ứng hóa setup candidate theo bối cảnh thị trường.

        Args:
            candidate: SetupCandidate ban đầu từ SetupDetector.
            df: DataFrame nến hiện tại (tùy chọn để kiểm tra confirmation).
            regime_result: Kết quả phân loại Market Regime (tùy chọn).

        Returns:
            SetupValidationResult chứa trạng thái hợp lệ và candidate đã được thích ứng.
        """
        spec = self.get_specification(candidate.setup_type)
        if spec is None:
            # Setup không có đặc tả riêng -> Giữ nguyên mặc định
            return SetupValidationResult(
                is_valid=True,
                setup_type=candidate.setup_type,
                reasons=["Setup không thuộc 7 nhóm cần tinh chỉnh đặc biệt"],
                adapted_candidate=candidate,
            )

        rejection_reasons = []
        warnings = []

        # ── 1. Kiểm tra tính tương thích với Market Regime ──
        if regime_result is not None:
            current_regime = regime_result.regime
            metrics = regime_result.metrics

            # 1.1 Cấm kỵ tuyệt đối (Incompatible Regimes)
            if current_regime in spec.incompatible_regimes:
                rejection_reasons.append(
                    f"Setup [{spec.name}] bị CẤM trong chế độ thị trường [{current_regime.value}] "
                    f"để tránh thua lỗ lặp lại."
                )

            # 1.2 Kiểm tra ADX tối thiểu
            if spec.min_adx > 0 and metrics is not None:
                if metrics.adx < spec.min_adx:
                    rejection_reasons.append(
                        f"Setup [{spec.name}] đòi hỏi ADX >= {spec.min_adx:.1f} (Hiện tại: {metrics.adx:.1f}) "
                        f"để bảo đảm có xung lực xu hướng đủ mạnh."
                    )

            # 1.3 Kiểm tra độ giãn nở ATR
            if spec.max_atr_ratio < 999.0 and metrics is not None:
                # Tính atr_ratio nếu có dữ liệu nến
                if df is not None and len(df) >= 20 and "atr_14" in df.columns:
                    recent_atr = float(df["atr_14"].iloc[-1])
                    avg_atr = float(df["atr_14"].tail(20).mean())
                    atr_ratio = recent_atr / avg_atr if avg_atr > 0 else 1.0
                    if atr_ratio > spec.max_atr_ratio:
                        rejection_reasons.append(
                            f"Setup [{spec.name}] vượt ngưỡng giãn nở ATR an toàn "
                            f"(ATR ratio {atr_ratio:.2f}x > {spec.max_atr_ratio:.2f}x)."
                        )

        # ── 2. Kiểm tra nến xác nhận bổ sung (Price Action Confirmation) ──
        if df is not None and len(df) >= 1:
            last_candle = df.iloc[-1]
            high = float(last_candle["high"])
            low = float(last_candle["low"])
            open_p = float(last_candle["open"])
            close_p = float(last_candle["close"])
            candle_range = high - low

            # Với Liquidity Sweep: Cần có râu nến từ chối rõ rệt
            if candidate.setup_type == SetupType.SMC_LIQUIDITY_SWEEP and candle_range > 0:
                if candidate.direction.upper() == "SELL":
                    upper_wick = high - max(open_p, close_p)
                    if (upper_wick / candle_range) < 0.25:
                        warnings.append("Liquidity Sweep có râu trên tương đối ngắn (< 25% biên độ nến).")
                elif candidate.direction.upper() == "BUY":
                    lower_wick = min(open_p, close_p) - low
                    if (lower_wick / candle_range) < 0.25:
                        warnings.append("Liquidity Sweep có râu dưới tương đối ngắn (< 25% biên độ nến).")

        # Nếu có lý do từ chối -> Return INVALID
        if rejection_reasons:
            log.info("Setup [%s] bị từ chối thích ứng: %s", spec.name, "; ".join(rejection_reasons))
            return SetupValidationResult(
                is_valid=False,
                setup_type=candidate.setup_type,
                reasons=rejection_reasons,
                adapted_candidate=None,
                warning_messages=warnings,
            )

        # ── 3. Thích ứng mức Stop Loss / Take Profit (Cushion Adaptation) ──
        adapted = candidate
        if regime_result is not None and regime_result.cushion_multiplier != 1.0:
            cushion = regime_result.cushion_multiplier
            raw_sl_dist = candidate.sl_distance
            # Điều chỉnh SL theo hệ số đệm biến động
            new_sl_dist = round(min(12.5, max(10.0, raw_sl_dist * cushion)), 2)

            if candidate.direction.upper() == "BUY":
                new_sl = round(candidate.entry_price - new_sl_dist, 2)
                new_tp1 = round(candidate.entry_price + new_sl_dist, 2)
                new_tp2 = round(candidate.entry_price + (new_sl_dist * 2.0), 2)
            else:
                new_sl = round(candidate.entry_price + new_sl_dist, 2)
                new_tp1 = round(candidate.entry_price - new_sl_dist, 2)
                new_tp2 = round(candidate.entry_price - (new_sl_dist * 2.0), 2)

            # Cập nhật candidate đã thích ứng
            adapted_reasons = list(candidate.reasons)
            if cushion > 1.0:
                adapted_reasons.append(f"Thích ứng đệm SL x{cushion:.2f} do biến động thị trường ({new_sl_dist:.1f} giá)")

            adapted = SetupCandidate(
                setup_type=candidate.setup_type,
                direction=candidate.direction,
                entry_price=candidate.entry_price,
                stop_loss=new_sl,
                take_profit=new_tp2,
                take_profit_1=new_tp1,
                invalidation_level=candidate.invalidation_level or new_sl,
                setup_id=candidate.setup_id,
                reasons=adapted_reasons,
                score_components=candidate.score_components,
                invalidation=candidate.invalidation,
            )

        return SetupValidationResult(
            is_valid=True,
            setup_type=candidate.setup_type,
            reasons=["Setup thỏa mãn toàn bộ tiêu chí thích ứng Market Regime"],
            adapted_candidate=adapted,
            warning_messages=warnings,
        )
