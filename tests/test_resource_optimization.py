# -*- coding: utf-8 -*-
"""
Unit and Integration tests for Resource Optimization & System Diagnostics (Phase 10).
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from app.api.server import get_system_benchmark
from app.bot.runner import LiveBotRunner
from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.market.timeframe_manager import Timeframe
from app.system.resource_optimizer import (
    BoundedDataCache,
    ProcessSingletonGuard,
    ResourceProfiler,
)
from config import OptimizationConfig, Settings


@pytest.fixture
def memory_db():
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)
    return db


@pytest.fixture
def sample_df():
    data = []
    base_price = 2700.0
    for i in range(25):
        data.append({
            "open": base_price + i * 0.5,
            "high": base_price + i * 0.5 + 2.0,
            "low": base_price + i * 0.5 - 1.0,
            "close": base_price + i * 0.5 + 1.0,
            "atr_14": 3.0,
            "ema_20": base_price + i * 0.4,
            "ema_50": base_price + i * 0.3,
            "ema_200": base_price + i * 0.2,
            "rsi_14": 52.0,
            "time": pd.Timestamp("2026-10-26 12:00:00", tz="UTC") + pd.Timedelta(minutes=5 * i),
        })
    return pd.DataFrame(data)


class TestOptimizationConfig:
    """Kiểm tra cấu hình OptimizationConfig."""

    def test_default_values(self):
        cfg = OptimizationConfig()
        assert cfg.enable_ml_filter is True
        assert cfg.enable_self_learning is True
        assert cfg.max_cached_candles == 200
        assert cfg.data_cache_ttl_sec == 3.0
        assert cfg.enable_process_singleton is True

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ML_FILTER", "false")
        monkeypatch.setenv("ENABLE_SELF_LEARNING", "0")
        monkeypatch.setenv("MAX_CACHED_CANDLES", "150")
        monkeypatch.setenv("DATA_CACHE_TTL_SEC", "10.0")

        cfg = OptimizationConfig.from_env()
        assert cfg.enable_ml_filter is False
        assert cfg.enable_self_learning is False
        assert cfg.max_cached_candles == 150
        assert cfg.data_cache_ttl_sec == 10.0


class TestProcessSingletonGuard:
    """Kiểm tra cơ chế chống trùng lặp tiến trình bot."""

    def test_acquire_and_release(self, tmp_path):
        lock_file = tmp_path / "test_runner.lock"
        guard = ProcessSingletonGuard(lock_file_path=str(lock_file))

        assert guard.acquire() is True
        assert lock_file.exists()
        assert str(os.getpid()) in lock_file.read_text(encoding="utf-8")

        # Cùng PID gọi lại acquire vẫn trả về True
        assert guard.acquire() is True

        guard.release()
        assert not lock_file.exists()

    def test_double_process_rejected(self, tmp_path):
        lock_file = tmp_path / "test_runner.lock"
        # Giả lập lock file đã bị sở hữu bởi 1 PID đang chạy khác (vd PID của process cha hoặc PID hiện tại + giả lập)
        lock_file.write_text(f"{os.getpid() + 999999}:1234567.0", encoding="utf-8")

        guard = ProcessSingletonGuard(lock_file_path=str(lock_file))
        with patch("psutil.pid_exists", return_value=True):
            with patch("psutil.Process") as mock_proc:
                mock_instance = MagicMock()
                mock_instance.is_running.return_value = True
                mock_instance.status.return_value = "running"
                mock_proc.return_value = mock_instance

                # Tiến trình thứ 2 phải bị từ chối
                assert guard.acquire() is False


class TestBoundedDataCache:
    """Kiểm tra BoundedDataCache với giới hạn max_bars và TTL."""

    def test_bounds_maximum_candles(self):
        cache = BoundedDataCache(max_bars=5, ttl_seconds=2.0)
        df_large = pd.DataFrame({"close": range(10)})
        cache.put(Timeframe.M5, df_large)

        cached = cache.get(Timeframe.M5)
        assert cached is not None
        assert len(cached) == 5
        assert list(cached["close"]) == [5, 6, 7, 8, 9]

    def test_ttl_expiry(self):
        cache = BoundedDataCache(max_bars=10, ttl_seconds=0.1)
        df = pd.DataFrame({"close": [1, 2, 3]})
        cache.put(Timeframe.H1, df)

        # Còn trong TTL -> lấy được
        assert cache.get(Timeframe.H1) is not None

        # Chờ quá TTL -> trả về default
        time.sleep(0.15)
        assert cache.get(Timeframe.H1, default=None) is None

    def test_dict_like_operations(self):
        cache = BoundedDataCache(max_bars=10, ttl_seconds=5.0)
        df = pd.DataFrame({"close": [100.0]})
        cache[Timeframe.M5] = df

        assert Timeframe.M5 in cache
        assert len(cache) == 1
        assert cache[Timeframe.M5]["close"].iloc[0] == 100.0

        cache.clear()
        assert len(cache) == 0


class TestResourceProfiler:
    """Kiểm tra đo lường tài nguyên và Benchmark hệ thống."""

    def test_get_process_metrics(self):
        metrics = ResourceProfiler.get_process_metrics()
        assert "pid" in metrics
        assert metrics["pid"] == os.getpid()
        assert metrics["ram_rss_mb"] > 0
        assert metrics["threads_count"] >= 1
        assert "cpu_percent" in metrics

    def test_measure_latency(self):
        def sample_work():
            time.sleep(0.02)
            return "ok"

        res, latency_ms = ResourceProfiler.measure_latency(sample_work)
        assert res == "ok"
        assert latency_ms >= 15.0  # ít nhất ~20ms

    def test_measure_database_footprint(self, memory_db):
        footprint = ResourceProfiler.measure_database_footprint(memory_db)
        assert footprint["status"] == "ONLINE"
        assert "signals" in footprint["table_counts"]
        assert "market_data" in footprint["table_counts"]

    def test_get_system_benchmark(self, memory_db, sample_df):
        from app.strategy.signal_engine import SignalEngine
        eng = SignalEngine(strategy_version="v1.0-Test")

        bench = ResourceProfiler.get_system_benchmark(
            db_manager=memory_db,
            signal_engine=eng,
            sample_df=sample_df,
        )

        assert "process" in bench
        assert "database" in bench
        assert "benchmarks" in bench
        assert bench["benchmarks"]["signal_generation_latency_ms"] >= 0.0
        assert bench["benchmarks"]["latency_status"] in ("EXCELLENT", "GOOD", "WARNING")
        assert bench["resource_efficiency"]["memory_bounded"] is True


class TestBotRunnerOptimizationIntegration:
    """Kiểm tra cấu hình tối ưu hóa tài nguyên trong LiveBotRunner."""

    def test_runner_honors_disabled_ml_and_self_learning(self, monkeypatch, memory_db):
        monkeypatch.setenv("ENABLE_ML_FILTER", "false")
        monkeypatch.setenv("ENABLE_SELF_LEARNING", "false")
        monkeypatch.setenv("ENABLE_PROCESS_SINGLETON", "false")

        settings = Settings.load()
        assert settings.optimization.enable_ml_filter is False
        assert settings.optimization.enable_self_learning is False

        mock_connector = MagicMock()
        mock_connector.is_connected = True

        runner = LiveBotRunner(
            settings=settings,
            db_manager=memory_db,
            connector=mock_connector,
        )

        assert runner.ml_filter is None
        assert runner.feedback_engine is None
        assert runner.signal_engine.ml_filter is None
        assert runner.signal_engine.feedback_engine is None

    def test_runner_check_new_candle_skips_processing(self, memory_db):
        mock_connector = MagicMock()
        mock_connector.is_connected = True

        runner = LiveBotRunner(db_manager=memory_db, connector=mock_connector)
        runner.last_processed_m5_time = pd.Timestamp("2026-10-26 12:00:00", tz="UTC")

        # Mock check_new_candle trả về False (chưa có nến mới)
        runner.data_mgr.check_new_candle = MagicMock(
            return_value=(False, runner.last_processed_m5_time)
        )
        runner.data_mgr.get_latest_price = MagicMock(
            return_value={"bid": 2700.0, "ask": 2700.3, "spread": 0.3}
        )

        sig = runner.run_once()
        assert sig is None
        # get_candles không được gọi vì nến chưa đóng
        assert runner.data_mgr.check_new_candle.called


class TestApiSystemBenchmarkEndpoint:
    """Kiểm tra API endpoint GET /api/v1/system/benchmark."""

    def test_api_system_benchmark(self):
        data = get_system_benchmark()
        assert "process" in data
        assert "database" in data
        assert "benchmarks" in data
        assert "resource_efficiency" in data
        assert data["resource_efficiency"]["memory_bounded"] is True
