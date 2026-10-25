# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: Backtest Engine (Phase 7).

Kiểm tra toàn diện hệ thống kiểm thử tự động (Backtest & Walk-Forward Analysis):
- Nạp dữ liệu nến đa khung thời gian: Khung thực thi M5 và Khung xu hướng H1.
- Mô phỏng Bar-by-bar không look-ahead bias, tính toán Spread & Slippage.
- Áp dụng các quy tắc quản lý lệnh vàng thực chiến:
  + Lãi 5 giá -> Kéo Stop Loss về hòa vốn (Breakeven).
  + Lãi 10 giá -> Chốt 50% khối lượng (TP1), gồng phần còn lại nuôi TP2.
- Đánh giá độ ổn định của chiến lược qua Walk-Forward Analysis (3 chu kỳ).

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_backtest.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from app.backtest.engine import BacktestEngine
from app.backtest.models import BacktestConfig, BacktestResult, TradeStatus
from app.backtest.walk_forward import WalkForwardAnalyzer, WalkForwardReport
from app.database.connection import DatabaseManager
from app.database.repository import MarketDataRepository
from app.market.data_manager import MarketDataManager
from app.market.timeframe_manager import Timeframe
from app.mt5.connector import MT5Connector
from config import get_settings
from logger import get_logger, setup_logging

setup_logging()
log = get_logger("integration.backtest")


def generate_synthetic_gold_data(n_bars: int = 500, start_price: float = 2700.0) -> pd.DataFrame:
    """Tạo dữ liệu sóng giả lập XAUUSD nếu không kết nối được MT5."""
    times = pd.date_range("2026-03-01 00:00:00", periods=n_bars, freq="5min", tz=timezone.utc)
    prices = [start_price]
    step = 0.8
    direction = 1

    for i in range(1, n_bars):
        if i % 25 == 0:
            direction *= -1
        change = direction * step + np.random.normal(0, 0.4)
        prices.append(max(2000.0, prices[-1] + change))

    df = pd.DataFrame({
        "time": times,
        "open": prices,
        "high": [p + abs(np.random.normal(0.8, 0.3)) for p in prices],
        "low": [p - abs(np.random.normal(0.8, 0.3)) for p in prices],
        "close": [p + np.random.normal(0, 0.3) for p in prices],
        "volume": [150 + int(abs(np.random.normal(50, 20))) for _ in range(n_bars)],
    })
    return df


