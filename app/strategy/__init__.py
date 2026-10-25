# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Strategy & Signal Engine Package.

Cung cấp các thành phần phân tích chiến lược và sinh tín hiệu:
- SignalDirection, SignalStatus, TradingSignal (Models)
- SetupDetector, SetupCandidate, SetupType
- RiskFilter, FilterConfig, FilterResult
- SignalScoring, ScoreBreakdown
- SignalTracker, TrackerConfig
- SignalEngine (Main Entry Point)
"""

from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.setup_detector import SetupCandidate, SetupType, detect_setups
from app.strategy.risk_filter import FilterConfig, FilterResult, apply_filters
from app.strategy.signal_scoring import ScoreBreakdown, calculate_signal_score
from app.strategy.signal_tracker import SignalTracker, TrackerConfig
from app.strategy.signal_engine import SignalEngine

__all__ = [
    "SignalDirection",
    "SignalStatus",
    "TradingSignal",
    "SetupCandidate",
    "SetupType",
    "detect_setups",
    "FilterConfig",
    "FilterResult",
    "apply_filters",
    "ScoreBreakdown",
    "calculate_signal_score",
    "SignalTracker",
    "TrackerConfig",
    "SignalEngine",
]
