# VietKey Gold AI — Changelog

Tất cả thay đổi quan trọng của dự án được ghi nhận tại đây.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [2.1.0] - 2026-10-26

### Smart Trading Terminal UI & Adaptive Profit Protection Upgrade
- **Bảo Vệ Lợi Nhuận & Quản Trị Thoát Lệnh Thông Minh (`app/strategy/smart_exit.py`):**
  - Tự động dời SL hòa vốn (Breakeven) khi lệnh xanh +5 giá (+50 pips).
  - Kích hoạt Trailing Stop từng bước khóa lợi nhuận khi lãi +8 giá (+80 pips).
  - Cảnh báo thoát lệnh sớm (Early Exit Alert) khi nến M5 vi phạm cấu trúc Order Block.
  - Áp dụng nguyên tắc an toàn: Tuyệt đối không vào lệnh BUY và SELL tại cùng 1 điểm giá hoặc lệch nhau 1-2 giá.
- **AI Companion & Telegram Trợ Lý Giao Dịch (`app/strategy/ai_companion.py`):**
  - Tự động gửi tin nhắn trò chuyện, khuyên dời SL, gồng lãi hoặc cắt lệnh thông minh như bot AI đồng hành.
  - Chức năng Báo Cáo Lệnh Vừa Khớp Lên Telegram (`/api/v1/telegram/broadcast-last-outcome`) tổng kết PnL Pips, điểm chốt lời/cắt lỗ.
- **Giám Sát Hệ Thống & Tìm Lỗi Toàn Diện (`frontend/src/components/views/SystemMonitoringView.tsx`):**
  - Màn hình chuyên dụng giám sát sức khỏe bot, tài nguyên CPU/RAM, độ trễ IPC MT5 (1ms), SQLite WAL mode, và xem log trực tiếp.
- **Ví Đầu Tư Ảo 0.01 Lot (`frontend/src/components/views/PaperWalletView.tsx`):**
  - Tự động khớp lệnh mô phỏng tài khoản $50 (0.01 lot) và hiển thị trực tiếp tiền lời/lỗ ($ U) thời gian thực.
- **Tối Ưu Hóa & Tinh Gọn Giao Diện Người Dùng (UI/UX Refinement):**
  - Loại bỏ thanh menu dư thừa trên cùng (`Topbar.tsx`), giữ không gian màn hình thoáng đãng.
  - Vòng tròn giá vàng trung tâm (`MarketTickerHero.tsx`) bo tròn, viền vàng ánh kim neon phát sáng nổi bật ở chính giữa.
  - Vòng tròn suy nghĩ Thinking (`LiveOpenPositions.tsx`) hoạt họa radar AI quét nến M5 kèm đồng hồ đếm ngược nhịp tim.
  - Bảng Tín Hiệu & Lệnh (`LatestSignals.tsx`) tinh gọn từ 10 cột rườm rà xuống 5 cột rành mạch, hỗ trợ nhấn chuột vào bất kỳ vị trí nào trên dòng lệnh để mở popup phân tích chi tiết SMC & Order Block.

---

## [2.0.0] - 2026-10-26

### VietKey Gold AI — Trading Intelligence & Self-Learning Upgrade (Phases 1 - 11)

Toàn bộ 11 giai đoạn nâng cấp định lượng và học máy tự thích ứng đã hoàn thành và được kiểm thử toàn diện:

- **Phase 1: Quantitative Audit & Baselining**:
  - Khảo sát mã nguồn, đo lường độ trễ, thiết lập baseline kiến trúc và bảo vệ nghiêm ngặt tiêu chuẩn mã hóa UTF-8 tiếng Việt.
- **Phase 2: Signal Conflict Resolution & Setup Lifecycle**:
  - `app/strategy/conflict_resolver.py`: Phân xử xung đột BUY/SELL cùng nến theo xu hướng H4 và cấp bậc ưu tiên setup.
  - `app/strategy/signal_tracker.py`: Quản lý chu kỳ sống `SetupLifecycleStatus` (DISCOVERED, VALIDATED, ACTIVE, APPROACHING, ENTRY_REACHED, INVALIDATED, EXPIRED, CANCELLED, COMPLETED).
