# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: Signal Engine.

Chạy phân tích đa khung thời gian và sinh tín hiệu thực tế trên dữ liệu XAUUSD từ MT5.

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_signal.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from logger import setup_logging, get_logger
from app.mt5.connector import MT5Connector
from app.market.timeframe_manager import Timeframe
from app.market.data_manager import MarketDataManager
from app.market.indicators import add_all_indicators
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection

setup_logging()
log = get_logger("integration.signal")


def main() -> int:
    """Chạy integration test cho Signal Engine."""
    settings = get_settings()
    symbol = settings.mt5.symbol

    print("=" * 65)
    print("  VietKey Gold AI — Integration Test: Signal Engine (Phase 4)")
    print("=" * 65)

    connector = MT5Connector(settings.mt5)
    result = connector.connect()
    if not result.success:
        print("❌ Không thể kết nối MT5 terminal!")
        return 1

    try:
        terminal_info = connector.get_terminal_info()
        terminal_name = terminal_info.get("name", "MT5") if isinstance(terminal_info, dict) else getattr(terminal_info, "name", "MT5")
        print(f"✓ MT5 Connected: {terminal_name}")
        print(f"✓ Symbol: {symbol}")

        # 1. Thu thập dữ liệu nến thực tế qua MarketDataManager
        print("\n--- 1. Thu thập nến thực tế từ MT5 ---")
        mgr = MarketDataManager(symbol)
        df_h4 = mgr.get_candles(Timeframe.H4, num_bars=200)
        df_h1 = mgr.get_candles(Timeframe.H1, num_bars=200)
        df_m15 = mgr.get_candles(Timeframe.M15, num_bars=200)

        if df_h4 is None or df_h1 is None:
            print("❌ Không lấy được dữ liệu nến từ MT5!")
            return 1

        print(f"✓ H4 Bars: {len(df_h4)} | Close: {df_h4['close'].iloc[-1]:.2f}")
        print(f"✓ H1 Bars: {len(df_h1)} | Close: {df_h1['close'].iloc[-1]:.2f}")
        if df_m15 is not None:
            print(f"✓ M15 Bars: {len(df_m15)} | Close: {df_m15['close'].iloc[-1]:.2f}")

        # 2. Khởi tạo Signal Engine
        print("\n--- 2. Khởi tạo Signal Engine ---")
        engine = SignalEngine(strategy_version="v1.0", symbol=symbol, default_timeframe="H1")
        print(f"✓ Engine initialized (version: {engine.strategy_version})")

        # 3. Phân tích và sinh tín hiệu cho H1
        print("\n--- 3. Phân tích và sinh tín hiệu H1 ---")
        signal_h1 = engine.generate_signal(
            df=df_h1,
            h4_df=df_h4,
            symbol=symbol,
            timeframe="H1",
        )

        print("\n" + "=" * 55)
        print("  KẾT QUẢ TÍN HIỆU H1:")
        print("=" * 55)
        print(signal_h1.summary())
        print("=" * 55)

        # 4. Phân tích thêm trên M15 nếu có dữ liệu
        if df_m15 is not None:
            print("\n--- 4. Phân tích và sinh tín hiệu M15 (Scalping Context) ---")
            engine_m15 = SignalEngine(strategy_version="v1.0-M15", symbol=symbol, default_timeframe="M15")
            signal_m15 = engine_m15.generate_signal(
                df=df_m15,
                h4_df=df_h1,  # Cho M15, khung trend lớn là H1
                symbol=symbol,
                timeframe="M15",
            )
            print("\n" + "=" * 55)
            print("  KẾT QUẢ TÍN HIỆU M15:")
            print("=" * 55)
            print(signal_m15.summary())
            print("=" * 55)

        # 5. Kiểm tra tính hợp lệ
        assert signal_h1 is not None
        assert signal_h1.symbol == symbol
        assert signal_h1.direction in (SignalDirection.BUY, SignalDirection.SELL, SignalDirection.WAIT)

        print("\n✅ Integration Test: Signal Engine PASSED!")
        return 0

    finally:
        connector.disconnect()


if __name__ == "__main__":
    sys.exit(main())
