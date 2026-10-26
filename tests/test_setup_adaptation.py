# -*- coding: utf-8 -*-
"""
Unit and Integration tests for Setup Adaptation Engine (Phase 9).
"""

from unittest.mock import MagicMock
import pandas as pd
import pytest
from app.api.server import get_setup_specifications
from app.market.market_structure import MarketStructureResult, TrendDirection
from app.market.regime import MarketRegime, MarketRegimeResult, RegimeBias, RegimeMetrics
from app.strategy.setup_adapter import (
    SETUP_SPECIFICATIONS,
    SetupAdapterEngine,
    SetupSpecification,
    SetupValidationResult,
)
from app.strategy.setup_detector import SetupCandidate, SetupType
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection


@pytest.fixture
def sample_metrics():
    return RegimeMetrics(
        adx=25.0,
        plus_di=28.0,
        minus_di=14.0,
        atr_value=3.5,
        atr_percentile=55.0,
        bb_width=12.0,
        bb_width_percentile=50.0,
        is_squeeze=False,
        ema_alignment="BULLISH",
        ema_slope_20=0.15,
    )


@pytest.fixture
def sample_df():
    # Tạo 25 nến giả lập có cột atr_14, high, low, open, close
    data = []
    base_price = 2700.0
    for i in range(25):
        data.append({
            "open": base_price + i * 0.5,
            "high": base_price + i * 0.5 + 2.0,
            "low": base_price + i * 0.5 - 1.0,
            "close": base_price + i * 0.5 + 1.0,
            "atr_14": 3.0,
        })
    return pd.DataFrame(data)


class TestSetupSpecifications:
    """Kiểm tra tính đầy đủ và toàn vẹn của đặc tả 7 setup giao dịch."""

    def test_all_seven_setups_exist(self):
        core_setups = [
            SetupType.SMC_ORDER_BLOCK,
            SetupType.SMC_LIQUIDITY_SWEEP,
            SetupType.SMC_FVG_RETEST,
            SetupType.EMA_BOUNCE,
            SetupType.PREDICTIVE_LIMIT,
            SetupType.RSI_DIVERGENCE,
            SetupType.BOS_RETEST,
        ]
        for st in core_setups:
            assert st in SETUP_SPECIFICATIONS, f"Thiếu đặc tả cho {st.value}"
            spec = SETUP_SPECIFICATIONS[st]
            assert isinstance(spec, SetupSpecification)
            assert len(spec.definition) > 10
            assert len(spec.entry_condition) > 10
            assert len(spec.confirmation_rules) > 10
            assert len(spec.invalidation_rules) > 10
            assert len(spec.stop_methodology) > 10
            assert len(spec.target_methodology) > 10
            assert spec.expiry_bars > 0
            assert len(spec.compatible_regimes) > 0

    def test_specification_serialization(self):
        spec = SETUP_SPECIFICATIONS[SetupType.SMC_ORDER_BLOCK]
        d = spec.to_dict()
        assert d["setup_type"] == "SMC_ORDER_BLOCK"
        assert "TRENDING_BULLISH" in d["compatible_regimes"]
        assert d["expiry_bars"] == 30
        assert d["min_rr"] == 1.0