- **Phase 3: Market Regime Detection Engine**:
  - `app/market/regime.py`: Nhận diện 5 trạng thái thị trường định lượng (TRENDING_BULLISH, TRENDING_BEARISH, RANGING, HIGH_VOLATILITY_EXPANSION, COMPRESSION_SQUEEZE) dựa trên ADX, DI+/DI-, ATR percentile và Bollinger Band width.
- **Phase 4: Dynamic Confluence & Weight Scoring**:
  - `app/strategy/signal_scoring.py`: Chuyển đổi mô hình tính điểm sang chấm điểm trọng số động theo từng Regime thị trường (tổng trọng số chuẩn hóa 1.0, minh bạch minh họa chi tiết breakdown).
- **Phase 5: Setup Performance Memory & Decay**:
  - `app/strategy/performance_evaluator.py`: Đo lường sâu PnL, Win Rate, Profit Factor, Expectancy R, MFE/MAE trung bình theo từng Setup Type với trọng số phân rã theo thời gian (exponential time decay).
- **Phase 6: Multi-Horizon ML Prediction**:
  - `app/ml/features.py`: Trích xuất 21 đặc trưng định lượng gồm momentum ratios, cost/spread volatility, session liquidity score, volume surge.
  - `app/ml/filter.py`: Phân loại chất lượng tín hiệu qua Machine Learning kết hợp fallback quy tắc truyền thống an toàn.
- **Phase 7: Walk-Forward Evaluation & Model Versioning**:
  - `app/ml/walk_forward.py`: Thẩm định Out-of-Sample Walk-Forward với Expanding Window chống Look-ahead Bias và Data Leakage.
  - `app/ml/registry.py`: Đăng ký, kiểm duyệt tiêu chuẩn sản xuất (Promotion Rules) và cơ chế Rollback tự động.
- **Phase 8: Advanced Self-Learning from Closed Trade Feedback**:
  - `app/strategy/feedback_learner.py`: Bộ phân tích nguyên nhân đóng lệnh `TradeOutcomeAnalyzer` (RootCause: SPREAD_WIDENING, NEWS_SPIKE, STRUCTURAL_FAILURE, NORMAL_LOSS, LIQUIDITY_REVERSAL, MOMENTUM_SURGE, CLEAN_TREND_RUN).
  - Tự động cộng/trừ điểm thưởng/phạt và tự động nới rộng hệ số đệm SL (`cushion_multiplier = 1.15`) khi phát hiện broker giãn spread.
- **Phase 9: Setup Adaptation & Specialization Engine**:
  - `app/strategy/setup_adapter.py`: Chuẩn hóa 7 setup lõi (`SetupSpecification`) và động cơ `SetupAdapterEngine` tự động thích ứng thông số SL cushion, min R:R, filter requirement theo từng regime cụ thể.
- **Phase 10: Resource Optimization & Stability Shield**:
  - `app/system/resource_optimizer.py`: `ProcessSingletonGuard` (ngăn xung đột đa tiến trình), `BoundedDataCache` (LRU cache kiểm soát RAM), `ResourceProfiler` (đo lường benchmark latency, bộ nhớ).
  - Tối ưu hóa truy vấn nến MT5 chỉ khi có nến mới hình thành (`check_new_candle`), tối ưu kết nối SQLite với WAL mode và batch queries.
- **Phase 11: Comprehensive Verification Suite**:
  - `tests/test_phase11_comprehensive_verification.py`: Bộ kiểm thử hợp nhất 20 kịch bản định lượng bắt buộc (Conflict, Duplicate, Expiry, Invalidation, Regime, Feature Snapshot, Outcome, R-Multiple, MFE/MAE, Data Leakage, Chronological Split, Aggregation, ML Evaluation, Versioning, Promotion, Rollback, Missing Data, Stale Candles, Spread Spike, Unknown Regime).
  - Toàn bộ test suite đạt **436/436 tests passed** (100%), frontend biên dịch hoàn hảo.

