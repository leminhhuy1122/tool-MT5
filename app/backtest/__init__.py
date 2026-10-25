# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Backtest Engine Package.

Cung cấp các công cụ kiểm thử chiến lược trên dữ liệu quá khứ:
- BacktestConfig, TradeRecord, TradeStatus, BacktestResult
- calculate_metrics
- HistoricalLoader
- BacktestEngine
- WalkForwardAnalyzer, WalkForwardReport
"""

from app.backtest.models import (
    BacktestConfig,
    BacktestResult,
    TradeRecord,
    TradeStatus,
)
from app.backtest.metrics import calculate_metrics
from app.backtest.historical_loader import HistoricalLoader
from app.backtest.engine import BacktestEngine
from app.backtest.walk_forward import WalkForwardAnalyzer, WalkForwardReport

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "TradeRecord",
    "TradeStatus",
    "calculate_metrics",
    "HistoricalLoader",
    "BacktestEngine",
    "WalkForwardAnalyzer",
    "WalkForwardReport",
]