class TestSetupAdapterEngineRegimeValidation:
    """Kiểm tra quy tắc thẩm định tương thích Regime và chỉ số kỹ thuật."""

    def test_ema_bounce_rejected_in_ranging(self, sample_metrics, sample_df):
        engine = SetupAdapterEngine()
        candidate = SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
            take_profit_1=2710.0,
        )
        regime_ranging = MarketRegimeResult(
            regime=MarketRegime.RANGING,
            confidence=0.85,
            bias=RegimeBias.NEUTRAL,
            metrics=sample_metrics,
            cushion_multiplier=1.1,
        )

        res = engine.validate_and_adapt(candidate, df=sample_df, regime_result=regime_ranging)
        assert res.is_valid is False
        assert any("CẤM trong chế độ thị trường [RANGING]" in r for r in res.reasons)

    def test_ema_bounce_rejected_when_adx_too_low(self, sample_df):
        engine = SetupAdapterEngine()
        candidate = SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
            take_profit_1=2710.0,
        )
        low_adx_metrics = RegimeMetrics(
            adx=16.0,  # Ngưỡng yêu cầu là 22.0
            plus_di=20.0,
            minus_di=15.0,
            atr_value=2.0,
            atr_percentile=40.0,
            bb_width=8.0,
            bb_width_percentile=40.0,
            is_squeeze=False,
            ema_alignment="BULLISH",
            ema_slope_20=0.05,
        )
        regime_trending = MarketRegimeResult(
            regime=MarketRegime.TRENDING_BULLISH,
            confidence=0.75,
            bias=RegimeBias.BULLISH,
            metrics=low_adx_metrics,
            cushion_multiplier=1.0,
        )

        res = engine.validate_and_adapt(candidate, df=sample_df, regime_result=regime_trending)
        assert res.is_valid is False
        assert any("đòi hỏi ADX >= 22.0" in r for r in res.reasons)

    def test_ema_bounce_accepted_in_strong_trending(self, sample_metrics, sample_df):
        engine = SetupAdapterEngine()
        candidate = SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
            take_profit_1=2710.0,
        )
        regime_trending = MarketRegimeResult(
            regime=MarketRegime.TRENDING_BULLISH,
            confidence=0.88,
            bias=RegimeBias.BULLISH,
            metrics=sample_metrics,  # ADX = 25.0 >= 22.0
            cushion_multiplier=1.0,
        )

        res = engine.validate_and_adapt(candidate, df=sample_df, regime_result=regime_trending)
        assert res.is_valid is True
        assert res.adapted_candidate is not None

    def test_fvg_retest_rejected_in_high_volatility(self, sample_metrics, sample_df):
        engine = SetupAdapterEngine()
        candidate = SetupCandidate(
            setup_type=SetupType.SMC_FVG_RETEST,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
            take_profit_1=2710.0,
        )
        regime_vol = MarketRegimeResult(
            regime=MarketRegime.HIGH_VOLATILITY_EXPANSION,
            confidence=0.90,
            bias=RegimeBias.BULLISH,
            metrics=sample_metrics,
            cushion_multiplier=1.5,
        )

        res = engine.validate_and_adapt(candidate, df=sample_df, regime_result=regime_vol)
        assert res.is_valid is False
        assert any("HIGH_VOLATILITY_EXPANSION" in r for r in res.reasons)

    def test_liquidity_sweep_accepted_in_high_volatility(self, sample_metrics, sample_df):
        engine = SetupAdapterEngine()
        candidate = SetupCandidate(
            setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
            direction="SELL",
            entry_price=2720.0,
            stop_loss=2730.0,
            take_profit=2700.0,
            take_profit_1=2710.0,
        )
        regime_vol = MarketRegimeResult(
            regime=MarketRegime.HIGH_VOLATILITY_EXPANSION,
            confidence=0.90,
            bias=RegimeBias.BEARISH,
            metrics=sample_metrics,
            cushion_multiplier=1.2,
        )

        res = engine.validate_and_adapt(candidate, df=sample_df, regime_result=regime_vol)
        assert res.is_valid is True
        # Kiểm tra SL được điều chỉnh đệm biến động
        assert res.adapted_candidate is not None
        assert res.adapted_candidate.sl_distance >= 10.0