---

## [1.2.0] - 2026-10-25

### Economic Calendar & News Blackout Shield Engine
- `app/news/models.py` — Cấu trúc dữ liệu sự kiện kinh tế: `EconomicEvent`, `NewsImpact` (HIGH/MEDIUM/LOW/HOLIDAY), `GoldImpactBias` (BULLISH_GOLD/BEARISH_GOLD/HIGH_VOLATILITY/NEUTRAL).
- `app/news/calendar.py` — `NewsManager`: Tự động đồng bộ nguồn cấp dữ liệu lịch kinh tế toàn cầu từ ForexFactory API, phân tích tính chất tin tức ảnh hưởng lên XAUUSD.
- **Cơ chế Vùng Cấm Giao Dịch Tin Đỏ (News Blackout Shield):**
  - Tự động nhận diện tin tức trọng yếu của Mỹ (USD High Impact: CPI, Non-Farm, FOMC/Lãi suất Fed, GDP, PMI...).
  - Trước 30 phút và sau 20 phút giờ ra tin: Bot tự động tạm dừng phát tín hiệu mới để bảo vệ tài khoản khỏi trượt giá (slippage) và bão giá quét SL 2 đầu.
  - Tích hợp trực tiếp vào vòng lặp `LiveBotRunner.run_once()`.
- `app/api/server.py` — Bổ sung endpoint `GET /api/v1/news/calendar` cung cấp dữ liệu lịch kinh tế và trạng thái blackout thời gian thực cho Desktop Terminal.
- `frontend/src/components/views/EconomicCalendarView.tsx` — Màn hình Lịch Kinh Tế chuyên nghiệp hiển thị đồng hồ đếm ngược tin đỏ tiếp theo, bảng phân tích kỳ vọng tác động lên vàng và bộ lọc đa năng.
- `frontend/src/App.tsx` — Cảnh báo banner đỏ tức thời khi thị trường bước vào vùng nguy hiểm tin đỏ.
- `tests/test_news_calendar.py` — 4 unit tests tự động cho parsing, blackout window và API caching. Tổng test suite đạt 286/286 tests (100%).

---

## [1.1.0] - 2026-10-25

### Standalone Desktop Client (Native Window Terminal) & Frontend UX/UI
- `client.py` — Launcher ứng dụng Desktop chuyên nghiệp độc lập dựa trên `pywebview` (chạy trên Microsoft Edge WebView2 native của Windows). Không cần mở trình duyệt web bên ngoài, không thanh URL, không tab trình duyệt, giao diện Dark Theme mượt mà như TradingView Desktop.
- `run_client.bat` — File thực thi 1-click mở trực tiếp giao diện Desktop trên máy tính Windows.
- `main.py` — Bổ sung cờ lệnh `--client` (`python main.py --client`).
- `tests/test_desktop_client.py` — Bộ kiểm thử tự động 6 tests cho Desktop Client launcher.
- **Tối ưu hóa toàn diện Frontend cho chế độ Client (UX/UI & Kéo giãn mượt mà):**
  - Khóa khung shell `100vh / overflow: hidden` loại bỏ hoàn toàn hiện tượng cuộn kép (double scroll), giữ Topbar và Sidebar cố định tuyệt đối.
  - Vùng nội dung (`.content-area`) cuộn mượt mà độc lập với thanh cuộn sleek và `scrollbar-gutter: stable`.
  - Hệ thống Grid co giãn thích ứng (`.grid-status-cards`, `.grid-2col`, `.telemetry-stack`) tự động tính toán tỷ lệ trên mọi kích thước cửa sổ từ 1024x700 đến 4K mà không bị vỡ layout hay tràn ngang.
  - Chế độ hiển thị thu gọn **Compact Density Mode (`COMP`)** giúp hiển thị toàn bộ chỉ báo và dữ liệu trên 1 màn hình mà không cần cuộn.
  - Bộ điều khiển tần suất nạp dữ liệu (Feed Interval: 5s, 10s, 30s) và nút Fullscreen Trading Desk trên Topbar.
  - Bảng tín hiệu bổ sung bộ lọc trạng thái (ALL / BUY / SELL / ACTIVE), ô tìm kiếm mã tín hiệu tức thì và Sticky Header ghim tiêu đề cột khi cuộn.
  - Xây dựng đầy đủ các màn hình chuyên sâu: `StrategySettingsView`, `MarketAnalysisView`, `SystemMonitoringView`, `TelegramSettingsView`.

