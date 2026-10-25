# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Market Data Manager.

Lấy và chuẩn hóa dữ liệu thị trường từ MetaTrader 5:
- Historical candles (OHLCV).
- Data validation.
- Không sử dụng dữ liệu tương lai.
- Kiểm tra nến chưa đóng.
- Cache trong bộ nhớ (giới hạn để tiết kiệm RAM).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from app.market.timeframe_manager import Timeframe, DEFAULT_BAR_COUNTS
from logger import get_logger

log = get_logger("market.data")


# ──────────────────────────────────────────────
# Data validation results
# ──────────────────────────────────────────────
@dataclass
class DataQuality:
    """Kết quả kiểm tra chất lượng dữ liệu."""

    total_bars: int = 0
    missing_bars: int = 0
    duplicate_timestamps: int = 0
    future_bars: int = 0
    invalid_ohlc: int = 0
    has_unclosed_bar: bool = False

    @property
    def is_valid(self) -> bool:
        """Dữ liệu có đạt chất lượng tối thiểu không."""
        return (
            self.total_bars > 0
            and self.duplicate_timestamps == 0
            and self.future_bars == 0
            and self.invalid_ohlc == 0
        )

    @property
    def issues(self) -> list[str]:
        """Danh sách vấn đề phát hiện."""
        problems: list[str] = []
        if self.total_bars == 0:
            problems.append("Không có dữ liệu")
        if self.duplicate_timestamps > 0:
            problems.append(f"{self.duplicate_timestamps} timestamp trùng")
        if self.future_bars > 0:
            problems.append(f"{self.future_bars} nến tương lai")
        if self.invalid_ohlc > 0:
            problems.append(f"{self.invalid_ohlc} nến OHLC không hợp lệ")
        if self.missing_bars > 0:
            problems.append(f"~{self.missing_bars} nến thiếu (ước tính)")
        if self.has_unclosed_bar:
            problems.append("Có nến chưa đóng (đã loại bỏ)")
        return problems


