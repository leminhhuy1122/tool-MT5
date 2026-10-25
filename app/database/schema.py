# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Database Schema DDL.

Định nghĩa bảng và chỉ mục (indexes) cho SQLite:
1. signals: Bảng lưu vết các tín hiệu giao dịch.
2. signal_features: Lưu các chỉ số kỹ thuật tại thời điểm phát tín hiệu (phục vụ ML Phase 9).
3. signal_outcomes: Lưu kết quả giao dịch thực tế (TP/SL/Hòa vốn, PnL, R:R).
4. market_data: Lưu nến lịch sử OHLCV đa khung thời gian phục vụ backtest.
5. strategy_versions: Quản lý phiên bản chiến lược giao dịch.
6. model_versions: Quản lý phiên bản mô hình AI/ML.
7. model_evaluations: Đánh giá hiệu suất mô hình ML.
8. schema_migrations: Theo dõi các đợt migration.
"""

INITIAL_SCHEMA_SQL = """
-- 1. Quản lý migration
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Quản lý phiên bản chiến lược
CREATE TABLE IF NOT EXISTS strategy_versions (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    parameters TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bảng tín hiệu giao dịch chính
CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    strategy_version TEXT DEFAULT 'v1.0',
    symbol TEXT NOT NULL DEFAULT 'XAUUSD',
    timeframe TEXT NOT NULL DEFAULT 'H1',
    direction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    entry_price REAL NOT NULL,
    entry_zone_low REAL,
    entry_zone_high REAL,
    stop_loss REAL NOT NULL,
    take_profit_1 REAL NOT NULL,
    take_profit_2 REAL,
    risk_reward_ratio REAL,
    sl_distance REAL,
    tp_distance REAL,
    score REAL DEFAULT 0.0,
    confidence TEXT DEFAULT 'LOW',
    setup_type TEXT,
    reasons TEXT,
    invalidation TEXT,
    trend_h4 TEXT,
    trend_h1 TEXT,
    created_at TIMESTAMP,
    expires_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 4. Đặc trưng kỹ thuật tại thời điểm phát tín hiệu (ML Features)
CREATE TABLE IF NOT EXISTS signal_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL,
    rsi_14 REAL,
    ema_20 REAL,
    ema_50 REAL,
    ema_200 REAL,
    atr_14 REAL,
    spread REAL,
    volatility_level TEXT,
    body_ratio REAL,
    candle_range REAL,
    swing_high REAL,
    swing_low REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(signal_id) ON DELETE CASCADE
);

-- 5. Kết quả thực tế của tín hiệu (Outcomes)
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL UNIQUE,
    final_status TEXT NOT NULL,
    entry_hit_price REAL,
    exit_price REAL,
    pnl_points REAL,
    pnl_r REAL,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    duration_seconds INTEGER,
    max_favorable_excursion REAL,
    max_adverse_excursion REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(signal_id) ON DELETE CASCADE
);

-- 6. Dữ liệu nến thị trường (Market Data OHLCV)
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    time TIMESTAMP NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL DEFAULT 0,
    spread REAL DEFAULT 0,
    UNIQUE(symbol, timeframe, time)
);

-- 7. Phiên bản mô hình Machine Learning (Phase 9)
CREATE TABLE IF NOT EXISTS model_versions (
    version TEXT PRIMARY KEY,
    model_type TEXT NOT NULL,
    features_list TEXT,
    metrics TEXT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Đánh giá hiệu suất mô hình (Phase 9)
CREATE TABLE IF NOT EXISTS model_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version TEXT NOT NULL,
    evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    win_rate REAL,
    profit_factor REAL,
    sample_size INTEGER,
    details TEXT,
    FOREIGN KEY (model_version) REFERENCES model_versions(version) ON DELETE CASCADE
);

-- Chỉ mục (Indexes) để tăng tốc độ truy vấn
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf ON signals(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_market_data_lookup ON market_data(symbol, timeframe, time);
CREATE INDEX IF NOT EXISTS idx_signal_features_sig_id ON signal_features(signal_id);
"""