---

## [1.0.0] - 2026-10-25

### Full System Release: Phase 9, 10 & 11

#### Phase 9: Machine Learning Engine
- `app/ml/features.py` — `FeatureExtractor`: Trích xuất 14 đặc trưng kỹ thuật chất lượng (RSI, EMA ratios, ATR, Spread/ATR ratio, Candle morphology, Swing distances, Multi-timeframe trend encoding, Session hour).
- `app/ml/dataset.py` — `DatasetBuilder`: Xây dựng tập dữ liệu từ trade records và nến lịch sử, thuật toán `time_series_split` theo trục thời gian không shuffle ngẫu nhiên, chống rò rỉ dữ liệu.
- `app/ml/model.py` — `SignalQualityClassifier`: RandomForestClassifier kết hợp hiệu chuẩn xác suất, tính toán Accuracy, Precision, Recall, F1, ROC-AUC và Brier Score. Lưu/tải mô hình bằng joblib.
- `app/ml/registry.py` — `ModelRegistry`: Quản lý phiên bản và kết quả kiểm định mô hình trong SQLite (`model_versions`, `model_evaluations`). Kiểm duyệt ngưỡng chất lượng trước khi cho phép vào PRODUCTION.
- `app/ml/filter.py` — `MLSignalFilter`: Tích hợp vào Signal Engine để nâng điểm hợp lưu (high confidence >= 60%) hoặc lọc bỏ tín hiệu rủi ro (low confidence < 35%), có fallback an toàn.
- `tests/test_ml_*.py` — 12 unit tests tự động cho features, dataset, classifier, registry, và filter.

#### Phase 10: Demo Forward Testing & Live Bot Runner
- `app/bot/runner.py` — `LiveBotRunner`: Động cơ điều phối vòng lặp thời gian thực:
  - Tự động nhận diện nến M5 mới (New bar detection) để phân tích setup.
  - Phân tích đa khung thời gian (H4, H1, M15, M5) và lọc qua ML.
  - Quản lý trạng thái lệnh (Entry ±1 giá, Lãi 5 giá kéo SL hòa vốn, Lãi 10 giá chốt 50% TP1 nuôi TP2).
  - Tự động gửi thông báo Telegram tức thì và cập nhật trạng thái lệnh.
  - Lưu trữ bền vững vào SQLite (`signals`, `signal_features`, `signal_outcomes`).
- `main.py` — Nâng cấp toàn diện CLI hỗ trợ `--check`, `--once`, `--server`, `--interval` và vòng lặp `run_forever()`.
- `tests/test_bot_runner.py` — 3 unit tests cho LiveBotRunner.

#### Phase 11: Hosting, Monitoring & Operations Tooling
- `scripts/backup_db.py` — Sao lưu nóng trực tuyến (Online SQLite Backup) bảo đảm ACID, tự động xoay vòng giữ lại 14 bản gần nhất.
- `scripts/health_check.py` — Chẩn đoán sức khỏe hệ thống: MT5, SQLite integrity check, Telegram, RAM, CPU, dung lượng đĩa.
- `run_bot.bat` — 1-click launcher cho Live Bot Runner trên Windows.
- `run_dashboard.bat` — 1-click launcher cho cả API Server và UI Dashboard.
- `backup.bat` — 1-click launcher cho sao lưu cơ sở dữ liệu.
- `docs/DEPLOYMENT_GUIDE.md` — Hướng dẫn chi tiết vận hành 24/7 trên Windows 11 / Windows VPS qua Task Scheduler hoặc Windows Service (NSSM).