# ──────────────────────────────────────────────
# Market Data Manager
# ──────────────────────────────────────────────
class MarketDataManager:
    """
    Quản lý dữ liệu thị trường.

    Sử dụng:
        manager = MarketDataManager(symbol="XAUUSD")
        df = manager.get_candles(Timeframe.H1, num_bars=200)
        quality = manager.validate(df, Timeframe.H1)
    """

    def __init__(self, symbol: str = "XAUUSD") -> None:
        """
        Khởi tạo data manager.

        Args:
            symbol: Symbol cần lấy dữ liệu.
        """
        self._symbol = symbol
        self._cache: dict[Timeframe, pd.DataFrame] = {}

    @property
    def symbol(self) -> str:
        return self._symbol

    def get_candles(
        self,
        timeframe: Timeframe,
        num_bars: Optional[int] = None,
        include_unclosed: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Lấy historical candles từ MT5.

        Args:
            timeframe: Khung thời gian.
            num_bars: Số nến cần lấy. None = dùng default.
            include_unclosed: Có giữ nến chưa đóng không.
                              Mặc định False (loại bỏ nến hiện tại).

        Returns:
            DataFrame với columns: time, open, high, low, close, tick_volume, spread.
            None nếu lỗi.
        """
        if num_bars is None:
            num_bars = DEFAULT_BAR_COUNTS.get(timeframe, 200)

        log.debug(
            "Lấy %d nến %s %s...", num_bars, self._symbol, timeframe.label
        )

        # Lấy thêm 1 nến (nến hiện tại chưa đóng) để có thể loại bỏ
        fetch_count = num_bars + 1 if not include_unclosed else num_bars

        rates = mt5.copy_rates_from_pos(
            self._symbol,
            timeframe.mt5_const,
            0,  # bắt đầu từ nến hiện tại
            fetch_count,
        )

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            log.error(
                "Không lấy được dữ liệu %s %s: %s",
                self._symbol, timeframe.label, error,
            )
            return None

        # Chuyển sang DataFrame
        df = pd.DataFrame(rates)

        # Chuyển timestamp sang datetime UTC
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

        # Loại bỏ nến chưa đóng (nến cuối cùng = nến hiện tại)
        if not include_unclosed and len(df) > num_bars:
            df = df.iloc[:-1].copy()

        # Giữ columns cần thiết, đổi tên cho rõ ràng
        columns_map = {
            "time": "time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "tick_volume": "tick_volume",
            "spread": "spread",
        }
        # Chỉ giữ columns tồn tại
        existing_cols = [c for c in columns_map if c in df.columns]
        df = df[existing_cols].copy()

        # Set index
        df = df.set_index("time", drop=False)
        df.index.name = "datetime"

        # Cache
        self._cache[timeframe] = df

        log.info(
            "✓ %s %s: %d nến | %s → %s",
            self._symbol, timeframe.label, len(df),
            df["time"].iloc[0].strftime("%Y-%m-%d %H:%M"),
            df["time"].iloc[-1].strftime("%Y-%m-%d %H:%M"),
        )

        return df

    def get_multiple_timeframes(
        self,
        timeframes: Optional[list[Timeframe]] = None,
    ) -> dict[Timeframe, pd.DataFrame]:
        """
        Lấy dữ liệu nhiều timeframe cùng lúc.

        Args:
            timeframes: Danh sách timeframes. None = dùng default (H4,H1,M15,M5).

        Returns:
            Dictionary {timeframe: DataFrame}.
        """
        from app.market.timeframe_manager import DEFAULT_TIMEFRAMES

        if timeframes is None:
            timeframes = DEFAULT_TIMEFRAMES

        result: dict[Timeframe, pd.DataFrame] = {}

        for tf in timeframes:
            df = self.get_candles(tf)
            if df is not None:
                result[tf] = df
            else:
                log.warning("Không lấy được dữ liệu %s", tf.label)

        log.info(
            "Đã lấy %d/%d timeframes cho %s",
            len(result), len(timeframes), self._symbol,
        )
        return result

    def validate(
        self, df: pd.DataFrame, timeframe: Timeframe
    ) -> DataQuality:
        """
        Kiểm tra chất lượng dữ liệu.

        Args:
            df: DataFrame cần kiểm tra.
            timeframe: Timeframe tương ứng.

        Returns:
            DataQuality với chi tiết các vấn đề.
        """
        quality = DataQuality()

        if df is None or df.empty:
            log.warning("Dữ liệu rỗng cho %s", timeframe.label)
            return quality

        quality.total_bars = len(df)

        # 1. Kiểm tra timestamp trùng
        time_col = df["time"]
        duplicates = time_col.duplicated().sum()
        quality.duplicate_timestamps = int(duplicates)

        # 2. Kiểm tra nến tương lai
        now_utc = datetime.now(timezone.utc)
        future_mask = time_col > now_utc
        quality.future_bars = int(future_mask.sum())

        # 3. Kiểm tra OHLC hợp lệ
        # High >= Open, Close, Low; Low <= Open, Close, High
        invalid_mask = (
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["high"] < df["low"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"])
        )
        quality.invalid_ohlc = int(invalid_mask.sum())

        # 4. Ước tính nến thiếu (dựa trên khoảng cách thời gian)
        if len(df) >= 2:
            time_diffs = time_col.diff().dropna()
            expected_delta = pd.Timedelta(minutes=timeframe.minutes)
            # Nến thiếu = tổng khoảng cách lớn hơn 2x expected
            gaps = time_diffs[time_diffs > expected_delta * 2]
            if not gaps.empty:
                estimated_missing = sum(
                    int(gap / expected_delta) - 1 for gap in gaps
                )
                quality.missing_bars = max(0, estimated_missing)

        # Log kết quả
        if quality.is_valid:
            log.debug(
                "✓ Data quality %s: %d bars, valid",
                timeframe.label, quality.total_bars,
            )
        else:
            log.warning(
                "⚠ Data quality %s: %s",
                timeframe.label, ", ".join(quality.issues),
            )

        return quality

    def get_latest_price(self) -> Optional[dict]:
        """
        Lấy giá hiện tại (bid/ask/spread).

        Returns:
            Dictionary với bid, ask, spread, time. None nếu lỗi.
        """
        tick = mt5.symbol_info_tick(self._symbol)
        if tick is None:
            log.error("Không lấy được tick %s", self._symbol)
            return None

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(tick.ask - tick.bid, 2),
            "last": tick.last,
            "volume": tick.volume,
            "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
        }

    def clear_cache(self) -> None:
        """Xóa cache để giải phóng RAM."""
        count = len(self._cache)
        self._cache.clear()
        if count:
            log.debug("Đã xóa cache %d timeframes", count)

    def get_cached(self, timeframe: Timeframe) -> Optional[pd.DataFrame]:
        """Lấy dữ liệu từ cache (nếu có)."""
        return self._cache.get(timeframe)
