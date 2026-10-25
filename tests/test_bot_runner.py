# -*- coding: utf-8 -*-
"""Unit tests for Live Bot Runner (Phase 10)."""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from app.bot.runner import LiveBotRunner
from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from tests.test_ml_features import make_sample_df


@pytest.fixture
def mock_runner():
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)

    mock_connector = MagicMock()
    mock_connector.is_connected = True
    mock_connector.connect.return_value = MagicMock(success=True)

    mock_notifier = MagicMock()
    mock_notifier.is_enabled = True

    runner = LiveBotRunner(
        db_manager=db,
        connector=mock_connector,
        notifier=mock_notifier,
    )
    return runner


def test_runner_initialization(mock_runner):
    assert mock_runner.symbol == "XAUUSD"
    assert mock_runner.is_running is False
    assert mock_runner.signal_engine is not None
    assert mock_runner.tracker is not None


def test_runner_start_stop(mock_runner):
    mock_runner.start()
    assert mock_runner.is_running is True

    mock_runner.stop()
    assert mock_runner.is_running is False


def test_runner_run_once_with_mock_market(mock_runner):
    df_m5 = make_sample_df(40)
    df_h1 = make_sample_df(30)

    mock_runner.data_mgr.get_latest_price = MagicMock(return_value={
        "bid": 2705.50,
        "ask": 2705.80,
        "spread": 0.30,
    })
    mock_runner.data_mgr.get_candles = MagicMock(side_effect=lambda tf, num_bars: df_m5 if "M5" in str(tf) else df_h1)

    # Test run_once
    sig = mock_runner.run_once()
    assert mock_runner.last_price == 2705.50
    assert mock_runner.last_processed_m5_time is not None


def test_runner_news_blackout_skips_signal(mock_runner):
    """Kiểm tra bot tự động hoãn phát tín hiệu khi rơi vào vùng cấm tin đỏ USD."""
    from app.news.models import EconomicEvent, NewsImpact
    from datetime import datetime, timezone

    mock_event = EconomicEvent(
        id="USD_CPI",
        title="CPI m/m",
        country="USD",
        impact=NewsImpact.HIGH,
        time_utc=datetime.now(timezone.utc),
    )

    mock_runner.news_mgr.is_in_blackout_window = MagicMock(return_value=(True, mock_event))
    mock_runner.data_mgr.get_latest_price = MagicMock(return_value={"bid": 2700.0, "ask": 2700.3, "spread": 0.3})
    mock_runner.data_mgr.get_candles = MagicMock(return_value=make_sample_df(40))

    sig = mock_runner.run_once()
    assert sig is None