---

## [0.9.0] - 2026-10-25

### Phase 8: Trading Terminal Dashboard & REST API
- `app/api/server.py` — Máy chủ FastAPI cung cấp 5 endpoints REST API trực tiếp kết nối MetaTrader 5 Terminal và SQLite Database (`/dashboard/overview`, `/market/overview`, `/signals`, `/system/metrics`, `/performance`).
- `frontend/` — Giao diện Web Trading Terminal chuyên nghiệp xây dựng bằng React 19 + TypeScript + Vite + Vanilla CSS design system tối ưu tài nguyên:
  - Nền Dark Mode chuẩn institutional `#0B0F19`, font Inter và JetBrains Mono.
  - Sidebar 12 menu điều hướng, Topbar thời gian thực, 8 thẻ trạng thái Status Cards.
  - Ma trận xu hướng đa khung thời gian H4, H1, M15, M5 và phân tích cấu trúc nến.
  - Bảng tín hiệu gần nhất kết nối trực tiếp SQLite, Modal chi tiết hiển thị quy tắc vào lệnh.
  - Giám sát CPU/RAM qua `psutil` không rò rỉ bộ nhớ.
  - Đã kiểm thử trình duyệt thực tế đạt 0 lỗi console.

---

## [0.8.0] - 2026-10-25

### Phase 7: Backtest Engine

#### Thêm mới
- `app/backtest/models.py` — Cấu trúc dữ liệu mô phỏng: `BacktestConfig` (cấu hình vốn, lot, spread, slippage, quy tắc quản lý lệnh), `TradeStatus`, `TradeRecord` (nhật ký lệnh MFE, MAE, Breakeven, chốt 50% TP1), `BacktestResult` (báo cáo tổng thể).
- `app/backtest/metrics.py` — Bộ tính toán chỉ số hiệu suất: Tỷ lệ thắng (Win rate), Hệ số lợi nhuận (Profit Factor), Lợi nhuận ròng (cash & points), Maximum Drawdown ($ và %), Sharpe Ratio, chuỗi thắng/thua liên tiếp, đường cong vốn (Equity Curve).
- `app/backtest/historical_loader.py` — Tiện ích xử lý dữ liệu lịch sử `HistoricalLoader`: làm sạch, sắp xếp, tính toán indicators, căn chỉnh đa khung thời gian (`align_multi_timeframe`) tuyệt đối không look-ahead bias (`time < current_exec_time`).
- `app/backtest/engine.py` — `BacktestEngine` mô phỏng khớp lệnh Bar-by-bar tuần tự:
  - Khớp lệnh chân thực theo vùng Entry, tính toán Spread & Slippage.
  - Quy tắc quản lý lệnh vàng thực chiến: Lãi 5 giá tự động dời SL về hòa vốn (Breakeven).
  - Chạm TP1 (10 giá): Chốt 50% khối lượng, kéo SL dương nuôi TP2.
  - Ghi nhận biến động cực đại trong lệnh: MFE (Max Favorable Excursion) và MAE (Max Adverse Excursion).
- `app/backtest/walk_forward.py` — `WalkForwardAnalyzer` và `WalkForwardReport`: phân tích Walk-Forward kiểm tra độ ổn định và tính nhất quán (Consistency Rate) của chiến lược qua nhiều chu kỳ thị trường độc lập.
- `app/backtest/__init__.py` — Package export các thành phần backtest.
- `tests/test_backtest_models.py` — 4 unit tests cho models và TradeRecord status.
- `tests/test_backtest_metrics.py` — 4 unit tests cho tính toán win rate, profit factor, drawdown, Sharpe ratio.
- `tests/test_backtest_loader.py` — 4 unit tests cho clean data, deduplication, căn chỉnh multi-timeframe.
- `tests/test_backtest_engine.py` — 4 unit tests cho Bar-by-bar engine, spread/slippage, breakeven trigger, partial TP.
- `tests/test_backtest_walk_forward.py` — 2 unit tests cho Walk-Forward analyzer và báo cáo phân đoạn.
- `tests/integration_backtest.py` — Integration test kiểm thử đầu cuối trên nến M5 & H1 thật từ MT5.

