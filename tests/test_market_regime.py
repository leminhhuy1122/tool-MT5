# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Market Regime Detector (Phase 3).

Kiểm thử toàn diện:
1. Chỉ báo ADX, +DI, -DI (Wilder).
2. Dải Bollinger Bands và Keltner Channels.
3. 5 Chế độ thị trường:
   - TRENDING_BULLISH
   - TRENDING_BEARISH
   - RANGING
   - HIGH_VOLATILITY_EXPANSION
   - COMPRESSION_SQUEEZE
4. Cơ chế đồng thuận đa khung thời gian (H4 + H1).
5. Cơ chế gán trọng số và lọc setup thích ứng theo Regime.
6. Tích hợp trong SignalEngine.
"""

import numpy as np
import pandas as pd
import pytest

from app.market.indicators import (
    add_all_indicators,
    calc_adx,
    calc_bollinger_bands,
    calc_keltner_channels,
)
from app.market.regime import (
    MarketRegime,
    MarketRegimeDetector,
    MarketRegimeResult,
    RegimeBias,
)
from app.strategy.setup_detector import SetupType
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection


def _make_ohlcv_series(
    n_bars: int = 60,
    base_price: float = 2000.0,
    trend: str = "FLAT",
    volatility: float = 1.0,
) -> pd.DataFrame:
    """Tạo chuỗi nến giả lập cho kiểm thử regime."""
    np.random.seed(42)
    prices = [base_price]
    step = 1.5 if trend == "BULLISH" else (-1.5 if trend == "BEARISH" else 0.0)

    for i in range(1, n_bars):
        noise = np.random.randn() * volatility
        p = prices[-1] + step + noise
        prices.append(p)

    closes = np.array(prices)
    highs = closes + np.abs(np.random.randn(n_bars) * volatility) + 0.5
    lows = closes - np.abs(np.random.randn(n_bars) * volatility) - 0.5
    opens = closes - (np.random.randn(n_bars) * 0.2)

    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n_bars, freq="1h"),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": np.random.randint(100, 500, n_bars),
    })


class TestRegimeIndicators:
    """Kiểm tra các chỉ báo kỹ thuật phục vụ nhận diện Regime."""

    def test_calc_adx(self):
        """Tính ADX, +DI, -DI chuẩn xác."""
        df = _make_ohlcv_series(n_bars=60, trend="BULLISH", volatility=0.5)
        adx, plus_di, minus_di = calc_adx(df, period=14)

        assert isinstance(adx, pd.Series)
        assert isinstance(plus_di, pd.Series)
        assert isinstance(minus_di, pd.Series)
        assert len(adx) == len(df)
        assert not pd.isna(adx.iloc[-1])
        assert not pd.isna(plus_di.iloc[-1])
        assert not pd.isna(minus_di.iloc[-1])
        # Xu hướng tăng mạnh: +DI phải lớn hơn -DI
        assert plus_di.iloc[-1] > minus_di.iloc[-1]

    def test_calc_bollinger_bands(self):
        """Tính Bollinger Bands và Bandwidth."""
        df = _make_ohlcv_series(n_bars=50)
        upper, middle, lower, bandwidth = calc_bollinger_bands(df, period=20, std_dev=2.0)

        assert upper.iloc[-1] > middle.iloc[-1] > lower.iloc[-1]
        assert bandwidth.iloc[-1] > 0.0
        # Kiểm tra công thức bandwidth = (upper - lower) / middle * 100
        expected_bw = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1] * 100.0
        assert pytest.approx(bandwidth.iloc[-1], 0.01) == expected_bw

    def test_calc_keltner_channels(self):
        """Tính Keltner Channels."""
        df = _make_ohlcv_series(n_bars=50)
        upper, middle, lower = calc_keltner_channels(df, ema_period=20, atr_period=10, multiplier=1.5)
        assert upper.iloc[-1] > middle.iloc[-1] > lower.iloc[-1]

    def test_add_all_indicators_includes_regime_cols(self):
        """add_all_indicators tự động tích hợp các cột indicator cho regime."""
        df = _make_ohlcv_series(n_bars=40)
        result = add_all_indicators(df, include_regime_indicators=True)
        assert "adx_14" in result.columns
        assert "plus_di_14" in result.columns
        assert "minus_di_14" in result.columns
        assert "bb_upper" in result.columns
        assert "bb_width" in result.columns


class TestMarketRegimeDetector:
    """Kiểm tra bộ phân loại chế độ thị trường MarketRegimeDetector."""

    def test_detect_trending_bullish(self):
        """Nhận diện xu hướng tăng mạnh TRENDING_BULLISH."""
        detector = MarketRegimeDetector()
        df = _make_ohlcv_series(n_bars=60, trend="BULLISH", volatility=0.2)
        res = detector.detect_regime(df)

        assert res.regime == MarketRegime.TRENDING_BULLISH
        assert res.bias == RegimeBias.BULLISH
        assert res.confidence >= 0.7
        assert res.metrics.plus_di > res.metrics.minus_di
        assert SetupType.TREND_CONTINUATION in res.allowed_setups
        assert SetupType.BOS_RETEST in res.allowed_setups

    def test_detect_trending_bearish(self):
        """Nhận diện xu hướng giảm mạnh TRENDING_BEARISH."""
        detector = MarketRegimeDetector()
        df = _make_ohlcv_series(n_bars=60, trend="BEARISH", volatility=0.2)
        res = detector.detect_regime(df)

        assert res.regime == MarketRegime.TRENDING_BEARISH
        assert res.bias == RegimeBias.BEARISH
        assert res.metrics.minus_di > res.metrics.plus_di
        assert SetupType.TREND_CONTINUATION in res.allowed_setups

    def test_detect_ranging(self):
        """Nhận diện thị trường đi ngang / tích lũy RANGING."""
        detector = MarketRegimeDetector()
        df = _make_ohlcv_series(n_bars=60, trend="FLAT", volatility=0.5)
        res = detector.detect_regime(df)

        assert res.regime in (MarketRegime.RANGING, MarketRegime.COMPRESSION_SQUEEZE)
        assert res.bias == RegimeBias.NEUTRAL
        assert SetupType.SMC_LIQUIDITY_SWEEP in res.allowed_setups
        assert SetupType.SMC_ORDER_BLOCK in res.allowed_setups

    def test_detect_high_volatility_expansion(self):
        """Nhận diện giãn nở biến động cực mạnh HIGH_VOLATILITY_EXPANSION."""
        detector = MarketRegimeDetector()
        # Tạo chuỗi nến bình thường sau đó nến biến động cực mạnh
        df = _make_ohlcv_series(n_bars=60, trend="FLAT", volatility=0.5)
        # Giả lập 5 nến cuối biên độ tăng vọt gấp 10 lần
        for i in range(-5, 0):
            df.loc[df.index[i], "high"] = df.loc[df.index[i], "close"] + 30.0
            df.loc[df.index[i], "low"] = df.loc[df.index[i], "close"] - 30.0

        res = detector.detect_regime(df)
        assert res.regime == MarketRegime.HIGH_VOLATILITY_EXPANSION
        assert res.cushion_multiplier == 1.5
        assert res.min_confluence_score == 75.0

    def test_detect_compression_squeeze(self):
        """Nhận diện nén biên độ (Squeeze) khi BB co hẹp trong Keltner Channel."""
        detector = MarketRegimeDetector()
        # Tạo chuỗi nến biến động bình thường trước
        df = _make_ohlcv_series(n_bars=50, trend="FLAT", volatility=3.0)
        # 15 nến cuối cực kỳ phẳng (biến động gần như bằng 0) -> Squeeze
        last_close = df["close"].iloc[40]
        for i in range(40, 50):
            df.loc[df.index[i], "close"] = last_close
            df.loc[df.index[i], "open"] = last_close
            df.loc[df.index[i], "high"] = last_close + 0.05
            df.loc[df.index[i], "low"] = last_close - 0.05

        res = detector.detect_regime(df)
        assert res.regime == MarketRegime.COMPRESSION_SQUEEZE
        assert res.metrics.is_squeeze is True
        assert res.cushion_multiplier == 0.8
        assert SetupType.PREDICTIVE_LIMIT in res.allowed_setups

    def test_multi_timeframe_alignment_boosts_confidence(self):
        """Đồng thuận giữa H4 và H1 làm tăng độ tin cậy của Regime."""
        detector = MarketRegimeDetector()
        h1_df = _make_ohlcv_series(n_bars=60, trend="BULLISH", volatility=0.2)
        h4_df = _make_ohlcv_series(n_bars=60, trend="BULLISH", volatility=0.2)

        res_single = detector.detect_regime(h1_df)
        res_mtf = detector.detect_regime(h1_df, h4_df=h4_df)

        assert res_mtf.h4_regime == MarketRegime.TRENDING_BULLISH
        assert res_mtf.confidence >= res_single.confidence
        assert any("Đồng thuận đa khung" in r for r in res_mtf.reasons)


class TestRegimeStrategyAdaptation:
    """Kiểm tra quy tắc thích ứng chiến lược theo Regime."""

    def test_score_adjustments(self):
        """Thử nghiệm điểm thưởng/phạt theo Regime."""
        detector = MarketRegimeDetector()
        df_bull = _make_ohlcv_series(n_bars=60, trend="BULLISH", volatility=0.2)
        res_bull = detector.detect_regime(df_bull)

        # Trong trending: Tiếp diễn xu hướng được cộng 10 điểm, phân kỳ bị trừ 15 điểm
        assert res_bull.get_score_adjustment(SetupType.TREND_CONTINUATION) == +10.0
        assert res_bull.get_score_adjustment(SetupType.RSI_DIVERGENCE) == -15.0

        # Trong ranging: Quét thanh khoản được cộng 10 điểm, tiếp diễn xu hướng bị trừ 15 điểm
        df_range = _make_ohlcv_series(n_bars=60, trend="FLAT", volatility=0.5)
        res_range = detector.detect_regime(df_range)
        if res_range.regime == MarketRegime.RANGING:
            assert res_range.get_score_adjustment(SetupType.SMC_LIQUIDITY_SWEEP) == +10.0
            assert res_range.get_score_adjustment(SetupType.TREND_CONTINUATION) == -15.0

    def test_allowed_setups(self):
        """Kiểm tra danh sách setup được phép theo Regime."""
        detector = MarketRegimeDetector()
        df_bull = _make_ohlcv_series(n_bars=60, trend="BULLISH", volatility=0.2)
        res = detector.detect_regime(df_bull)
        assert res.is_setup_allowed(SetupType.TREND_CONTINUATION) is True
        assert res.is_setup_allowed(SetupType.BOS_RETEST) is True


class TestSignalEngineRegimeIntegration:
    """Kiểm tra tích hợp Market Regime vào SignalEngine."""

    def test_signal_engine_regime_detector_initialized(self):
        """SignalEngine có detector regime được khởi tạo."""
        engine = SignalEngine()
        assert engine.regime_detector is not None
        assert isinstance(engine.regime_detector, MarketRegimeDetector)

    def test_get_current_regime_method(self):
        """Phương thức get_current_regime trả về kết quả chuẩn."""
        engine = SignalEngine()
        df = _make_ohlcv_series(n_bars=50)
        regime = engine.get_current_regime(df)
        assert isinstance(regime, MarketRegimeResult)
        assert regime.regime in MarketRegime

    def test_emitted_signal_contains_regime_data(self):
        """Tín hiệu phát ra (kể cả WAIT) mang thông tin market_regime chuẩn xác."""
        engine = SignalEngine()
        df = _make_ohlcv_series(n_bars=50)
        signal = engine.generate_signal(df=df)
        assert signal.market_regime != ""
        assert signal.market_regime in [r.value for r in MarketRegime]
