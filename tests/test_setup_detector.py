# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Setup Detector.
"""

import pandas as pd
import numpy as np
import pytest

from app.market.market_structure import (
    MarketStructureResult,
    StructureBreak,
    StructureEvent,
    SwingPoint,
    SwingType,
    TrendDirection,
)
from app.strategy.setup_detector import (
    SetupCandidate,
    SetupType,
    detect_setups,
)


def _create_mock_df(n_bars: int = 30, base_price: float = 2000.0) -> pd.DataFrame:
    """Tạo DataFrame giả lập có sẵn các cột indicators."""
    prices = [base_price + i * 0.5 for i in range(n_bars)]
    df = pd.DataFrame({
        "open": prices,
        "high": [p + 2.0 for p in prices],
        "low": [p - 2.0 for p in prices],
        "close": prices,
        "ema_20": [p - 1.0 for p in prices],
        "ema_50": [p - 5.0 for p in prices],
        "rsi_14": [50.0] * n_bars,
        "atr_14": [3.0] * n_bars,
    })
    return df


class TestSetupDetector:
    """Test suite cho Setup Detector."""

    def test_setup_candidate_properties(self):
        """Kiểm tra các properties tính toán của SetupCandidate."""
        cand = SetupCandidate(
            setup_type=SetupType.EMA_BOUNCE,
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2020.0,
        )
        assert cand.sl_distance == 10.0
        assert cand.tp_distance == 20.0
        assert cand.risk_reward == 2.0

    def test_detect_setups_insufficient_data(self):
        """Dữ liệu ít hơn 20 nến phải trả về danh sách rỗng."""
        df_short = _create_mock_df(n_bars=10)
        struct = MarketStructureResult(trend=TrendDirection.BULLISH)
        candidates = detect_setups(df_short, struct, atr_value=2.0)
        assert len(candidates) == 0

    def test_detect_setups_none_dataframe(self):
        """None DataFrame phải trả về danh sách rỗng an toàn."""
        struct = MarketStructureResult(trend=TrendDirection.BULLISH)
        candidates = detect_setups(None, struct, atr_value=2.0)
        assert len(candidates) == 0

    def test_detect_setups_zero_atr(self):
        """ATR = 0 không thể tính SL/TP -> trả về rỗng."""
        df = _create_mock_df(n_bars=30)
        df["atr_14"] = 0.0
        struct = MarketStructureResult(trend=TrendDirection.BULLISH)
        candidates = detect_setups(df, struct, atr_value=0.0)
        assert len(candidates) == 0

    def test_detect_ema_bounce_buy(self):
        """Kiểm tra phát hiện EMA Bounce BUY."""
        df = _create_mock_df(n_bars=30, base_price=2000.0)
        # Thiết lập điều kiện bounce:
        # close > ema_20, prev_close <= ema_20 * 1.002, ema_20 > ema_50, 35 < rsi < 65
        ema20 = 2000.0
        ema50 = 1990.0
        df.loc[df.index[-2], "close"] = 2000.5
        df.loc[df.index[-1], "close"] = 2003.0
        df.loc[df.index[-1], "ema_20"] = ema20
        df.loc[df.index[-1], "ema_50"] = ema50
        df.loc[df.index[-1], "rsi_14"] = 48.0
        df.loc[df.index[-1], "atr_14"] = 4.0

        struct = MarketStructureResult(trend=TrendDirection.BULLISH)
        candidates = detect_setups(
            df=df,
            structure=struct,
            higher_tf_trend=TrendDirection.BULLISH,
            atr_value=4.0,
        )

        ema_candidates = [c for c in candidates if c.setup_type == SetupType.EMA_BOUNCE]
        assert len(ema_candidates) >= 1
        cand = ema_candidates[0]
        assert cand.direction == "BUY"
        assert cand.entry_price == 2003.0
        assert cand.stop_loss < cand.entry_price
        assert cand.take_profit > cand.entry_price
        assert cand.risk_reward > 1.5

    def test_detect_ema_bounce_sell(self):
        """Kiểm tra phát hiện EMA Bounce SELL."""
        df = _create_mock_df(n_bars=30, base_price=2000.0)
        ema20 = 2000.0
        ema50 = 2010.0
        df.loc[df.index[-2], "close"] = 1999.5
        df.loc[df.index[-1], "close"] = 1997.0
        df.loc[df.index[-1], "ema_20"] = ema20
        df.loc[df.index[-1], "ema_50"] = ema50
        df.loc[df.index[-1], "rsi_14"] = 52.0
        df.loc[df.index[-1], "atr_14"] = 4.0

        struct = MarketStructureResult(trend=TrendDirection.BEARISH)
        candidates = detect_setups(
            df=df,
            structure=struct,
            higher_tf_trend=TrendDirection.BEARISH,
            atr_value=4.0,
        )

        ema_candidates = [c for c in candidates if c.setup_type == SetupType.EMA_BOUNCE]
        assert len(ema_candidates) >= 1
        cand = ema_candidates[0]
        assert cand.direction == "SELL"
        assert cand.stop_loss > cand.entry_price
        assert cand.take_profit < cand.entry_price

    def test_detect_bos_retest_buy(self):
        """Kiểm tra phát hiện BOS Retest BUY."""
        df = _create_mock_df(n_bars=30, base_price=2000.0)
        close = 2010.0
        df.loc[df.index[-1], "close"] = close
        df.loc[df.index[-1], "rsi_14"] = 55.0
        df.loc[df.index[-1], "atr_14"] = 3.0

        # BOS xảy ra ở level 2008 (close 2010 nằm gần 2008)
        bos_event = StructureEvent(
            event_type=StructureBreak.BOS_BULLISH,
            index=25,
            price=2012.0,
            broken_level=2008.0,
        )
        struct = MarketStructureResult(
            swings=[SwingPoint(index=20, price=2000.0, swing_type=SwingType.SWING_LOW)],
            trend=TrendDirection.BULLISH,
            structure_events=[bos_event],
        )

        candidates = detect_setups(
            df=df,
            structure=struct,
            higher_tf_trend=TrendDirection.BULLISH,
            atr_value=3.0,
        )

        bos_candidates = [c for c in candidates if c.setup_type == SetupType.BOS_RETEST]
        assert len(bos_candidates) >= 1
        cand = bos_candidates[0]
        assert cand.direction == "BUY"
        assert cand.risk_reward >= 1.5

    def test_detect_rsi_extreme_buy(self):
        """Kiểm tra phát hiện RSI oversold extreme BUY."""
        df = _create_mock_df(n_bars=30, base_price=2000.0)
        df.loc[df.index[-1], "close"] = 1980.0
        df.loc[df.index[-1], "rsi_14"] = 25.0  # Oversold < 30
        df.loc[df.index[-1], "atr_14"] = 3.0

        struct = MarketStructureResult(trend=TrendDirection.NEUTRAL)
        candidates = detect_setups(
            df=df,
            structure=struct,
            higher_tf_trend=TrendDirection.NEUTRAL,
            atr_value=3.0,
        )

        rsi_candidates = [c for c in candidates if c.setup_type == SetupType.RSI_DIVERGENCE]
        assert len(rsi_candidates) >= 1
        assert rsi_candidates[0].direction == "BUY"

    def test_detect_predictive_limit_setup(self):
        """Kiểm tra phát hiện Kế hoạch Dự đoán Từ xa (PREDICTIVE_LIMIT) khi có vùng hỗ trợ/kháng cự cách xa."""
        from app.market.market_structure import SRZone
        df = _create_mock_df(n_bars=30, base_price=4015.0)
        df.loc[df.index[-1], "close"] = 4015.0
        df.loc[df.index[-1], "rsi_14"] = 52.0
        df.loc[df.index[-1], "atr_14"] = 3.0

        # Vùng hỗ trợ cách giá hiện tại 15 giá (4000.0)
        sup_zone = SRZone(price=4000.0, zone_type="SUPPORT", strength=3)
        struct = MarketStructureResult(
            swings=[SwingPoint(index=15, price=4000.0, swing_type=SwingType.SWING_LOW)],
            trend=TrendDirection.BULLISH,
            sr_zones=[sup_zone],
        )

        candidates = detect_setups(
            df=df,
            structure=struct,
            higher_tf_trend=TrendDirection.BULLISH,
            atr_value=3.0,
        )

        limit_cands = [c for c in candidates if c.setup_type == SetupType.PREDICTIVE_LIMIT]
        assert len(limit_cands) >= 1
        limit_cand = limit_cands[0]
        assert limit_cand.direction == "BUY"
        assert limit_cand.entry_price == 4000.0
        assert limit_cand.risk_reward >= 1.5
        assert any("DỰ ĐOÁN TỪ XA" in r for r in limit_cand.reasons)