#### Kỹ thuật & Tối ưu
- Tuyệt đối loại bỏ Look-ahead bias: tại nến `i` khung M5, khung xu hướng H1 chỉ được phép nhìn thấy các nến đã đóng trước `time[i]`.
- Event-driven simulation bám sát thực tế thị trường vàng.
- Nâng tổng số unit test tự động lên **260/260 tests PASSED 100%**.

---

## [0.7.0] - 2026-10-25

### Phase 6: Database

#### Thêm mới
- `app/database/connection.py` — `DatabaseManager` quản lý kết nối SQLite, tự động tạo thư mục `data/`, cấu hình PRAGMA WAL mode, foreign keys, busy timeout và session context manager. Hỗ trợ persistent in-memory database cho testing.
- `app/database/schema.py` — Schema DDL tạo toàn bộ 8 bảng: `signals`, `signal_features`, `signal_outcomes`, `market_data`, `strategy_versions`, `model_versions`, `model_evaluations`, `schema_migrations` và các indexes truy vấn nhanh.
- `app/database/migrations.py` — Migration runner tự động nhận diện version, áp dụng tuần tự các migration, ghi log an toàn.
- `app/database/repository.py` — Repositories:
  - `SignalRepository`: CRUD tín hiệu, đặc trưng ML features, cập nhật kết quả outcomes và thống kê.
  - `MarketDataRepository`: Lưu trữ nến OHLCV đa khung thời gian với cơ chế chống trùng lặp timestamp, truy vấn nến phục vụ backtest.
  - `StrategyRepository`: Quản lý và kích hoạt phiên bản chiến lược.
- `app/database/__init__.py` — Package export các thành phần database.
- `tests/test_database_connection.py` — 5 unit tests cho connection manager, parse URL, commit/rollback.
- `tests/test_database_migrations.py` — 3 unit tests cho migration runner, schema verification, idempotency.
- `tests/test_database_repository.py` — 8 unit tests cho SignalRepository, MarketDataRepository, StrategyRepository.
- `tests/integration_database.py` — Integration test trên file database thật `data/vietkey_gold.db`, nến M5 thật từ MT5.

#### Kỹ thuật & Tối ưu
- Sử dụng `sqlite3` từ thư viện chuẩn Python (Zero external dependencies).
- Bật WAL (Write-Ahead Logging) cho khả năng đọc/ghi đồng thời tối ưu.
- Tự động đồng bộ trạng thái giữa `signals` và `signal_outcomes`.
- Chuẩn bị sẵn bảng `model_versions` và `model_evaluations` cho AI/ML Phase 9.

---

## [0.6.0] - 2026-10-25

### Phase 5: Telegram Notification

#### Thêm mới
- `app/telegram/formatter.py` — Định dạng tin nhắn HTML an toàn, chuyên nghiệp cho BUY, SELL, WAIT, các cập nhật trạng thái (ENTRY_REACHED, TP_REACHED, SL_REACHED, INVALIDATED, EXPIRED) và thông báo hệ thống.
- `app/telegram/client.py` — Telegram API Client giao tiếp qua thư viện chuẩn `urllib` (zero external dependencies), hỗ trợ retry exponential backoff, xử lý rate limit (HTTP 429), `get_me` và `verify_connection`.
- `app/telegram/notifier.py` — Telegram Notifier điều phối gửi tín hiệu, hỗ trợ bật/tắt (toggle `enable`/`disable`), duplicate protection và lọc theo cấu hình `send_wait_signals`.
- `app/telegram/__init__.py` — Package export các thành phần Telegram.
- `tests/test_telegram_formatter.py` — 9 unit tests cho formatting HTML.
- `tests/test_telegram_client.py` — 10 unit tests cho Telegram API client và network handling.
- `tests/test_telegram_notifier.py` — 9 unit tests cho notifier logic, duplicate protection và toggle state.
- `tests/integration_telegram.py` — Integration test kiểm tra kết nối thật hoặc chạy dry-run mô phỏng an toàn.

