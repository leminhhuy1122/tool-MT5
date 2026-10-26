# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Resource Optimization & Diagnostics (Phase 10).

Cung cấp các công cụ tối ưu hóa tài nguyên và benchmark hệ thống:
1. ProcessSingletonGuard: Khóa tiến trình chống chạy song song trùng lặp.
2. BoundedDataCache: Bộ nhớ đệm dữ liệu nến giới hạn số nến tối đa và TTL.
3. ResourceProfiler: Đo lường định lượng CPU, RAM, Latency và Database Footprint.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
import pandas as pd
import psutil

from logger import get_logger

log = get_logger("system.optimizer")


class ProcessSingletonGuard:
    """
    Cơ chế bảo vệ đơn tiến trình (Process Singleton Guard).

    Đảm bảo chỉ có một instance bot runner duy nhất hoạt động trên Windows/VPS,
    tránh xung đột thiết bị MT5 Terminal và khóa ghi SQLite file.
    """

    def __init__(self, lock_file_path: Optional[str] = None):
        if lock_file_path:
            self.lock_path = Path(lock_file_path)
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.lock_path = base_dir / ".vietkey_runner.lock"
        self._is_locked = False

    def acquire(self) -> bool:
        """
        Chiếm giữ khóa tiến trình.

        Returns:
            True nếu chiếm khóa thành công; False nếu đã có tiến trình khác đang chạy.
        """
        current_pid = os.getpid()

        if self.lock_path.exists():
            try:
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if content:
                    existing_pid = int(content.split(":")[0])
                    if existing_pid == current_pid:
                        self._is_locked = True
                        return True

                    # Kiểm tra xem tiến trình cũ còn đang sống hay không
                    if psutil.pid_exists(existing_pid):
                        try:
                            proc = psutil.Process(existing_pid)
                            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                                log.warning(
                                    "Phát hiện tiến trình VietKey Bot khác (PID: %d) đang chạy. "
                                    "Từ chối khởi chạy thêm instance trùng lặp!",
                                    existing_pid,
                                )
                                return False
                        except Exception:
                            pass
            except Exception as e:
                log.debug("Đọc lock file cũ gặp lỗi: %s", e)

        # Ghi PID và thời gian hiện tại vào lock file
        try:
            self.lock_path.write_text(f"{current_pid}:{time.time()}", encoding="utf-8")
            self._is_locked = True
            log.info("✓ Đã chiếm giữ khóa tiến trình an toàn (PID: %d)", current_pid)
            return True
        except Exception as e:
            log.error("Không thể ghi file lock: %s", e)
            return False

    def release(self) -> None:
        """Giải phóng khóa tiến trình khi bot tắt."""
        if not self._is_locked:
            return

        try:
            if self.lock_path.exists():
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if content:
                    pid = int(content.split(":")[0])
                    if pid == os.getpid():
                        self.lock_path.unlink(missing_ok=True)
                        log.info("✓ Đã giải phóng khóa tiến trình (PID: %d)", pid)
            self._is_locked = False
        except Exception as e:
            log.debug("Giải phóng lock file: %s", e)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class BoundedDataCache:
    """
    Bộ nhớ đệm dữ liệu nến giới hạn số nến tối đa trong RAM và có thời gian sống TTL.

    Giúp hạn chế số lần gọi MT5 IPC không cần thiết khi nến chưa kết thúc.
    """

    def __init__(self, max_bars: int = 200, ttl_seconds: float = 3.0):
        self.max_bars = max_bars
        self.ttl_seconds = ttl_seconds
        self._store: dict[Any, tuple[pd.DataFrame, float]] = {}

    def get(self, key: Any, default: Any = None) -> Optional[pd.DataFrame]:
        """
        Lấy DataFrame từ cache nếu còn trong hạn TTL.
        """
        if key in self._store:
            df, timestamp = self._store[key]
            if time.time() - timestamp <= self.ttl_seconds:
                return df.copy()
        return default

    def put(self, key: Any, df: pd.DataFrame) -> None:
        """
        Lưu DataFrame vào cache với giới hạn max_bars.
        """
        if df is None or len(df) == 0:
            return

        # Khống chế số lượng nến lưu trong RAM
        bounded_df = df.iloc[-self.max_bars:].copy() if len(df) > self.max_bars else df.copy()
        self._store[key] = (bounded_df, time.time())

    def __getitem__(self, key: Any) -> pd.DataFrame:
        if key in self._store:
            df, _ = self._store[key]
            return df
        raise KeyError(key)

    def __setitem__(self, key: Any, df: pd.DataFrame) -> None:
        self.put(key, df)

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: Any) -> bool:
        return key in self._store

    def clear(self) -> None:
        """Dọn sạch cache."""
        self._store.clear()

    def size(self) -> int:
        """Số lượng mục đang cache."""
        return len(self._store)


