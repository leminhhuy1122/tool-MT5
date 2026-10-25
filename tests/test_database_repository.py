# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Database Repositories.
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.database.repository import (
    MarketDataRepository,
    SignalRepository,
    StrategyRepository,
)
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal


@pytest.fixture
def test_db():
    """Tạo database in-memory và chạy migration sẵn sàng cho mỗi test."""
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)
    return db


def _make_signal(
    signal_id: str = "sig_repo_1",
    direction: SignalDirection = SignalDirection.BUY,
    status: SignalStatus = SignalStatus.ACTIVE,
) -> TradingSignal:
    return TradingSignal(
        signal_id=signal_id,
        strategy_version="v1.0",
        direction=direction,
        status=status,
        symbol="XAUUSD",
        timeframe="H1",
        entry_price=2000.0,
        entry_zone_low=1999.0,
        entry_zone_high=2001.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        risk_reward_ratio=2.0,
        sl_distance=10.0,
        tp_distance=20.0,
        score=80.0,
        confidence="HIGH",
        setup_type="BOS_RETEST",
        reasons=["BOS Bullish", "Retest Support"],
        invalidation="Close dưới 1990",
        trend_h4="BULLISH",
        trend_h1="BULLISH",
    )


class TestSignalRepository:
    """Test suite cho SignalRepository."""

    def test_save_and_get_signal(self, test_db):
        """Lưu và truy vấn lại tín hiệu theo ID."""
        repo = SignalRepository(test_db)
        sig = _make_signal()

        assert repo.save_signal(sig) is True
        saved = repo.get_signal("sig_repo_1")

        assert saved is not None
        assert saved["signal_id"] == "sig_repo_1"
        assert saved["symbol"] == "XAUUSD"
        assert saved["direction"] == "BUY"
        assert saved["status"] == "ACTIVE"
        assert saved["entry_price"] == 2000.0
        assert saved["stop_loss"] == 1990.0
        assert saved["take_profit_1"] == 2020.0
        assert saved["score"] == 80.0
        assert saved["reasons"] == ["BOS Bullish", "Retest Support"]

    def test_save_signal_with_features(self, test_db):
        """Lưu tín hiệu kèm theo bảng chỉ số kỹ thuật features."""
        repo = SignalRepository(test_db)
        sig = _make_signal()
        features = {
            "rsi_14": 52.5,
            "ema_20": 1998.0,
            "ema_50": 1990.0,
            "ema_200": 1950.0,
            "atr_14": 4.5,
            "spread": 15.0,
            "volatility_level": "NORMAL",
            "body_ratio": 0.65,
            "candle_range": 6.0,
            "swing_high": 2010.0,
            "swing_low": 1995.0,
        }

        assert repo.save_signal(sig, features=features) is True

        with test_db.session() as conn:
            cursor = conn.execute(
                "SELECT * FROM signal_features WHERE signal_id = ?;", ("sig_repo_1",)
            )
            feat = dict(cursor.fetchone())

        assert feat["rsi_14"] == 52.5
        assert feat["volatility_level"] == "NORMAL"

    def test_update_status(self, test_db):
        """Cập nhật trạng thái tín hiệu."""
        repo = SignalRepository(test_db)
        sig = _make_signal()
        repo.save_signal(sig)

        assert repo.update_status("sig_repo_1", SignalStatus.ENTRY_REACHED) is True
        updated = repo.get_signal("sig_repo_1")
        assert updated["status"] == "ENTRY_REACHED"

    def test_save_outcome(self, test_db):
        """Lưu kết quả giao dịch và đồng bộ trạng thái ở bảng signals."""
        repo = SignalRepository(test_db)
        sig = _make_signal()
        repo.save_signal(sig)

        now = datetime.now(timezone.utc)
        assert repo.save_outcome(
            signal_id="sig_repo_1",
            final_status="TP_REACHED",
            entry_hit_price=2000.5,
            exit_price=2020.0,
            pnl_points=19.5,
            pnl_r=2.0,
            entry_time=now - timedelta(hours=2),
            exit_time=now,
            duration_seconds=7200,
            notes="Đạt TP1 chuẩn",
        ) is True

        # Kiểm tra bảng signal_outcomes
        with test_db.session() as conn:
            cursor = conn.execute(
                "SELECT * FROM signal_outcomes WHERE signal_id = ?;", ("sig_repo_1",)
            )
            outcome = dict(cursor.fetchone())

        assert outcome["final_status"] == "TP_REACHED"
        assert outcome["pnl_points"] == 19.5
        assert outcome["pnl_r"] == 2.0

        # Kiểm tra status bảng signals cũng được đồng bộ sang TP_REACHED
        sig_record = repo.get_signal("sig_repo_1")
        assert sig_record["status"] == "TP_REACHED"

    def test_get_active_signals(self, test_db):
        """Chỉ lấy các tín hiệu ACTIVE hoặc ENTRY_REACHED."""
        repo = SignalRepository(test_db)
        sig1 = _make_signal("sig1", status=SignalStatus.ACTIVE)
        sig2 = _make_signal("sig2", status=SignalStatus.ENTRY_REACHED)
        sig3 = _make_signal("sig3", status=SignalStatus.TP_REACHED)

        repo.save_signal(sig1)
        repo.save_signal(sig2)
        repo.save_signal(sig3)

        actives = repo.get_active_signals("XAUUSD")
        active_ids = [s["signal_id"] for s in actives]

        assert "sig1" in active_ids
        assert "sig2" in active_ids
        assert "sig3" not in active_ids

    def test_count_signals(self, test_db):
        """Đếm tổng số tín hiệu."""
        repo = SignalRepository(test_db)
        assert repo.count_signals() == 0
        repo.save_signal(_make_signal("sig1"))
        repo.save_signal(_make_signal("sig2"))
        assert repo.count_signals() == 2