#### Kỹ thuật & An toàn
- Sử dụng HTML format thay vì Markdown để tránh các lỗi parse ký tự đặc biệt.
- Zero dependencies — sử dụng `urllib.request` từ thư viện chuẩn Python.
- Duplicate Protection — không bao giờ gửi 2 lần cùng một trạng thái của tín hiệu.
- An toàn tuyệt đối: Không crash luồng giao dịch chính nếu Telegram gặp sự cố mạng hoặc chưa cấu hình token.

---

## [0.5.0] - 2026-10-25

### Phase 4: Signal Engine

#### Thêm mới
- `app/strategy/signal_models.py` — Data models: `SignalDirection` (BUY/SELL/WAIT), `SignalStatus`, `TradingSignal` với đầy đủ entry, SL, TP1, TP2, R:R, score, confidence, reasons, invalidation.
- `app/strategy/setup_detector.py` — Phát hiện setup candidates: EMA Bounce, BOS Retest, RSI Divergence/Extreme. Tính entry, SL, TP theo ATR.
- `app/strategy/risk_filter.py` — Bộ lọc đa tầng: R:R filter (tối thiểu 1:1.5), Trend alignment H4, Spread filter, Volatility filter, Score filter.
- `app/strategy/signal_scoring.py` — Hệ thống chấm điểm Confluence (0-100) theo 5 tiêu chí: Trend, Structure, Indicators, R:R, Volatility. Phân loại Confidence: LOW / MEDIUM / HIGH.
- `app/strategy/signal_tracker.py` — Quản lý vòng đời tín hiệu (ACTIVE → ENTRY_REACHED → TP/SL/INVALIDATED/EXPIRED), Duplicate Protection và Cooldown chống spam.
- `app/strategy/signal_engine.py` — Bộ điều phối trung tâm: phân tích đa khung thời gian (H4, H1, M15), chạy setup detection, risk filter, scoring, duplicate check và cập nhật trạng thái giá real-time.
- `tests/test_signal_models.py` — 6 tests cho data models.
- `tests/test_setup_detector.py` — 8 tests cho setup detection logic.
- `tests/test_risk_filter.py` — 8 tests cho các bộ lọc rủi ro.
- `tests/test_signal_scoring.py` — 5 tests cho confluence scoring & confidence.
- `tests/test_signal_tracker.py` — 11 tests cho tracking vòng đời tín hiệu và duplicate filter.
- `tests/test_signal_engine.py` — 7 tests cho end-to-end SignalEngine.
- `tests/integration_signal.py` — Integration test trên dữ liệu nến XAUUSD thật từ MT5.

#### Kỹ thuật & An toàn
- Tuyệt đối không tự động đặt lệnh.
- Không tuyên bố xác suất thắng (win probability) — Score là điểm confluence kỹ thuật.
- Duplicate Protection ngăn chặn tín hiệu trùng lặp trong thời gian cooldown.
- Toàn bộ 198 unit tests passed, integration test trên dữ liệu MT5 thật passed.

---

## [0.4.0] - 2026-10-25

### Phase 3: Technical Analysis Engine

#### Thêm mới
- `app/market/indicators.py` — EMA (20/50/200), RSI (Wilder), ATR (True Range + Wilder smoothing).
- `app/market/market_structure.py` — Swing H/L, HH/HL/LH/LL, BOS, CHoCH, S/R zones.
- `app/market/volatility.py` — ATR-based volatility (LOW/NORMAL/HIGH/EXTREME), spread monitoring, candle range, body ratio.
- `tests/test_indicators.py` — 21 tests cho indicators.
- `tests/test_market_structure.py` — 16 tests cho market structure.
- `tests/test_volatility.py` — 17 tests cho volatility.
- `tests/integration_analysis.py` — Integration test trên dữ liệu XAUUSD thật.

