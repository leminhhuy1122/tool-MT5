# VietKey Gold AI — Kế hoạch dự án

**Phiên bản:** V1.0
**Mục tiêu:** Xây dựng AI Trading Signal Scanner
**Nền tảng:** Windows 11, Python, MetaTrader 5
**Chế độ:** Phân tích thị trường và phát tín hiệu, không tự động đặt lệnh

---

## 1. Tổng quan

VietKey Gold AI là hệ thống AI hỗ trợ phân tích thị trường vàng XAUUSD.

Hệ thống kết nối MetaTrader 5 để lấy dữ liệu giá, phân tích nhiều khung thời gian,
nhận diện cấu trúc thị trường, tìm kiếm các cơ hội giao dịch và gửi tín hiệu BUY, SELL hoặc WAIT.

### 1.1. Mục tiêu chính

- Kết nối MetaTrader 5.
- Lấy dữ liệu giá XAUUSD realtime.
- Phân tích nhiều khung thời gian.
- Nhận diện xu hướng và cấu trúc thị trường.
- Phát hiện các setup giao dịch tiềm năng.
- Đánh giá chất lượng tín hiệu.
- Phát tín hiệu BUY, SELL hoặc WAIT.
- Đề xuất vùng Entry, Stop Loss và Take Profit.
- Gửi tín hiệu qua Telegram.
- Lưu dữ liệu và kết quả tín hiệu.
- Xây dựng hệ thống backtest.
- Đánh giá hiệu suất chiến lược.
- Huấn luyện mô hình AI từ dữ liệu lịch sử.
- Quản lý phiên bản chiến lược và mô hình.
- Xây dựng dashboard theo dõi hoạt động.

### 1.2. Phạm vi V1

V1 chỉ tập trung vào: **AI phân tích thị trường và phát tín hiệu.**

Không triển khai:
- Tự động đặt lệnh BUY/SELL trên tài khoản thật.
- Tự động tăng lot / Martingale.
- Cam kết tỷ lệ thắng.
- Tự động thay đổi chiến lược live.

---

## 2. Các phase triển khai

### Phase 0: Environment Setup ✅
- Python virtual environment.
- Dependencies.
- Config từ .env (MT5, Telegram, Database, AI).
- Logging (console + file).
- Unit tests.

### Phase 1: MT5 Connector ✅
- Kết nối MetaTrader 5 terminal.
- Kiểm tra terminal, symbol XAUUSD.
- Lấy account information (chỉ đọc).
- Lấy historical candles, tick data.
- Retry connection với backoff.
- Logging kết nối.
- **Không có chức năng đặt lệnh.**

### Phase 2: Market Data Engine ✅
- Dữ liệu OHLCV + Bid/Ask/Spread.
- Khung thời gian: H4, H1, M15, M5.
- Data validation (thiếu nến, trùng timestamp, spread).
- Cache và synchronization.
- **Không sử dụng dữ liệu tương lai.**

### Phase 3: Technical Analysis Engine ✅
- Trend: EMA 20/50/200, HH/HL, LH/LL.
- Market Structure: BOS, CHoCH, Swing H/L, S/R.
- Liquidity: sweep, equal H/L.
- Price Action: engulfing, rejection, breakout, retest.
- Volatility: ATR, biên độ nến, spread.
- **Unit test cho mỗi indicator, không có look-ahead bias.**

### Phase 4: Signal Engine ✅
- Setup detection + entry confirmation.
- Filters: trend, structure, spread, volatility, R:R, session, duplicate.
- Signal scoring (chưa phải xác suất thắng).
- Tín hiệu: BUY/SELL/WAIT với entry zone, SL, TP, reason, invalidation.
- Strategy version tracking.

### Phase 5: Telegram Notification ✅
- Telegram Bot API.
- Định dạng tin nhắn chuẩn vàng: Entry ±1 giá, lãi 5 giá kéo SL hòa vốn, lãi 10 giá chốt 50% TP1 nuôi TP2.
- Gửi tín hiệu mới, cập nhật trạng thái lệnh.
- Duplicate protection.
- Có thể bật/tắt.

### Phase 6: Database ✅
- SQLite với Write-Ahead Logging (WAL mode).
- 8 Bảng: signals, signal_features, signal_outcomes, market_data, strategy_versions, model_versions, model_evaluations, schema_migrations.
- Migration runner tự động.
- Repositories: SignalRepository, MarketDataRepository, StrategyRepository.

