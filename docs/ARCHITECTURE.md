# VietKey Gold AI — Kiến trúc hệ thống

## 1. Tổng quan kiến trúc

```
┌──────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                   (Entry Point / Orchestrator)                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐                                     │
│  │  config   │  │  logger  │                                     │
│  │  (.env)   │  │          │                                     │
│  └──────────┘  └──────────┘                                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  app/mt5/                                            │       │
│  │  connector.py | account_info.py | symbol_info.py     │       │
│  └──────────────────────┬───────────────────────────────┘       │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────┐       │
│  │  app/market/                                          │       │
│  │  data_manager | timeframe_manager | indicators        │       │
│  │  market_structure | liquidity | volatility            │       │
│  └──────────────────────┬───────────────────────────────┘       │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────┐       │
│  │  app/strategy/                                        │       │
│  │  setup_detector | entry_confirmation | signal_engine  │       │
│  │  signal_scoring | risk_filter                         │       │
│  └──────────┬───────────────────────┬───────────────────┘       │
│             │                       │                            │
│  ┌──────────▼────────┐  ┌──────────▼────────┐                  │
│  │  app/notification/ │  │  app/database/     │                  │
│  │  telegram_bot      │  │  database.py       │                  │
│  │  message_formatter │  │  models.py         │                  │
│  └───────────────────┘  │  signal_repository  │                  │
│                          └───────────────────┘                   │
│                                                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │ app/backtest/  │  │ app/ai/        │  │ app/dashboard/    │   │
│  │ backtest_engine│  │ model_trainer  │  │ streamlit app     │   │
│  │ walk_forward   │  │ model_registry │  │                   │   │
│  └───────────────┘  └───────────────┘  └───────────────────┘   │
│                                                                  │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  app/monitoring/                                       │      │
│  │  health_check | performance_monitor                    │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Công nghệ

| Lớp | Công nghệ | Phase |
|-----|-----------|-------|
| Trading Engine | Python 3.14, MetaTrader5, Pandas, NumPy | 0-4 |
| Technical Analysis | pandas-ta / TA-Lib | 3 |
| Notification | Telegram Bot API | 5 |
| Database | SQLite → PostgreSQL | 6 |
| Backtest | Custom engine | 7 |
| Dashboard | Streamlit → Next.js/NestJS | 8 |
| AI/ML | Scikit-learn, XGBoost/LightGBM | 9 |
| Monitoring | Custom health check | 11 |

## 3. Nguyên tắc thiết kế

### Separation of Concerns
- `config.py` — Chỉ đọc cấu hình từ .env.
- `logger.py` — Chỉ thiết lập logging.
- `main.py` — Orchestrate, không chứa business logic.
- `app/mt5/` — Chỉ kết nối và lấy dữ liệu MT5.
- `app/market/` — Chỉ xử lý và validate dữ liệu.
- `app/strategy/` — Chỉ phân tích và phát tín hiệu.
- `app/notification/` — Chỉ gửi thông báo.
- `app/database/` — Chỉ lưu trữ dữ liệu.

### Dependency Direction
```
main → mt5 → market → strategy → notification + database
                                → backtest
                                → ai (giai đoạn sau)
```
Các module cấp thấp không import module cấp cao.

### Configuration via Environment
- Tất cả secrets, credentials nằm trong `.env`.
- Không hardcode giá trị nhạy cảm.
- Signal engine không được gọi chức năng đặt lệnh.

### Testability
- Mỗi module có unit test riêng.
- Config dùng dataclass `frozen=True` — immutable, dễ mock.
- Hàm nhận dependency qua parameter.

### Resource Optimization
- Chỉ lấy nến cần thiết.
- Phân tích lại chỉ khi có nến mới.
- Xử lý incremental.
- Shutdown an toàn.

## 4. Cấu trúc thư mục (dự kiến đầy đủ)

```
chibao MT5/
├── main.py                    # Entry point
├── config.py                  # Config từ .env
├── logger.py                  # Logging setup
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── mt5/                   # Phase 1
│   ├── market/                # Phase 2-3
│   ├── strategy/              # Phase 4
│   ├── notification/          # Phase 5
│   ├── database/              # Phase 6
│   ├── backtest/              # Phase 7
│   ├── ai/                    # Phase 9
│   ├── monitoring/            # Phase 11
│   └── dashboard/             # Phase 8
│
├── data/                      # Dữ liệu
│   ├── historical/
│   ├── processed/
│   └── datasets/
│
├── models/                    # ML models
│   ├── candidate/
│   ├── production/
│   └── archive/
│
├── logs/                      # Log files
│
├── tests/                     # Unit + integration tests
│
└── docs/                      # Tài liệu
    ├── PROJECT_PLAN.md
    ├── ARCHITECTURE.md
    ├── STRATEGY.md            # Phase 4+
    ├── DATABASE.md            # Phase 6+
    ├── TESTING.md             # Phase 7+
    └── CHANGELOG.md
```

> **Lưu ý:** Không tạo toàn bộ thư mục ngay. Xây dựng từng module theo phase.

## 5. Luồng dữ liệu

```
MT5 Terminal
    │
    ▼
MT5 Connector (kết nối, lấy OHLCV + tick)
    │
    ▼
Market Data Engine (validate, cache, chuẩn hóa)
    │
    ▼
Technical Analysis (EMA, RSI, ATR, BOS, CHoCH, S/R, PA)
    │
    ▼
Signal Engine (setup detection → scoring → BUY/SELL/WAIT)
    │
    ├──▶ Telegram (gửi tín hiệu)
    ├──▶ Database (lưu signal + features + outcome)
    └──▶ Signal Tracker (theo dõi kết quả)
              │
              ▼
        Performance Report → Dashboard
              │
              ▼
        AI Learning Pipeline (feature eng → train → evaluate)
```

## 6. Database Schema (dự kiến)

| Table | Mục đích | Phase |
|-------|----------|-------|
| signals | Lưu tín hiệu | 6 |
| signal_features | Feature kèm tín hiệu | 6 |
| signal_outcomes | Kết quả tín hiệu | 6 |
| market_data | Dữ liệu nến | 6 |
| strategy_versions | Phiên bản chiến lược | 6 |
| model_versions | Phiên bản ML model | 9 |
| model_evaluations | Đánh giá model | 9 |

## 7. Quy ước đặt tên

| Loại | Quy ước | Ví dụ |
|------|---------|-------|
| Module | snake_case | `config.py`, `mt5_connector.py` |
| Class | PascalCase | `MT5Config`, `SignalEngine` |
| Function | snake_case | `get_settings()`, `check_environment()` |
| Constant | UPPER_SNAKE | `BASE_DIR`, `LOG_LEVEL` |
| Test file | `test_` prefix | `test_config.py` |
| Test class | `Test` prefix | `TestMT5Config` |

## 8. Signal States

```
WAIT ──▶ ACTIVE ──▶ ENTRY_REACHED ──┬──▶ TP_REACHED
                                     ├──▶ SL_REACHED
                                     └──▶ UNRESOLVED
                  ├──▶ INVALIDATED
                  └──▶ EXPIRED
```
