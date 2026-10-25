# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Integration Test: Technical Analysis.

Chạy phân tích kỹ thuật trên dữ liệu XAUUSD thật từ MT5.

Cách chạy:
    venv/Scripts/activate  (Windows)
    python tests/integration_analysis.py
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
from app.market.market_structure import analyze_market_structure
from app.market.volatility import analyze_volatility


def main() -> None:
    """Chạy integration test Technical Analysis."""
    settings = get_settings()
    setup_logging(log_level="INFO")
    log = get_logger("integration_analysis")

    log.info("=" * 60)
    log.info("  INTEGRATION TEST — Technical Analysis Engine")
    log.info("=" * 60)

    connector = MT5Connector(settings.mt5)
    result = connector.connect()
    if not result.success:
        log.error("Không thể kết nối MT5.")
        return

    try:
        symbol = settings.mt5.symbol
        mgr = MarketDataManager(symbol)
        results: dict[str, str] = {}

        for tf in [Timeframe.H4, Timeframe.H1, Timeframe.M15]:
            log.info("\n" + "─" * 50)
            log.info("  PHÂN TÍCH %s %s", symbol, tf.label)
            log.info("─" * 50)

            # 1. Lấy dữ liệu
            df = mgr.get_candles(tf, num_bars=200)
            if df is None:
                results[f"{tf.label}"] = "✗ FAIL — không lấy được dữ liệu"
                continue

            # 2. Indicators
            df_ind = add_all_indicators(df)
            last = df_ind.iloc[-1]
            log.info(
                "  EMA20=%.2f | EMA50=%.2f | RSI=%.1f | ATR=%.2f",
                last.get("ema_20", 0), last.get("ema_50", 0),
                last.get("rsi_14", 0), last.get("atr_14", 0),
            )

            # 3. Market Structure
            structure = analyze_market_structure(df, left_bars=3, right_bars=3)
            log.info(
                "  Trend: %s | Swings: %d | Events: %d | S/R: %d",
                structure.trend.value,
                len(structure.swings),
                len(structure.structure_events),
                len(structure.sr_zones),
            )

            # 4. Volatility
            vol = analyze_volatility(df)
            if vol:
                log.info(
                    "  Volatility: %s | ATR ratio: %.1f%% | Spread high: %s",
                    vol.level.value, vol.atr_ratio * 100, vol.is_spread_high,
                )

            results[f"{tf.label}"] = (
                f"✓ PASS | Trend={structure.trend.value} | "
                f"RSI={last.get('rsi_14', 0):.1f} | Vol={vol.level.value if vol else 'N/A'}"
            )

    finally:
        connector.disconnect()

    # Kết quả
    log.info("\n" + "=" * 60)
    log.info("  KẾT QUẢ INTEGRATION TEST — TECHNICAL ANALYSIS")
    log.info("=" * 60)
    for tf_name, status in results.items():
        log.info("  %s: %s", tf_name, status)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
