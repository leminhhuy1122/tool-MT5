# -*- coding: utf-8 -*-
"""
VietKey Gold AI — SMC Analysis Tests.

Kiểm tra toàn diện module đọc biểu đồ Smart Money Concepts (SMC):
- Fair Value Gap (FVG) / Imbalance detection.
- Order Block (OB) detection & mitigation.
- Liquidity Sweep (BSL / SSL) detection.
- Discount / Premium zone calculation.
- compute_gold_sl_tp: đảm bảo SL 10-12 giá, TP1 10-12 giá, TP2 20-24 giá.
"""

import numpy as np
import pandas as pd
import pytest

from app.market.market_structure import SwingPoint, SwingType
from app.market.smc import (
    FVGType,
    OBType,
    PriceZone,
    SweepType,
    analyze_smc,
    calculate_discount_premium,
    detect_fvgs,
    detect_liquidity_sweeps,
    detect_order_blocks,
)
from app.strategy.setup_detector import compute_gold_sl_tp


def _create_sample_candles(n: int = 50, base_price: float = 2000.0) -> pd.DataFrame:
    """Tạo chuỗi nến mẫu cho test."""
    times = pd.date_range("2026-01-01", periods=n, freq="5min")
    np.random.seed(42)
    closes = base_price + np.cumsum(np.random.randn(n) * 2.0)
    highs = closes + np.random.uniform(0.5, 3.0, n)
    lows = closes - np.random.uniform(0.5, 3.0, n)
    opens = (highs + lows) / 2.0

    return pd.DataFrame({
        "time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.randint(100, 1000, n),
    })


def test_fvg_detection_bullish():
    """Kiểm tra nhận diện Bullish Fair Value Gap (Khoảng trống giá tăng)."""
    # Nến 0: High = 2000
    # Nến 1: Nến tăng mạnh
    # Nến 2: Low = 2005 -> Gap = [2000, 2005], size = 5.0
    df = pd.DataFrame([
        {"time": pd.Timestamp("2026-01-01 00:00"), "open": 1995.0, "high": 2000.0, "low": 1990.0, "close": 1998.0, "volume": 100},
        {"time": pd.Timestamp("2026-01-01 00:05"), "open": 1998.0, "high": 2020.0, "low": 1997.0, "close": 2018.0, "volume": 500},
        {"time": pd.Timestamp("2026-01-01 00:10"), "open": 2018.0, "high": 2025.0, "low": 2005.0, "close": 2022.0, "volume": 200},
    ])

    fvgs = detect_fvgs(df, min_gap_pts=1.0)
    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.fvg_type == FVGType.BULLISH
    assert fvg.bottom == 2000.0
    assert fvg.top == 2005.0
    assert fvg.size == 5.0
    assert fvg.midpoint == 2002.5
    assert not fvg.is_mitigated


def test_fvg_detection_bearish():
    """Kiểm tra nhận diện Bearish Fair Value Gap (Khoảng trống giá giảm)."""
    # Nến 0: Low = 2050
    # Nến 1: Nến giảm mạnh
    # Nến 2: High = 2042 -> Gap = [2042, 2050], size = 8.0
    df = pd.DataFrame([
        {"time": pd.Timestamp("2026-01-01 00:00"), "open": 2055.0, "high": 2060.0, "low": 2050.0, "close": 2052.0, "volume": 100},
        {"time": pd.Timestamp("2026-01-01 00:05"), "open": 2052.0, "high": 2053.0, "low": 2030.0, "close": 2032.0, "volume": 500},
        {"time": pd.Timestamp("2026-01-01 00:10"), "open": 2032.0, "high": 2042.0, "low": 2025.0, "close": 2028.0, "volume": 200},
    ])

    fvgs = detect_fvgs(df, min_gap_pts=1.0)
    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.fvg_type == FVGType.BEARISH
    assert fvg.bottom == 2042.0
    assert fvg.top == 2050.0
    assert fvg.size == 8.0
    assert fvg.midpoint == 2046.0


def test_order_block_detection():
    """Kiểm tra nhận diện Bullish & Bearish Order Block."""
    # Thêm 2 nến đệm trước đó để len(df) >= 5
    df = pd.DataFrame([
        {"time": pd.Timestamp("2026-01-01 00:00"), "open": 2008.0, "high": 2010.0, "low": 2007.0, "close": 2009.0, "volume": 100},
        {"time": pd.Timestamp("2026-01-01 00:05"), "open": 2009.0, "high": 2011.0, "low": 2008.0, "close": 2010.0, "volume": 100},
        {"time": pd.Timestamp("2026-01-01 00:10"), "open": 2010.0, "high": 2012.0, "low": 2004.0, "close": 2005.0, "volume": 150},
        {"time": pd.Timestamp("2026-01-01 00:15"), "open": 2005.0, "high": 2025.0, "low": 2005.0, "close": 2024.0, "volume": 800},
        {"time": pd.Timestamp("2026-01-01 00:20"), "open": 2024.0, "high": 2030.0, "low": 2018.0, "close": 2028.0, "volume": 400},
        {"time": pd.Timestamp("2026-01-01 00:25"), "open": 2028.0, "high": 2032.0, "low": 2026.0, "close": 2030.0, "volume": 300},
    ])

    obs = detect_order_blocks(df, lookback_bars=10)
    assert len(obs) >= 1
    ob = obs[0]
    assert ob.ob_type == OBType.BULLISH
    assert ob.low == 2004.0
    assert ob.high == 2012.0
    assert ob.midpoint == 2008.0
    assert not ob.is_mitigated


