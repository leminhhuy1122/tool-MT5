# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: Database.

Kiểm tra toàn diện lưu trữ dữ liệu thực tế vào SQLite:
- Chạy migrations khởi tạo 7 bảng cốt lõi.
- Lưu trữ nến XAUUSD thực tế vào market_data.
- Lưu trữ và cập nhật tín hiệu giao dịch, features và outcomes.
- Quản lý phiên bản chiến lược.

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_database.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from config import get_settings
from logger import setup_logging, get_logger
from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations, get_current_version
from app.database.repository import (
    MarketDataRepository,
    SignalRepository,
    StrategyRepository,
)
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.mt5.connector import MT5Connector
from app.market.timeframe_manager import Timeframe
from app.market.data_manager import MarketDataManager

setup_logging()
log = get_logger("integration.database")


def main() -> int:
    """Chạy integration test Database."""
    print("=" * 65)
    print("  VietKey Gold AI — Integration Test: Database (Phase 6)")
    print("=" * 65)

    settings = get_settings()

    # 1. Khởi tạo Database Manager & Chạy Migrations
    print("\n--- 1. Khởi tạo Database & Chạy Migrations ---")
    db = DatabaseManager(config=settings.database)
    current_ver = run_migrations(db)
    print(f"✓ Database Path: {db.db_path}")
    print(f"✓ Schema Version: v{current_ver}")

    signal_repo = SignalRepository(db)
    market_repo = MarketDataRepository(db)
    strategy_repo = StrategyRepository(db)

    # 2. Đăng ký phiên bản chiến lược M5/H1
    print("\n--- 2. Đăng ký phiên bản chiến lược ---")
    strategy_repo.register_version(
        version="v1.0-M5",
        name="VietKey Gold Scalper M5",
        description="Khung vào lệnh M5, lọc xu hướng H1/H4 theo SMC và EMA bounce",
        parameters={
            "execution_tf": "M5",
            "trend_tf": "H1",
            "min_rr": 1.5,
            "ema_periods": [20, 50, 200],
        },
        is_active=True,
    )
    active_strat = strategy_repo.get_active_version()
    print(f"✓ Active Strategy: {active_strat['version']} — {active_strat['name']}")

    # 3. Lấy dữ liệu nến thật từ MT5 và lưu vào database
    print("\n--- 3. Thu thập nến MT5 thật và lưu vào Database ---")
    connector = MT5Connector(settings.mt5)
    result = connector.connect()

    if result.success:
        try:
            symbol = settings.mt5.symbol
            mgr = MarketDataManager(symbol)
            df_m5 = mgr.get_candles(Timeframe.M5, num_bars=50)

            if df_m5 is not None and not df_m5.empty:
                inserted = market_repo.save_candles(symbol, "M5", df_m5)
                print(f"✓ Đã lưu {inserted} nến M5 vào bảng market_data.")

                # Truy vấn lại nến từ database
                df_loaded = market_repo.get_candles(symbol, "M5", limit=5)
                print(f"✓ Truy vấn lại {len(df_loaded)} nến từ SQLite:")
                for _, r in df_loaded.iterrows():
                    print(f"   • {r['time']} | C={r['close']:.2f} | H={r['high']:.2f} | L={r['low']:.2f}")
            else:
                print("⚠️ Không lấy được nến M5 từ MT5.")
        finally:
            connector.disconnect()
    else:
        print("ℹ️ MT5 terminal không khả dụng lúc này. Sử dụng nến mô phỏng để test.")
        times = pd.date_range("2026-10-25 10:00", periods=10, freq="5min")
        df_sim = pd.DataFrame({
            "time": times,
            "open": [4000.0 + i for i in range(10)],
            "high": [4003.0 + i for i in range(10)],
            "low": [3998.0 + i for i in range(10)],
            "close": [4002.0 + i for i in range(10)],
            "tick_volume": [150.0] * 10,
            "spread": [20.0] * 10,
        })
        market_repo.save_candles("XAUUSD", "M5", df_sim)
        print("✓ Đã lưu 10 nến mô phỏng vào market_data.")

    # 4. Lưu vết tín hiệu và đặc trưng ML (Features)
    print("\n--- 4. Lưu vết Tín hiệu Giao dịch & ML Features ---")
    now = datetime.now(timezone.utc)
    test_sig = TradingSignal(
        signal_id="xau_db_01",
        strategy_version="v1.0-M5",
        direction=SignalDirection.BUY,
        status=SignalStatus.ACTIVE,
        symbol="XAUUSD",
        timeframe="M5",
        entry_price=4003.0,
        entry_zone_low=4002.0,
        entry_zone_high=4004.0,
        stop_loss=3989.0,
        take_profit_1=4019.0,
        take_profit_2=4033.0,
        risk_reward_ratio=2.0,
        sl_distance=14.0,
        tp_distance=16.0,
        score=85.0,
        confidence="HIGH",
        setup_type="BOS_RETEST",
        reasons=["BOS Bullish xác nhận", "Retest EMA20 khung M5", "H1 Trend Bullish"],
        invalidation="Close dưới 3989.0",
        trend_h4="BULLISH",
        trend_h1="BULLISH",
        created_at=now,
    )

    features = {
        "rsi_14": 52.8,
        "ema_20": 4001.5,
        "ema_50": 3995.0,
        "ema_200": 3950.0,
        "atr_14": 4.5,
        "spread": 15.0,
        "volatility_level": "NORMAL",
        "body_ratio": 0.70,
        "candle_range": 6.5,
        "swing_high": 4010.0,
        "swing_low": 3990.0,
    }

    signal_repo.save_signal(test_sig, features=features)
    print("✓ Đã lưu tín hiệu [#xau_db_01] và features vào database.")

    # 5. Cập nhật trạng thái và Lưu kết quả giao dịch (Outcome)
    print("\n--- 5. Cập nhật Tiến độ & Lưu Outcome (Kết quả) ---")
    signal_repo.update_status("xau_db_01", SignalStatus.ENTRY_REACHED)
    print("✓ Trạng thái cập nhật: ENTRY_REACHED")

    signal_repo.save_outcome(
        signal_id="xau_db_01",
        final_status="TP_REACHED",
        entry_hit_price=4003.2,
        exit_price=4019.0,
        pnl_points=15.8,
        pnl_r=2.0,
        entry_time=now,
        exit_time=now,
        duration_seconds=1800,
        notes="Chạm TP1 hoàn hảo, lãi 15.8 giá",
    )
    print("✓ Đã lưu outcome: TP_REACHED (+15.8 giá, +2.0R)")

    # 6. Kiểm tra lại dữ liệu vừa lưu
    print("\n--- 6. Kiểm tra toàn vẹn dữ liệu ---")
    sig_saved = signal_repo.get_signal("xau_db_01")
    assert sig_saved is not None
    assert sig_saved["status"] == "TP_REACHED"
    assert sig_saved["reasons"] == ["BOS Bullish xác nhận", "Retest EMA20 khung M5", "H1 Trend Bullish"]
    print(f"✓ Tín hiệu đã đồng bộ: ID={sig_saved['signal_id']} | Status={sig_saved['status']} | Score={sig_saved['score']}")
    print(f"✓ Tổng số tín hiệu trong database: {signal_repo.count_signals()}")

    print("\n✅ Integration Test: Database PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
