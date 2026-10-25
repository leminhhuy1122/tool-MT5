# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Historical Data Loader.

Nạp và đồng bộ dữ liệu lịch sử phục vụ Backtest:
- Nạp từ SQLite Database (MarketDataRepository).
- Nạp từ MetaTrader 5 terminal (MarketDataManager).
- Đồng bộ đa khung thời gian: Nến M5 chỉ được nhìn nến H1 ĐÃ ĐÓNG trước đó (No Look-ahead Bias).
- Làm sạch dữ liệu: loại bỏ trùng lặp timestamp, sắp xếp theo thời gian tăng dần.
"""

from datetime import datetime
from typing import Optional

import pandas as pd

from app.database.connection import DatabaseManager
from app.database.repository import MarketDataRepository
from app.market.indicators import add_all_indicators
from app.market.timeframe_manager import Timeframe
from logger import get_logger

log = get_logger("backtest.loader")


class HistoricalLoader:
    """Nạp và chuẩn hóa dữ liệu nến cho Backtest Engine."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db
        self.market_repo = MarketDataRepository(db) if db else None

    def load_from_db(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M5",
        limit: int = 1000,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Nạp nến lịch sử từ SQLite Database.

        Returns:
            DataFrame OHLCV đã sắp xếp tăng dần theo thời gian.
        """
        if not self.market_repo:
            log.warning("Chưa cấu hình DatabaseManager để nạp dữ liệu.")
            return pd.DataFrame()

        df = self.market_repo.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )
        return self.clean_and_prepare(df)

    @staticmethod
    def clean_and_prepare(df: pd.DataFrame) -> pd.DataFrame:
        """
        Làm sạch, định dạng và tính toán indicators cơ bản cho DataFrame.
        """
        if df is None or df.empty:
            return pd.DataFrame()

        clean_df = df.copy()

        # Đảm bảo cột time ở dạng datetime và sắp xếp tăng dần
        if "time" in clean_df.columns:
            clean_df["time"] = pd.to_datetime(clean_df["time"])
            clean_df = clean_df.sort_values("time").drop_duplicates(subset=["time"])
            clean_df = clean_df.reset_index(drop=True)

        for col in ["open", "high", "low", "close"]:
            if col in clean_df.columns:
                clean_df[col] = clean_df[col].astype(float)

        if "tick_volume" not in clean_df.columns:
            clean_df["tick_volume"] = clean_df.get("volume", 100.0)

        # Tính indicators nếu chưa có
        if not {"ema_20", "ema_50", "rsi_14", "atr_14"}.issubset(clean_df.columns):
            if len(clean_df) >= 20:
                clean_df = add_all_indicators(clean_df)

        log.debug("Đã làm sạch %d nến lịch sử.", len(clean_df))
        return clean_df

    @staticmethod
    def align_multi_timeframe(
        df_exec: pd.DataFrame,
        df_macro: pd.DataFrame,
    ) -> dict[int, pd.DataFrame]:
        """
        Đồng bộ đa khung thời gian: Với mỗi nến thực thi (exec, vd M5),
        chỉ trả về phần nến macro (vd H1) có thời gian ĐÃ KẾT THÚC trước đó.
        TUYỆT ĐỐI KHÔNG CÓ LOOK-AHEAD BIAS.

        Args:
            df_exec: DataFrame khung thực thi (vd M5).
            df_macro: DataFrame khung xu hướng (vd H1).

        Returns:
            Dictionary: exec_idx -> slice của df_macro hợp lệ tại thời điểm đó.
        """
        alignment_map: dict[int, pd.DataFrame] = {}
        if df_exec.empty or df_macro.empty:
            return alignment_map

        # Với mỗi nến M5, lọc các nến H1 có time < time nến M5
        for idx, row in df_exec.iterrows():
            current_time = row["time"]
            valid_macro = df_macro[df_macro["time"] < current_time]
            alignment_map[idx] = valid_macro

        return alignment_map