class TestMarketDataRepository:
    """Test suite cho MarketDataRepository."""

    def test_save_and_get_candles(self, test_db):
        """Lưu nến vào database và truy vấn lại chính xác."""
        repo = MarketDataRepository(test_db)

        times = pd.date_range("2026-01-01", periods=10, freq="h")
        df = pd.DataFrame({
            "time": times,
            "open": [2000.0 + i for i in range(10)],
            "high": [2005.0 + i for i in range(10)],
            "low": [1995.0 + i for i in range(10)],
            "close": [2002.0 + i for i in range(10)],
            "tick_volume": [100.0] * 10,
            "spread": [20.0] * 10,
        })

        # Lưu 10 nến
        inserted = repo.save_candles("XAUUSD", "H1", df)
        assert inserted == 10

        # Lưu lại lần nữa -> Bỏ qua do trùng lặp (UNIQUE constraint)
        inserted_dup = repo.save_candles("XAUUSD", "H1", df)
        assert inserted_dup == 0

        # Truy vấn lại nến
        retrieved_df = repo.get_candles("XAUUSD", "H1", limit=5)
        assert len(retrieved_df) == 5
        # Nến cuối cùng (mới nhất) phải có close = 2011.0
        assert retrieved_df.iloc[-1]["close"] == 2011.0


class TestStrategyRepository:
    """Test suite cho StrategyRepository."""

    def test_register_and_get_version(self, test_db):
        """Đăng ký phiên bản chiến lược và truy vấn phiên bản đang active."""
        repo = StrategyRepository(test_db)

        params = {"min_rr": 1.5, "ema_period": 20, "timeframe": "M5"}
        assert repo.register_version(
            version="v1.0-M5",
            name="VietKey SMC Gold M5",
            description="Chiến lược theo dõi H1, vào lệnh M5",
            parameters=params,
            is_active=True,
        ) is True

        active = repo.get_active_version()
        assert active is not None
        assert active["version"] == "v1.0-M5"
        assert active["parameters"]["timeframe"] == "M5"