class TestSetupAdapterCushionAndConfirmation:
    """Kiểm tra điều chỉnh Stop Loss đệm và cảnh báo râu nến."""

    def test_cushion_multiplier_scales_sl(self, sample_metrics, sample_df):
        engine = SetupAdapterEngine()
        candidate = SetupCandidate(
            setup_type=SetupType.SMC_ORDER_BLOCK,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,  # raw sl_dist = 10.0
            take_profit=2720.0,
            take_profit_1=2710.0,
        )
        regime_cushion = MarketRegimeResult(
            regime=MarketRegime.HIGH_VOLATILITY_EXPANSION,
            confidence=0.85,
            bias=RegimeBias.BULLISH,
            metrics=sample_metrics,
            cushion_multiplier=1.2,  # scaled sl_dist = 10.0 * 1.2 = 12.0
        )

        res = engine.validate_and_adapt(candidate, df=sample_df, regime_result=regime_cushion)
        assert res.is_valid is True
        adapted = res.adapted_candidate
        assert adapted.sl_distance == 12.0
        assert adapted.stop_loss == 2688.0
        assert any("Thích ứng đệm SL x1.20" in r for r in adapted.reasons)

    def test_liquidity_sweep_wick_warning(self, sample_metrics):
        engine = SetupAdapterEngine()
        # Nến có râu trên rất bé
        df_stub = pd.DataFrame([{
            "open": 2700.0,
            "high": 2701.0,  # upper wick = 2701 - 2700.8 = 0.2 (20% range)
            "low": 2700.0,
            "close": 2700.8,
            "atr_14": 2.0,
        }])
        candidate = SetupCandidate(
            setup_type=SetupType.SMC_LIQUIDITY_SWEEP,
            direction="SELL",
            entry_price=2700.8,
            stop_loss=2710.8,
            take_profit=2680.8,
            take_profit_1=2690.8,
        )
        regime = MarketRegimeResult(
            regime=MarketRegime.RANGING,
            confidence=0.80,
            bias=RegimeBias.NEUTRAL,
            metrics=sample_metrics,
            cushion_multiplier=1.0,
        )

        res = engine.validate_and_adapt(candidate, df=df_stub, regime_result=regime)
        assert res.is_valid is True
        assert len(res.warning_messages) > 0
        assert any("râu trên tương đối ngắn" in w for w in res.warning_messages)


class TestSignalEngineSetupAdaptationIntegration:
    """Kiểm tra tích hợp SetupAdapterEngine bên trong SignalEngine."""

    def test_signal_engine_uses_setup_adapter_rejection(self, sample_df):
        engine = SignalEngine(symbol="XAUUSD", default_timeframe="H1")

        # Mock setup_detector sinh ra 1 EMA_BOUNCE candidate
        ema_cand = SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="BUY",
            entry_price=2700.0,
            stop_loss=2690.0,
            take_profit=2720.0,
            take_profit_1=2710.0,
        )

        # Mock regime_detector trả về RANGING
        mock_regime = MarketRegimeResult(
            regime=MarketRegime.RANGING,
            confidence=0.85,
            bias=RegimeBias.NEUTRAL,
            metrics=RegimeMetrics(
                adx=14.0, plus_di=18.0, minus_di=18.0, atr_value=2.0,
                atr_percentile=40.0, bb_width=8.0, bb_width_percentile=40.0,
                is_squeeze=False, ema_alignment="FLAT", ema_slope_20=0.0,
            ),
            cushion_multiplier=1.1,
        )

        engine.regime_detector.detect_regime = MagicMock(return_value=mock_regime)

        # Kiểm tra trực tiếp hàm validate_and_adapt của engine
        val_res = engine.setup_adapter.validate_and_adapt(
            candidate=ema_cand,
            df=sample_df,
            regime_result=mock_regime,
        )
        assert val_res.is_valid is False
        assert any("CẤM trong chế độ thị trường [RANGING]" in r for r in val_res.reasons)


class TestApiSetupSpecificationsEndpoint:
    """Kiểm tra REST API endpoint GET /api/v1/setups/specifications."""

    def test_get_setup_specifications_api(self):
        data = get_setup_specifications()
        assert "total_setups" in data
        assert data["total_setups"] >= 7
        assert "specifications" in data
        specs = data["specifications"]
        assert "SMC_ORDER_BLOCK" in specs
        assert "EMA_BOUNCE" in specs
        assert "SMC_LIQUIDITY_SWEEP" in specs
        assert specs["EMA_BOUNCE"]["min_adx"] == 22.0