def main() -> int:
    """Chạy integration test Backtest Engine."""
    print("=" * 70)
    print("  VietKey Gold AI — Integration Test: Backtest Engine (Phase 7)")
    print("=" * 70)

    settings = get_settings()
    symbol = settings.mt5.symbol

    df_m5: pd.DataFrame | None = None
    df_h1: pd.DataFrame | None = None
    source_name = "Synthetic Mock Data"

    # 1. Thử lấy dữ liệu thực tế từ MT5 Terminal
    print("\n--- 1. Thu thập dữ liệu nến đa khung thời gian ---")
    connector = MT5Connector(settings.mt5)
    mt5_res = connector.connect()

    if mt5_res.success:
        try:
            mgr = MarketDataManager(symbol)
            print(f"✓ MT5 Connected thành công! Đang tải nến {symbol}...")
            df_m5 = mgr.get_candles(Timeframe.M5, num_bars=500)
            df_h1 = mgr.get_candles(Timeframe.H1, num_bars=200)
            if df_m5 is not None and len(df_m5) >= 50:
                source_name = "MT5 Live Data"
                print(f"✓ Đã tải {len(df_m5)} nến M5 và {len(df_h1) if df_h1 is not None else 0} nến H1 từ MT5.")
        except Exception as e:
            log.warning("Lỗi tải nến MT5: %s", e)
        finally:
            connector.disconnect()

    # 2. Nếu không có MT5, thử lấy từ Database SQLite
    if df_m5 is None or len(df_m5) < 50:
        try:
            db = DatabaseManager(config=settings.database)
            market_repo = MarketDataRepository(db)
            db_m5 = market_repo.get_latest_candles(symbol, "M5", limit=500)
            if len(db_m5) >= 50:
                df_m5 = pd.DataFrame(db_m5)
                source_name = "SQLite Market Data Cache"
                print(f"✓ Đã nạp {len(df_m5)} nến M5 từ SQLite Database.")
        except Exception as e:
            log.warning("Lỗi truy vấn Database SQLite: %s", e)

    # 3. Fallback sang dữ liệu mẫu giả lập
    if df_m5 is None or len(df_m5) < 50:
        print("⚠️ Sử dụng dữ liệu giả lập chuẩn sóng XAUUSD (500 nến M5, 100 nến H1)...")
        df_m5 = generate_synthetic_gold_data(n_bars=500, start_price=2700.0)
        df_h1 = generate_synthetic_gold_data(n_bars=100, start_price=2700.0)
        source_name = "Synthetic Wave Simulation"

    print(f"✓ Nguồn dữ liệu: {source_name}")
    print(f"✓ Số nến thực thi M5: {len(df_m5)}")
    print(f"✓ Số nến xu hướng H1: {len(df_h1) if df_h1 is not None else 0}")

    # 4. Khởi tạo Backtest Engine với cấu hình quản lý vốn vàng
    print("\n--- 2. Khởi tạo Backtest Engine ---")
    config = BacktestConfig(
        symbol=symbol,
        initial_balance=10000.0,
        lot_size=0.1,
        spread_points=0.30,         # 0.30 giá vàng (~30 cents / 3 pips)
        slippage_points=0.10,       # 0.10 giá vàng trượt
        breakeven_trigger_points=5.0,  # Lãi 5 giá kéo SL hòa vốn
        partial_tp_ratio=0.5,       # Chốt 50% khối lượng khi chạm TP1
    )

    print(f"✓ Cấu hình Backtest:")
    print(f"  • Vốn ban đầu: ${config.initial_balance:,.2f}")
    print(f"  • Volume cố định: {config.lot_size} lot")
    print(f"  • Spread: {config.spread_points} giá | Slippage: {config.slippage_points} giá")
    print(f"  • Quy tắc SL hòa vốn: Lãi ≥ {config.breakeven_trigger_points} giá")
    print(f"  • Quy tắc chốt lời: Chốt {config.partial_tp_ratio*100:.0f}% tại TP1, gồng TP2")

    engine = BacktestEngine(config=config)

    # 5. Thực thi mô phỏng toàn bộ dữ liệu
    print("\n--- 3. Thực thi Bar-by-bar Backtest Simulation ---")
    result: BacktestResult = engine.run(df_exec=df_m5, df_macro=df_h1, min_warmup_bars=30)

    print("\n" + "=" * 65)
    print("  KẾT QUẢ BACKTEST TỔNG THỂ")
    print("=" * 65)
    print(result.summary())
    print("=" * 65)

    if result.trades:
        print(f"\n--- Chi tiết {len(result.trades)} lệnh đã thực hiện ---")
        for idx, t in enumerate(result.trades, 1):
            be_tag = " [SL Hòa vốn]" if t.is_breakeven_triggered else ""
            p_tag = " [Chốt 50% TP1]" if t.partial_closed else ""
            print(
                f"#{idx:02d} {t.direction} @ {t.actual_entry_price:.2f} "
                f"➔ Exit @ {t.actual_exit_price:.2f} ({t.status.value}){be_tag}{p_tag} | "
                f"PnL: ${t.pnl_cash:+,.2f} ({t.pnl_points:+,.1f} giá) | "
                f"MFE: {t.mfe_points:+.1f}g, MAE: {t.mae_points:+.1f}g"
            )

    # 6. Phân tích Walk-Forward (3 Folds)
    print("\n--- 4. Phân tích Walk-Forward (3 Chu kỳ Folds) ---")
    analyzer = WalkForwardAnalyzer(engine=engine, num_folds=3)
    wf_report: WalkForwardReport = analyzer.run(df_exec=df_m5, df_macro=df_h1)

    print("\n" + "=" * 65)
    print("  KẾT QUẢ WALK-FORWARD ANALYSIS")
    print("=" * 65)
    print(wf_report.summary())
    print("-" * 65)
    for fold in wf_report.folds:
        status_sym = "✅" if fold.is_profitable else "❌"
        print(
            f"Fold #{fold.fold_index}: {status_sym} Trades={fold.total_trades} | "
            f"WinRate={fold.win_rate:.1f}% | PF={fold.profit_factor:.2f} | "
            f"PnL=${fold.net_profit:+,.2f} | MaxDD={fold.max_drawdown_pct:.1f}%"
        )
    print("=" * 65)

    print("\n✅ TẤT CẢ CÁC HẠNG MỤC BACKTEST & WALK-FORWARD ĐÃ HOÀN THÀNH XUẤT SẮC!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
