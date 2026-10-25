# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Repositories.

Cung cấp các lớp truy xuất và thao tác dữ liệu (Data Access Layer / Repository):
- SignalRepository: Lưu, cập nhật và truy vấn tín hiệu giao dịch, features, outcomes.
- MarketDataRepository: Lưu và truy vấn nến OHLCV đa khung thời gian.
- StrategyRepository: Quản lý các phiên bản chiến lược.
"""

from datetime import datetime, timezone
import json
from typing import Optional

import pandas as pd

from app.database.connection import DatabaseManager
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from logger import get_logger

log = get_logger("database.repository")


class SignalRepository:
    """Repository quản lý tín hiệu giao dịch, features và outcomes."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def save_signal(
        self,
        signal: TradingSignal,
        features: Optional[dict] = None,
    ) -> bool:
        """
        Lưu tín hiệu mới vào bảng signals (kèm features nếu có).

        Args:
            signal: TradingSignal instance.
            features: Dictionary các chỉ số kỹ thuật lúc phát tín hiệu.

        Returns:
            True nếu lưu thành công.
        """
        created = signal.created_at
        if created and created.tzinfo is not None:
            created_str = created.isoformat()
        else:
            created_str = datetime.now(timezone.utc).isoformat()

        expires_str = signal.expires_at.isoformat() if signal.expires_at else None
        reasons_json = json.dumps(signal.reasons, ensure_ascii=False)

        sql_signal = """
        INSERT OR REPLACE INTO signals (
            signal_id, strategy_version, symbol, timeframe, direction, status,
            entry_price, entry_zone_low, entry_zone_high, stop_loss,
            take_profit_1, take_profit_2, risk_reward_ratio, sl_distance,
            tp_distance, score, confidence, setup_type, reasons,
            invalidation, trend_h4, trend_h1, created_at, expires_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        params = (
            signal.signal_id,
            signal.strategy_version,
            signal.symbol,
            signal.timeframe,
            signal.direction.value,
            signal.status.value,
            float(signal.entry_price),
            float(signal.entry_zone_low),
            float(signal.entry_zone_high),
            float(signal.stop_loss),
            float(signal.take_profit_1),
            float(signal.take_profit_2),
            float(signal.risk_reward_ratio),
            float(signal.sl_distance),
            float(signal.tp_distance),
            float(signal.score),
            signal.confidence,
            signal.setup_type,
            reasons_json,
            signal.invalidation,
            signal.trend_h4,
            signal.trend_h1,
            created_str,
            expires_str,
            created_str,
        )

        with self.db.session() as conn:
            conn.execute(sql_signal, params)

            # Lưu features nếu có
            if features:
                sql_feat = """
                INSERT INTO signal_features (
                    signal_id, rsi_14, ema_20, ema_50, ema_200, atr_14,
                    spread, volatility_level, body_ratio, candle_range,
                    swing_high, swing_low
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                feat_params = (
                    signal.signal_id,
                    features.get("rsi_14"),
                    features.get("ema_20"),
                    features.get("ema_50"),
                    features.get("ema_200"),
                    features.get("atr_14"),
                    features.get("spread"),
                    features.get("volatility_level"),
                    features.get("body_ratio"),
                    features.get("candle_range"),
                    features.get("swing_high"),
                    features.get("swing_low"),
                )
                conn.execute(sql_feat, feat_params)

        log.debug("Đã lưu tín hiệu [%s] vào database.", signal.signal_id)
        return True

    def update_status(
        self,
        signal_id: str,
        status: SignalStatus,
        updated_at: Optional[datetime] = None,
    ) -> bool:
        """
        Cập nhật trạng thái của tín hiệu.

        Args:
            signal_id: ID tín hiệu.
            status: Trạng thái mới.
            updated_at: Thời điểm cập nhật.

        Returns:
            True nếu cập nhật thành công ít nhất 1 dòng.
        """
        now_str = (updated_at or datetime.now(timezone.utc)).isoformat()
        sql = "UPDATE signals SET status = ?, updated_at = ? WHERE signal_id = ?;"

        with self.db.session() as conn:
            cursor = conn.execute(sql, (status.value, now_str, signal_id))
            updated = cursor.rowcount > 0

        if updated:
            log.debug("Đã cập nhật trạng thái [%s] -> %s", signal_id, status.value)
        return updated

    def save_outcome(
        self,
        signal_id: str,
        final_status: str,
        entry_hit_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        pnl_points: Optional[float] = None,
        pnl_r: Optional[float] = None,
        entry_time: Optional[datetime] = None,
        exit_time: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
        max_favorable_excursion: Optional[float] = None,
        max_adverse_excursion: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Lưu kết quả giao dịch thực tế vào bảng signal_outcomes.
        """
        entry_t_str = entry_time.isoformat() if entry_time else None
        exit_t_str = exit_time.isoformat() if exit_time else None

        sql = """
        INSERT OR REPLACE INTO signal_outcomes (
            signal_id, final_status, entry_hit_price, exit_price,
            pnl_points, pnl_r, entry_time, exit_time, duration_seconds,
            max_favorable_excursion, max_adverse_excursion, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        params = (
            signal_id, final_status, entry_hit_price, exit_price,
            pnl_points, pnl_r, entry_t_str, exit_t_str, duration_seconds,
            max_favorable_excursion, max_adverse_excursion, notes,
        )

        with self.db.session() as conn:
            conn.execute(sql, params)
            # Đồng bộ luôn status ở bảng signals
            conn.execute(
                "UPDATE signals SET status = ?, updated_at = ? WHERE signal_id = ?;",
                (final_status, datetime.now(timezone.utc).isoformat(), signal_id),
            )

        log.info("✓ Đã lưu outcome cho tín hiệu [%s]: %s (PnL: %s pts)",
                 signal_id, final_status, pnl_points)
        return True

    def get_signal(self, signal_id: str) -> Optional[dict]:
        """Lấy thông tin chi tiết của một tín hiệu theo ID."""
        sql = "SELECT * FROM signals WHERE signal_id = ?;"
        with self.db.session() as conn:
            cursor = conn.execute(sql, (signal_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("reasons"):
                try:
                    data["reasons"] = json.loads(data["reasons"])
                except Exception:
                    pass
            return data

    def get_active_signals(self, symbol: str = "XAUUSD") -> list[dict]:
        """Lấy danh sách các tín hiệu đang active (ACTIVE hoặc ENTRY_REACHED)."""
        sql = """
        SELECT * FROM signals 
        WHERE symbol = ? AND status IN ('ACTIVE', 'ENTRY_REACHED')
        ORDER BY created_at DESC;
        """
        with self.db.session() as conn:
            cursor = conn.execute(sql, (symbol,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_recent_signals(self, limit: int = 50, symbol: Optional[str] = None) -> list[dict]:
        """Lấy danh sách các tín hiệu gần nhất."""
        if symbol:
            sql = "SELECT * FROM signals WHERE symbol = ? ORDER BY created_at DESC LIMIT ?;"
            params = (symbol, limit)
        else:
            sql = "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?;"
            params = (limit,)

        with self.db.session() as conn:
            cursor = conn.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]

    def count_signals(self) -> int:
        """Đếm tổng số tín hiệu trong database."""
        with self.db.session() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM signals;")
            return cursor.fetchone()[0]


class MarketDataRepository:
    """Repository quản lý nến lịch sử đa khung thời gian."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def save_candles(self, symbol: str, timeframe: str, df: pd.DataFrame) -> int:
        """
        Lưu DataFrame nến vào bảng market_data (bỏ qua nếu trùng timestamp).

        Args:
            symbol: Mã giao dịch (vd: XAUUSD).
            timeframe: Khung thời gian (vd: H1, M5).
            df: DataFrame có columns: time, open, high, low, close.

        Returns:
            Số lượng nến mới được thêm vào.
        """
        if df is None or df.empty:
            return 0

        sql = """
        INSERT OR IGNORE INTO market_data (
            symbol, timeframe, time, open, high, low, close, volume, spread
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        rows = []
        for _, row in df.iterrows():
            t = row.get("time")
            t_str = t.isoformat() if hasattr(t, "isoformat") else str(t)
            vol = float(row.get("tick_volume", row.get("volume", 0.0)))
            spread = float(row.get("spread", 0.0))

            rows.append((
                symbol,
                timeframe,
                t_str,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                vol,
                spread,
            ))

        with self.db.session() as conn:
            cursor = conn.executemany(sql, rows)
            inserted = cursor.rowcount

        log.debug("Đã lưu %d nến vào market_data (%s %s)", len(rows), symbol, timeframe)
        return inserted

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Truy vấn nến từ database trả về DataFrame.

        Args:
            symbol: Mã giao dịch.
            timeframe: Khung thời gian.
            limit: Số nến tối đa.
            start_time: Thời điểm bắt đầu (nếu có).
            end_time: Thời điểm kết thúc (nếu có).

        Returns:
            DataFrame OHLCV chuẩn.
        """
        query = "SELECT time, open, high, low, close, volume, spread FROM market_data WHERE symbol = ? AND timeframe = ?"
        params: list = [symbol, timeframe]

        if start_time:
            query += " AND time >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND time <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY time DESC LIMIT ?;"
        params.append(limit)

        with self.db.session() as conn:
            cursor = conn.execute(query, tuple(params))
            records = cursor.fetchall()

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in records])
        # Đảo lại theo thứ tự thời gian tăng dần
        df = df.iloc[::-1].reset_index(drop=True)
        df["time"] = pd.to_datetime(df["time"])
        return df


class StrategyRepository:
    """Repository quản lý các phiên bản chiến lược."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def register_version(
        self,
        version: str,
        name: str,
        description: str = "",
        parameters: Optional[dict] = None,
        is_active: bool = True,
    ) -> bool:
        """Đăng ký một phiên bản chiến lược mới."""
        sql = """
        INSERT OR REPLACE INTO strategy_versions (
            version, name, description, parameters, is_active
        ) VALUES (?, ?, ?, ?, ?);
        """
        params_json = json.dumps(parameters or {}, ensure_ascii=False)
        with self.db.session() as conn:
            conn.execute(sql, (version, name, description, params_json, 1 if is_active else 0))

        log.info("Đã đăng ký phiên bản chiến lược: %s (%s)", version, name)
        return True

    def get_active_version(self) -> Optional[dict]:
        """Lấy phiên bản chiến lược đang kích hoạt."""
        sql = "SELECT * FROM strategy_versions WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1;"
        with self.db.session() as conn:
            cursor = conn.execute(sql)
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("parameters"):
                try:
                    data["parameters"] = json.loads(data["parameters"])
                except Exception:
                    pass
            return data
