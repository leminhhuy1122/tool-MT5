# -*- coding: utf-8 -*-
"""Unit tests for ML Dataset Builder."""

import pandas as pd
import pytest

from app.backtest.models import TradeRecord, TradeStatus
from app.ml.dataset import DatasetBuilder
from tests.test_ml_features import make_sample_df


def test_time_series_split():
    df = pd.DataFrame({"feat1": range(100), "feat2": range(100, 200)})
    y = pd.Series([i % 2 for i in range(100)])

    X_train, y_train, X_val, y_val, X_test, y_test = DatasetBuilder.time_series_split(
        df, y, train_ratio=0.7, val_ratio=0.15
    )

    assert len(X_train) == 70
    assert len(X_val) == 15
    assert len(X_test) == 15
    # Strict order check (no shuffle)
    assert X_train.iloc[0]["feat1"] == 0
    assert X_train.iloc[-1]["feat1"] == 69
    assert X_val.iloc[0]["feat1"] == 70
    assert X_test.iloc[-1]["feat1"] == 99


def test_build_from_trades():
    df = make_sample_df(40)
    trades = [
        TradeRecord(
            trade_id="T1",
            signal_id="S1",
            direction="BUY",
            actual_entry_price=2705.0,
            status=TradeStatus.CLOSED_TP1,
            pnl_points=10.0,
        ),
        TradeRecord(
            trade_id="T2",
            signal_id="S2",
            direction="SELL",
            actual_entry_price=2710.0,
            status=TradeStatus.CLOSED_SL,
            pnl_points=-6.0,
        ),
    ]

    X, y = DatasetBuilder.build_from_trades(trades, df)
    assert len(X) == 2
    assert len(y) == 2
    assert y.iloc[0] == 1
    assert y.iloc[1] == 0