### Phase 7: Backtest Engine ✅
- Historical loader (khử look-ahead bias đa khung thời gian).
- Backtest engine Bar-by-bar (khớp lệnh, spread, slippage, quy tắc kéo SL hòa vốn 5 giá, chốt 50% TP1 10 giá).
- Performance metrics toàn diện (Win rate, Profit factor, Drawdown, Sharpe ratio, Equity curve).
- Walk-forward evaluation (3 chu kỳ kiểm tra tính nhất quán).

### Phase 8: Trading Terminal Dashboard & REST API ✅
- Backend REST API FastAPI (`app/api/server.py`) kết nối trực tiếp MT5 và SQLite.
- Frontend React 19 + TypeScript + Vite + Vanilla CSS (`frontend/`) chuẩn Institutional Terminal dark mode.
- 8 Status Cards, Market Overview đa khung, Bảng tín hiệu live, Modal chi tiết, System Telemetry.

### Phase 9: Machine Learning Engine ✅
- Feature engineering (`FeatureExtractor` với 14 đặc trưng kỹ thuật).
- Dataset builder (`time_series_split` theo thời gian không look-ahead).
- Signal quality classifier (`RandomForestClassifier` hiệu chuẩn xác suất).
- Model registry (`model_versions`, `model_evaluations` trong SQLite).
- ML Signal Filter tích hợp an toàn vào Signal Engine.

### Phase 10: Demo Forward Testing & Live Bot Runner ✅
- `LiveBotRunner`: Chạy real-time tự động trên MT5 demo/live.
- Nhận diện nến M5 mới, phân tích setup đa khung thời gian, lọc ML.
- Theo dõi trạng thái lệnh: Entry ±1 giá, kéo SL hòa vốn khi lãi 5 giá, chốt 50% TP1 khi lãi 10 giá, gồng TP2.
- Tự động phát tín hiệu, gửi Telegram và lưu trữ SQLite.
- **Không tự động đặt lệnh tiền thật (Chỉ phát tín hiệu tham khảo).**

### Phase 11: Hosting, Monitoring & Operations ✅
- Scripts sao lưu nóng online SQLite (`scripts/backup_db.py`).
- Scripts chẩn đoán sức khỏe hệ thống (`scripts/health_check.py`).
- Windows 1-click launchers: `run_bot.bat`, `run_dashboard.bat`, `backup.bat`.
- Tài liệu vận hành chi tiết: `docs/DEPLOYMENT_GUIDE.md`.

---

## 3. Quy trình hoạt động

1. Kết nối MT5.
2. Thu thập dữ liệu thị trường (H4/H1/M15/M5).
3. Phân tích thị trường (trend, structure, liquidity, PA, volatility).
4. Phát hiện setup (BUY/SELL candidate hoặc WAIT).
5. Lọc tín hiệu (trend/structure/spread/volatility/R:R filter).
6. Chấm điểm setup (score, không phải xác suất thắng).
7. Phát tín hiệu (entry zone, SL, TP, reason, invalidation).
8. Gửi Telegram.
9. Theo dõi tín hiệu (ACTIVE → TP_REACHED/SL_REACHED/INVALIDATED/EXPIRED/UNRESOLVED).
10. Lưu dữ liệu.
11. Đánh giá hiệu suất.
12. AI Learning Pipeline.

---

## 4. Resource Optimization

- Chỉ lấy số lượng nến cần thiết.
- Không polling liên tục khi không cần.
- Phân tích lại chỉ khi có nến mới.
- Ưu tiên xử lý incremental.
- Không train model trong vòng lặp realtime.
- Shutdown an toàn, không thread vô hạn.
- Resource monitoring: RAM, CPU, uptime, latency.

---

## 5. Nguyên tắc phát triển

1. Triển khai tuần tự — không bỏ qua phase.
2. Mỗi phase có unit tests.
3. Không tự động đặt lệnh.
4. Cấu hình nhạy cảm trong .env.
5. Code clean, type hints, docstrings.
6. Cập nhật README, CHANGELOG.
7. Báo cáo sau mỗi phase.
8. Chờ xác nhận trước khi chuyển phase.
