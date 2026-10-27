# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Repositories.

Cung cấp các lớp truy xuất và thao tác dữ liệu (Data Access Layer / Repository):
- SignalRepository: Lưu, cập nhật và truy vấn tín hiệu giao dịch, features, outcomes.
- MarketDataRepository: Lưu và truy vấn nến OHLCV đa khung thời gian.
- StrategyRepository: Quản lý các phiên bản chiến lược.
"""

from datetime import datetime, timezone, timedelta
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
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Đảm bảo bảng signals và signal_features có các cột mở rộng."""
        try:
            with self.db.session() as conn:
                cursor = conn.execute("PRAGMA table_info(signals);")
                s_cols = [r["name"] for r in cursor.fetchall()]
                if s_cols and "market_regime" not in s_cols:
                    conn.execute("ALTER TABLE signals ADD COLUMN market_regime TEXT DEFAULT 'UNKNOWN';")
                if s_cols and "is_dca" not in s_cols:
                    conn.execute("ALTER TABLE signals ADD COLUMN is_dca INTEGER DEFAULT 0;")
                if s_cols and "parent_signal_id" not in s_cols:
                    conn.execute("ALTER TABLE signals ADD COLUMN parent_signal_id TEXT;")
                if s_cols and "dca_breakeven_price" not in s_cols:
                    conn.execute("ALTER TABLE signals ADD COLUMN dca_breakeven_price REAL;")

                cursor = conn.execute("PRAGMA table_info(signal_features);")
                cols = [r["name"] for r in cursor.fetchall()]
                if cols and "features_json" not in cols:
                    conn.execute("ALTER TABLE signal_features ADD COLUMN features_json TEXT;")
        except Exception as e:
            log.debug("Kiểm tra cột signals/signal_features: %s", e)

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
        regime_str = getattr(signal, "market_regime", "UNKNOWN") or "UNKNOWN"
        is_dca_val = 1 if getattr(signal, "is_dca", False) else 0
        parent_id_val = getattr(signal, "parent_signal_id", None)
        be_price_val = getattr(signal, "dca_breakeven_price", None)

        sql_signal = """
        INSERT OR REPLACE INTO signals (
            signal_id, strategy_version, symbol, timeframe, direction, status,
            entry_price, entry_zone_low, entry_zone_high, stop_loss,
            take_profit_1, take_profit_2, risk_reward_ratio, sl_distance,
            tp_distance, score, confidence, setup_type, reasons,
            invalidation, trend_h4, trend_h1, market_regime, is_dca, parent_signal_id, dca_breakeven_price,
            created_at, expires_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            regime_str,
            is_dca_val,
            parent_id_val,
            float(be_price_val) if be_price_val is not None else None,
            created_str,
            expires_str,
            created_str,
        )

        with self.db.session() as conn:
            conn.execute(sql_signal, params)

            # Lưu features nếu có
            if features:
                features_str = json.dumps(features, ensure_ascii=False)
                has_json_col = False
                try:
                    cursor = conn.execute("PRAGMA table_info(signal_features);")
                    cols = [r["name"] for r in cursor.fetchall()]
                    has_json_col = "features_json" in cols
                except Exception:
                    pass

                if has_json_col:
                    sql_feat = """
                    INSERT INTO signal_features (
                        signal_id, rsi_14, ema_20, ema_50, ema_200, atr_14,
                        spread, volatility_level, body_ratio, candle_range,
                        swing_high, swing_low, features_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                        features_str,
                    )
                else:
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

    def get_signal_features(self, signal_id: str) -> Optional[dict]:
        """Lấy đặc trưng kỹ thuật đã lưu của một tín hiệu."""
        sql = "SELECT * FROM signal_features WHERE signal_id = ? ORDER BY id DESC LIMIT 1;"
        with self.db.session() as conn:
            row = conn.execute(sql, (signal_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("features_json"):
                try:
                    data["full_features"] = json.loads(data["features_json"])
                except Exception:
                    pass
            return data

    def update_status(
        self,
        signal_id: str,
        status: SignalStatus,
        updated_at: Optional[datetime] = None,
        invalidation: Optional[str] = None,
    ) -> bool:
        """
        Cập nhật trạng thái của tín hiệu.

        Args:
            signal_id: ID tín hiệu.
            status: Trạng thái mới.
            updated_at: Thời điểm cập nhật.
            invalidation: Lý do hủy/vô hiệu hóa nếu có.

        Returns:
            True nếu cập nhật thành công ít nhất 1 dòng.
        """
        now_str = (updated_at or datetime.now(timezone.utc)).isoformat()
        if invalidation:
            sql = "UPDATE signals SET status = ?, invalidation = ?, updated_at = ? WHERE signal_id = ?;"
            params = (status.value, invalidation, now_str, signal_id)
        else:
            sql = "UPDATE signals SET status = ?, updated_at = ? WHERE signal_id = ?;"
            params = (status.value, now_str, signal_id)

        with self.db.session() as conn:
            cursor = conn.execute(sql, params)
            updated = cursor.rowcount > 0

        if updated:
            log.debug("Đã cập nhật trạng thái [%s] -> %s", signal_id, status.value)
        return updated

    def update_stop_loss(
        self,
        signal_id: str,
        new_stop_loss: float,
        updated_at: Optional[datetime] = None,
    ) -> bool:
        """
        Cập nhật mức Stop Loss trong database (dời SL hòa vốn hoặc kích hoạt Trailing Stop).
        """
        now_str = (updated_at or datetime.now(timezone.utc)).isoformat()
        sql = "UPDATE signals SET stop_loss = ?, updated_at = ? WHERE signal_id = ?;"

        with self.db.session() as conn:
            cursor = conn.execute(sql, (round(new_stop_loss, 2), now_str, signal_id))
            updated = cursor.rowcount > 0

        if updated:
            log.info("✓ Đã cập nhật Stop Loss mới cho tín hiệu [%s] -> %.2f", signal_id, new_stop_loss)
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
        """Lấy danh sách các tín hiệu gần nhất kèm thông tin kết quả outcome (nếu đã kết thúc)."""
        if symbol:
            sql = """
            SELECT s.*, 
                   o.final_status, o.exit_price, o.pnl_points, o.pnl_r,
                   o.duration_seconds, o.exit_time, o.created_at as outcome_time
            FROM signals s
            LEFT JOIN signal_outcomes o ON s.signal_id = o.signal_id
            WHERE s.symbol = ? 
            ORDER BY s.created_at DESC 
            LIMIT ?;
            """
            params = (symbol, limit)
        else:
            sql = """
            SELECT s.*, 
                   o.final_status, o.exit_price, o.pnl_points, o.pnl_r,
                   o.duration_seconds, o.exit_time, o.created_at as outcome_time
            FROM signals s
            LEFT JOIN signal_outcomes o ON s.signal_id = o.signal_id
            ORDER BY s.created_at DESC 
            LIMIT ?;
            """
            params = (limit,)

        with self.db.session() as conn:
            cursor = conn.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]

    def count_signals(self) -> int:
        """Đếm tổng số tín hiệu trong database."""
        with self.db.session() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM signals;")
            return cursor.fetchone()[0]

    def get_latest_outcome(self) -> Optional[dict]:
        """Lấy kết quả của lệnh vừa kết thúc/khớp gần đây nhất kèm chi tiết signal."""
        sql = """
        SELECT o.*, s.symbol, s.direction, s.entry_price, s.stop_loss, 
               s.take_profit_1, s.take_profit_2, s.created_at as signal_created_at,
               s.timeframe, s.score, s.strategy_version, s.risk_reward_ratio
        FROM signal_outcomes o
        JOIN signals s ON o.signal_id = s.signal_id
        ORDER BY o.id DESC
        LIMIT 1;
        """
        with self.db.session() as conn:
            cursor = conn.execute(sql)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_performance_summary(self) -> dict:
        """Lấy thống kê tổng hợp hiệu suất (Wins, Losses, Winrate, Net Points, Net Pips, Profit Factor)."""
        sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl_points < 0 THEN 1 ELSE 0 END) as losses,
            AVG(pnl_r) as avg_r,
            SUM(pnl_points) as net_points,
            SUM(CASE WHEN pnl_points > 0 THEN pnl_points ELSE 0 END) as total_profit,
            SUM(CASE WHEN pnl_points < 0 THEN ABS(pnl_points) ELSE 0 END) as total_loss
        FROM signal_outcomes;
        """
        with self.db.session() as conn:
            cursor = conn.execute(sql)
            row = cursor.fetchone()
            if not row or row["total"] == 0:
                return {
                    "total": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "loss_rate": 0.0,
                    "net_points": 0.0,
                    "net_pips": 0.0,
                    "profit_factor": 0.0,
                }
            total = int(row["total"])
            wins = int(row["wins"] or 0)
            losses = int(row["losses"] or 0)
            win_rate = (wins / total * 100) if total > 0 else 0.0
            loss_rate = (losses / total * 100) if total > 0 else 0.0
            net_points = float(row["net_points"] or 0.0)
            net_pips = round(net_points * 10.0, 1)
            total_profit = float(row["total_profit"] or 0.0)
            total_loss = float(row["total_loss"] or 0.0)
            if total_loss > 0:
                pf = round(total_profit / total_loss, 2)
            else:
                pf = 2.0 if wins > 0 else 0.0
            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 1),
                "loss_rate": round(loss_rate, 1),
                "net_points": round(net_points, 2),
                "net_pips": net_pips,
                "profit_factor": pf,
            }

    def get_historical_outcomes(
        self,
        lookback_days: Optional[int] = None,
        symbol: Optional[str] = None,
    ) -> list[dict]:
        """
        Lấy danh sách các lệnh đã có kết quả outcome (JOIN giữa signals và signal_outcomes)
        phục vụ theo dõi và đánh giá hiệu suất của từng setup.
        """
        clauses = []
        params = []
        if symbol:
            clauses.append("s.symbol = ?")
            params.append(symbol)
        if lookback_days:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
            clauses.append("s.created_at >= ?")
            params.append(cutoff)

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        sql = f"""
        SELECT 
            s.signal_id, s.symbol, s.setup_type, s.direction, s.timeframe,
            s.entry_price, s.stop_loss, s.take_profit_1, s.take_profit_2,
            s.score, s.confidence, s.strategy_version, s.created_at,
            s.market_regime,
            o.final_status, o.entry_hit_price, o.exit_price,
            o.pnl_points, o.pnl_r, o.duration_seconds,
            o.max_favorable_excursion, o.max_adverse_excursion,
            o.exit_time, o.notes
        FROM signal_outcomes o
        JOIN signals s ON o.signal_id = s.signal_id
        {where_str}
        ORDER BY s.created_at DESC;
        """

        with self.db.session() as conn:
            cursor = conn.execute(sql, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def get_setup_performance_summary(
        self,
        lookback_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Tổng hợp hiệu suất theo từng loại setup từ bảng outcomes.
        """
        from app.strategy.performance_evaluator import SetupPerformanceEvaluator

        evaluator = SetupPerformanceEvaluator(
            repository=self,
            lookback_days=lookback_days,
        )
        return {st: m.to_dict() for st, m in evaluator.refresh().items()}


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
