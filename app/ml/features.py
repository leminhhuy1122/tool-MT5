# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Feature Engineering.

Trích xuất các đặc trưng kỹ thuật có ý nghĩa cho mô hình học máy:
- Chỉ báo xung lượng & xu hướng: RSI(14), EMA ratios (Close/EMA20, EMA20/EMA50, EMA50/EMA200).
- Biến động & Phí: ATR(14), Spread tương đối, tỷ lệ Spread / ATR.
- Hình thái nến: Body ratio, râu trên, râu dưới, biên độ giá.
- Cấu trúc thị trường & Vùng cản: Khoảng cách tới Swing High/Low gần nhất.
- Khung thời gian lớn: Mã hóa xu hướng H4, H1.
- Phiên giao dịch (Session): Asian, London, New York.
"""

from typing import Any, Optional
import numpy as np
import pandas as pd


FEATURE_NAMES = [
    "rsi_14",
    "close_ema20_ratio",
    "close_ema50_ratio",
    "ema20_ema50_ratio",
    "atr_14",
    "spread_atr_ratio",
    "candle_body_ratio",
    "upper_shadow_ratio",
    "lower_shadow_ratio",
    "dist_swing_high",
    "dist_swing_low",
    "h4_trend_encoded",
    "h1_trend_encoded",
    "hour_of_day",
]


class FeatureExtractor:
    """Bộ trích xuất đặc trưng cho tín hiệu giao dịch."""

    @staticmethod
    def extract_features(
        df_exec: pd.DataFrame,
        candle_idx: int = -1,
        spread: float = 0.3,
        h4_trend: str = "NEUTRAL",
        h1_trend: str = "NEUTRAL",
        swing_high: Optional[float] = None,
        swing_low: Optional[float] = None,
    ) -> dict[str, float]:
        """
        Trích xuất vector đặc trưng tại nến xác định (không nhìn trước tương lai).
        """
        if candle_idx < 0:
            idx = len(df_exec) + candle_idx
        else:
            idx = candle_idx

        idx = max(0, min(len(df_exec) - 1, idx))
        row = df_exec.iloc[idx]

        c_open = float(row["open"])
        c_high = float(row["high"])
        c_low = float(row["low"])
        c_close = float(row["close"])
        candle_range = max(0.01, c_high - c_low)
        body = abs(c_close - c_open)

        # 1. RSI
        rsi_14 = float(row.get("rsi", 50.0))
        if np.isnan(rsi_14):
            rsi_14 = 50.0

        # 2. EMAs
        ema_20 = float(row.get("ema_fast", row.get("ema_20", c_close)))
        ema_50 = float(row.get("ema_mid", row.get("ema_50", c_close)))
        ema_200 = float(row.get("ema_slow", row.get("ema_200", c_close)))

        close_ema20_ratio = (c_close / ema_20 - 1.0) * 100.0 if ema_20 > 0 else 0.0
        close_ema50_ratio = (c_close / ema_50 - 1.0) * 100.0 if ema_50 > 0 else 0.0
        ema20_ema50_ratio = (ema_20 / ema_50 - 1.0) * 100.0 if ema_50 > 0 else 0.0

        # 3. ATR & Spread
        atr_14 = float(row.get("atr", 2.5))
        if np.isnan(atr_14) or atr_14 <= 0:
            atr_14 = 2.5
        spread_atr_ratio = spread / atr_14

        # 4. Hình thái nến
        candle_body_ratio = body / candle_range
        upper_shadow = c_high - max(c_open, c_close)
        lower_shadow = min(c_open, c_close) - c_low
        upper_shadow_ratio = upper_shadow / candle_range
        lower_shadow_ratio = lower_shadow / candle_range

        # 5. Cấu trúc khoảng cách swing
        dist_swing_high = (float(swing_high) - c_close) if swing_high is not None else 5.0
        dist_swing_low = (c_close - float(swing_low)) if swing_low is not None else 5.0

        # 6. Mã hóa xu hướng H4/H1: BULLISH = 1, BEARISH = -1, NEUTRAL = 0
        def encode_trend(t: str) -> float:
            t_upper = str(t).upper()
            if "BULL" in t_upper:
                return 1.0
            if "BEAR" in t_upper:
                return -1.0
            return 0.0

        h4_encoded = encode_trend(h4_trend)
        h1_encoded = encode_trend(h1_trend)

        # 7. Giờ trong ngày
        hour = 12.0
        if "time" in row:
            t = row["time"]
            if hasattr(t, "hour"):
                hour = float(t.hour)

        return {
            "rsi_14": round(rsi_14, 2),
            "close_ema20_ratio": round(close_ema20_ratio, 3),
            "close_ema50_ratio": round(close_ema50_ratio, 3),
            "ema20_ema50_ratio": round(ema20_ema50_ratio, 3),
            "atr_14": round(atr_14, 2),
            "spread_atr_ratio": round(spread_atr_ratio, 3),
            "candle_body_ratio": round(candle_body_ratio, 3),
            "upper_shadow_ratio": round(upper_shadow_ratio, 3),
            "lower_shadow_ratio": round(lower_shadow_ratio, 3),
            "dist_swing_high": round(dist_swing_high, 2),
            "dist_swing_low": round(dist_swing_low, 2),
            "h4_trend_encoded": h4_encoded,
            "h1_trend_encoded": h1_encoded,
            "hour_of_day": hour,
        }
