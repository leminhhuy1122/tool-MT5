# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Package.

Cung cấp các công cụ lưu trữ dữ liệu bền vững qua SQLite:
- DatabaseManager (kết nối, context manager, WAL mode)
- run_migrations, get_current_version
- SignalRepository, MarketDataRepository, StrategyRepository
"""

from app.database.connection import DatabaseManager, parse_sqlite_path
from app.database.migrations import get_current_version, run_migrations
from app.database.repository import (
    MarketDataRepository,
    SignalRepository,
    StrategyRepository,
)

__all__ = [
    "DatabaseManager",
    "parse_sqlite_path",
    "run_migrations",
    "get_current_version",
    "SignalRepository",
    "MarketDataRepository",
    "StrategyRepository",
]