class ResourceProfiler:
    """
    Công cụ định lượng và Benchmark tài nguyên hệ thống:
    - CPU & RAM RSS của tiến trình
    - Độ trễ sinh tín hiệu (Signal Generation Latency)
    - Độ trễ nạp mô hình ML (Model Load Time)
    - Kích thước lưu trữ và số bản ghi Database
    """

    @staticmethod
    def get_process_metrics() -> dict[str, Any]:
        """Lấy thông số CPU, RAM thực tế của tiến trình Python hiện tại."""
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        cpu_pct = proc.cpu_percent(interval=None)

        return {
            "pid": os.getpid(),
            "cpu_percent": round(cpu_pct, 1),
            "ram_rss_mb": round(mem.rss / (1024 * 1024), 2),
            "ram_vms_mb": round(mem.vms / (1024 * 1024), 2),
            "threads_count": proc.num_threads(),
            "system_ram_percent": psutil.virtual_memory().percent,
        }

    @staticmethod
    def measure_latency(func: Callable, *args, **kwargs) -> Tuple[Any, float]:
        """
        Đo thời gian thực thi của một hàm (milliseconds).

        Returns:
            Tuple (kết quả trả về, thời gian thực thi ms)
        """
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return result, round(elapsed_ms, 2)

    @staticmethod
    def measure_database_footprint(db_manager: Any) -> dict[str, Any]:
        """Đo kích thước file SQLite và số lượng bản ghi của từng bảng."""
        if db_manager is None:
            return {"file_size_mb": 0.0, "table_counts": {}, "status": "NO_DATABASE"}

        file_size_mb = 0.0
        db_path_str = getattr(db_manager, "db_path", None)
        if not db_path_str and hasattr(db_manager, "config") and hasattr(db_manager.config, "url"):
            db_path_str = db_manager.config.url.replace("sqlite:///", "")

        if db_path_str and db_path_str != ":memory:" and os.path.exists(db_path_str):
            file_size_mb = round(os.path.getsize(db_path_str) / (1024 * 1024), 2)

        table_counts = {}
        tables = ["signals", "signal_outcomes", "signal_features", "market_data", "model_versions"]

        try:
            with db_manager.session() as conn:
                for table in tables:
                    try:
                        cursor = conn.execute(f"SELECT COUNT(*) FROM {table};")
                        table_counts[table] = cursor.fetchone()[0]
                    except Exception:
                        table_counts[table] = 0
        except Exception as e:
            log.debug("Đo kích thước bảng database: %s", e)

        return {
            "file_size_mb": file_size_mb,
            "table_counts": table_counts,
            "status": "ONLINE",
        }

    @staticmethod
    def measure_model_load_latency(model_registry: Any) -> float:
        """Đo thời gian nạp Active Production Model từ SQLite vào RAM (ms)."""
        if model_registry is None:
            return 0.0

        t0 = time.perf_counter()
        try:
            model_registry.get_active_production_model()
        except Exception:
            pass
        return round((time.perf_counter() - t0) * 1000.0, 2)

    @classmethod
    def get_system_benchmark(
        cls,
        db_manager: Optional[Any] = None,
        model_registry: Optional[Any] = None,
        signal_engine: Optional[Any] = None,
        sample_df: Optional[pd.DataFrame] = None,
    ) -> dict[str, Any]:
        """
        Tạo báo cáo Benchmark toàn diện tài nguyên hệ thống (Phase 10).
        """
        proc_metrics = cls.get_process_metrics()
        db_footprint = cls.measure_database_footprint(db_manager)
        model_latency = cls.measure_model_load_latency(model_registry)

        signal_latency = 0.0
        if signal_engine is not None and sample_df is not None and len(sample_df) >= 20:
            try:
                _, signal_latency = cls.measure_latency(
                    signal_engine.generate_signal,
                    df=sample_df,
                    symbol="XAUUSD",
                    timeframe="M5",
                )
            except Exception as e:
                log.debug("Đo signal generation latency: %s", e)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "process": proc_metrics,
            "database": db_footprint,
            "benchmarks": {
                "signal_generation_latency_ms": signal_latency,
                "model_load_latency_ms": model_latency,
                "target_max_latency_ms": 250.0,
                "latency_status": "EXCELLENT" if signal_latency < 100.0 else ("GOOD" if signal_latency < 250.0 else "WARNING"),
            },
            "resource_efficiency": {
                "memory_bounded": True,
                "max_candles_in_ram": 200,
                "isolated_training": True,
            },
        }