def test_liquidity_sweep_bsl():
    """Kiểm tra nhận diện quét thanh khoản đỉnh (BSL Sweep)."""
    swings = [
        SwingPoint(index=5, price=2050.0, swing_type=SwingType.SWING_HIGH),
    ]
    rows = []
    for i in range(10):
        rows.append({
            "time": pd.Timestamp(f"2026-01-01 0{i}:00"),
            "open": 2035.0,
            "high": 2045.0,
            "low": 2030.0,
            "close": 2036.0,
            "volume": 100,
        })
    # Nến quét đỉnh tại index 10: High = 2053.0 (vượt 2050.0), Close = 2048.5 (dưới 2050.0)
    rows.append({
        "time": pd.Timestamp("2026-01-01 00:50"),
        "open": 2047.0,
        "high": 2053.0,
        "low": 2046.0,
        "close": 2048.5,
        "volume": 600,
    })
    df = pd.DataFrame(rows)

    sweeps = detect_liquidity_sweeps(df, swings=swings)
    assert len(sweeps) >= 1
    sweep = sweeps[-1]
    assert sweep.sweep_type == SweepType.BSL_SWEEP
    assert sweep.swept_level == 2050.0
    assert sweep.extreme_price == 2053.0
    assert sweep.wick_distance == pytest.approx(3.0, rel=1e-2)


def test_discount_premium_equilibrium():
    """Kiểm tra tính toán vùng Discount / Premium và 50% Equilibrium."""
    # Nến từ 2000 đến 2100 -> Equilibrium 2050
    # Nến cuối đóng ở 2020 -> DISCOUNT
    df_discount = pd.DataFrame([
        {"time": pd.Timestamp("2026-01-01 00:00"), "open": 2000.0, "high": 2100.0, "low": 2000.0, "close": 2020.0, "volume": 100},
    ] * 15)
    dp = calculate_discount_premium(df_discount)
    assert dp is not None
    assert dp.equilibrium == 2050.0
    assert dp.zone == "DISCOUNT"
    assert dp.percent_in_range == 20.0

    # Nến cuối đóng ở 2080 -> PREMIUM
    df_premium = pd.DataFrame([
        {"time": pd.Timestamp("2026-01-01 00:00"), "open": 2000.0, "high": 2100.0, "low": 2000.0, "close": 2080.0, "volume": 100},
    ] * 15)
    dp2 = calculate_discount_premium(df_premium)
    assert dp2 is not None
    assert dp2.zone == "PREMIUM"
    assert dp2.percent_in_range == 80.0


def test_compute_gold_sl_tp_rule():
    """
    Quy tắc tính SL/TP động theo Cấu Trúc Kháng Cự & Hỗ Trợ Đỉnh/Đáy:
    - SL BUY: Đặt dưới đáy hỗ trợ + 0.8 giá đệm (tối thiểu 3.0 giá, tối đa 8.0 giá).
    - SL SELL: Đặt trên đỉnh kháng cự + 0.8 giá đệm (tối thiểu 3.0 giá, tối đa 8.0 giá).
    - TP1: Đặt trước vùng cản đối diện hoặc đạt tối thiểu 1.5R.
    - TP2: Đón trọn con sóng tại 2.5R.
    """
    # 1. Test lệnh BUY với đáy hỗ trợ cách 3.5 giá
    entry_buy = 2050.0
    structure_low = 2046.5  # Cách 3.5 giá
    opp_high = 2058.0       # Đỉnh kháng cự cách 8.0 giá
    sl, tp1, tp2 = compute_gold_sl_tp("BUY", entry_buy, structure_level=structure_low, opposite_target=opp_high, atr=2.5)
    sl_dist = round(abs(entry_buy - sl), 2)
    tp1_dist = round(abs(tp1 - entry_buy), 2)
    tp2_dist = round(abs(tp2 - entry_buy), 2)

    # raw_dist = (2050 - 2046.5) + 0.8 = 4.3 giá
    assert sl_dist == 4.3, f"SL BUY {sl_dist} phải bằng 4.3 giá"
    # tp1 đặt trước cản 2058 - 0.5 = 2057.5 (+7.5 giá)
    assert tp1 == 2057.5, f"TP1 BUY {tp1} phải chốt trước cản 2057.5"
    assert tp2_dist >= sl_dist * 2.0, f"TP2 BUY {tp2_dist} phải >= 2.0R"

    # 2. Test lệnh SELL với đỉnh kháng cự cách 4.0 giá
    entry_sell = 2050.0
    structure_high = 2054.0  # Cách 4.0 giá
    opp_low = 2040.0         # Đáy hỗ trợ cách 10.0 giá
    sl_s, tp1_s, tp2_s = compute_gold_sl_tp("SELL", entry_sell, structure_level=structure_high, opposite_target=opp_low, atr=3.0)
    sl_dist_s = round(abs(sl_s - entry_sell), 2)
    tp1_dist_s = round(abs(entry_sell - tp1_s), 2)
    tp2_dist_s = round(abs(entry_sell - tp2_s), 2)

    # raw_dist = (2054 - 2050) + 0.8 = 4.8 giá
    assert sl_dist_s == 4.8, f"SL SELL {sl_dist_s} phải bằng 4.8 giá"
    assert tp1_s < entry_sell
    assert tp2_dist_s >= sl_dist_s * 2.0


def test_analyze_smc_comprehensive():
    """Kiểm tra hàm tổng hợp analyze_smc chạy mượt mà trên dữ liệu mẫu."""
    df = _create_sample_candles(60, base_price=2030.0)
    result = analyze_smc(df)
    assert result is not None
    assert isinstance(result.unmitigated_fvgs, list)
    assert isinstance(result.unmitigated_obs, list)
    assert isinstance(result.liquidity_sweeps, list)
    assert result.price_zone is not None