#### Kỹ thuật
- Không look-ahead bias (swing detection chờ right_bars xác nhận).
- Không mutate input DataFrame.
- Tự implement indicators (không phụ thuộc pandas-ta/TA-Lib).
- Wilder's smoothing cho RSI và ATR.

#### Kết quả test
- 153/153 unit tests passed.
- Integration: H4=BEARISH RSI=27.7, H1=NEUTRAL RSI=36.4, M15=NEUTRAL RSI=40.5.

---

## [0.3.0] - 2026-10-25

### Phase 2: Market Data Engine

#### Thêm mới
- `app/market/__init__.py` — Market module package.
- `app/market/timeframe_manager.py` — Timeframe enum (M5/M15/H1/H4/D1) với MT5 constant mapping, defaults.
- `app/market/data_manager.py` — Lấy OHLCV từ MT5, loại nến chưa đóng, validate dữ liệu, cache, latest price.
- `tests/test_timeframe.py` — 12 tests cho timeframe manager.
- `tests/test_market_data.py` — 22 tests cho data manager + validation.
- `tests/integration_market.py` — Integration test lấy dữ liệu thật (8 tests).

#### Data Validation
- Kiểm tra timestamp trùng.
- Kiểm tra nến tương lai (look-ahead).
- Kiểm tra OHLC hợp lệ (high >= low, etc.).
- Ước tính nến thiếu.
- Loại bỏ nến chưa đóng mặc định.

#### Kết quả test
- 99/99 unit tests passed (mock).
- 8/8 integration tests passed (MT5 thật).

---

## [0.2.0] - 2026-10-25

### Phase 1: MT5 Connector

#### Thêm mới
- `app/__init__.py` — App package.
- `app/mt5/__init__.py` — MT5 module package.
- `app/mt5/connector.py` — Kết nối MT5 với retry exponential backoff, context manager, graceful shutdown.
- `app/mt5/account_info.py` — Lấy thông tin tài khoản (chỉ đọc), cảnh báo nếu tài khoản REAL.
- `app/mt5/symbol_info.py` — Kiểm tra symbol, tự thêm vào Market Watch, lấy bid/ask/spread.
- `tests/test_mt5_connector.py` — 18 mock tests cho connector.
- `tests/test_mt5_account.py` — 7 mock tests cho account info.
- `tests/test_mt5_symbol.py` — 10 mock tests cho symbol info.
- `tests/integration_mt5.py` — Script integration test (chạy thủ công với MT5 thật).

#### Sửa lỗi
- `connector.py` — Fix `is_connected` không reset `_connected` flag khi `terminal_info()` trả `None`.

#### Kết quả test
- 65/65 tests passed (tất cả mock — không cần MT5 thật).

---

## [0.1.1] - 2026-10-25

### Phase 0: Cập nhật theo kế hoạch đầy đủ V1.0

#### Thay đổi
- `.env.example` — Đổi `MT5_PATH` → `MT5_TERMINAL_PATH`, thêm `MT5_SYMBOL`, `DATABASE_URL`, `AI_PROVIDER`, `AI_API_KEY`.
- `config.py` — Thêm `DatabaseConfig`, `MT5Config.symbol`, đổi `path` → `terminal_path`.
- `main.py` — Dùng `settings.mt5.symbol`.
- Tests cập nhật theo config mới.
- Docs cập nhật với kế hoạch V1.0 đầy đủ.

---

## [0.1.0] - 2026-10-25

### Phase 0: Environment Setup

#### Thêm mới
- `config.py` — Module cấu hình từ `.env`, frozen dataclass.
- `logger.py` — Logging console + file handler.
- `main.py` — Entry point kiểm tra môi trường.
- `requirements.txt` — Dependencies.
- `.env.example`, `.gitignore`, `README.md`.
- `docs/PROJECT_PLAN.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`.
- `tests/test_config.py`, `tests/test_logger.py`, `tests/test_main.py`.
- Virtual environment Python 3.14.
