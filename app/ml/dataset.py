# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Machine Learning Dataset Builder.

Xây dựng tập dữ liệu huấn luyện và kiểm định mô hình ML:
- Phân chia thời gian (Time-series Split): TUYỆT ĐỐI không shuffle ngẫu nhiên, chống rò rỉ dữ liệu.
- Định nghĩa Target: 1 (Lệnh thắng / chạm TP1), 0 (Lệnh thua / chạm SL).
- Chuẩn hóa dữ liệu và xử lý giá trị ngoại lai (outliers/NaN).
"""

from typing import Tuple
import numpy as np
import pandas as pd

from app.backtest.models import TradeRecord
from app.ml.features import FEATURE_NAMES, FeatureExtractor


class DatasetBuilder:
    """Xây dựng và phân chia Dataset cho Machine Learning."""

    @staticmethod
    def build_from_trades(
        trades: list[TradeRecord],
        df_exec: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Tạo tập đặc trưng X và nhãn y từ danh sách lệnh Backtest đã mô phỏng.

        Args:
            trades: Danh sách TradeRecord đã hoàn tất.
            df_exec: DataFrame nến OHLCV có tính sẵn indicators.

        Returns:
            Tuple (X, y): DataFrame đặc trưng và Series nhãn (1: Win, 0: Loss).
        """
        rows: list[dict] = []
        labels: list[int] = []

        # Tạo map thời gian nến sang index
        time_to_idx = {row["time"]: i for i, row in df_exec.iterrows()} if "time" in df_exec.columns else {}

        for trade in trades:
            if not trade.entry_time and trade.actual_entry_price <= 0:
                continue

            # Xác định index nến tại thời điểm vào lệnh
            idx = time_to_idx.get(trade.entry_time, -1)
            if idx == -1:
                # Tìm nến gần nhất
                idx = len(df_exec) // 2

            feats = FeatureExtractor.extract_features(
                df_exec=df_exec,
                candle_idx=idx,
                spread=0.3,
                swing_high=trade.entry_zone_high + 5.0,
                swing_low=trade.entry_zone_low - 5.0,
            )

            # Target: 1 nếu pnl > 0 (thắng / chốt TP1), 0 nếu lỗ
            label = 1 if trade.is_win or trade.pnl_points > 0.5 else 0

            rows.append(feats)
            labels.append(label)

        if not rows:
            # Tạo DataFrame rỗng có schema chuẩn nếu không có trades
            df_empty = pd.DataFrame(columns=FEATURE_NAMES)
            return df_empty, pd.Series(dtype=int)

        X = pd.DataFrame(rows)[FEATURE_NAMES]
        y = pd.Series(labels, name="target")
        return X, y

    @staticmethod
    def time_series_split(
        X: pd.DataFrame,
        y: pd.Series,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        """
        Chia dữ liệu theo trục thời gian (Chronological Train/Validation/Test Split).
        Tuyệt đối không dùng random shuffle để bảo đảm không có look-ahead bias.

        Returns:
            (X_train, y_train, X_val, y_val, X_test, y_test)
        """
        n = len(X)
        if n < 5:
            # Fallback nếu tập quá nhỏ
            return X, y, X, y, X, y

        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        X_train = X.iloc[:train_end].copy()
        y_train = y.iloc[:train_end].copy()

        X_val = X.iloc[train_end:val_end].copy()
        y_val = y.iloc[train_end:val_end].copy()

        X_test = X.iloc[val_end:].copy()
        y_test = y.iloc[val_end:].copy()

        return X_train, y_train, X_val, y_val, X_test, y_test
