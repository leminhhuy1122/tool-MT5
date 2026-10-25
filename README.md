# VietKey Gold AI

> Hệ thống AI phân tích tín hiệu giao dịch vàng XAUUSD bằng MetaTrader 5.

## Tổng quan

VietKey Gold AI là hệ thống AI hỗ trợ phân tích thị trường vàng (XAUUSD) sử dụng:

- **MetaTrader 5** — Kết nối dữ liệu thị trường.
- **Technical Analysis** — Phân tích đa timeframe (H4, H1, M15, M5).
- **Signal Engine** — Phát hiện setup và phát tín hiệu BUY/SELL/WAIT.
- **Telegram** — Gửi tín hiệu tới người dùng.
- **Database** — Lưu lịch sử và theo dõi kết quả.
- **Machine Learning** — Nâng cao độ chính xác (phase sau).

⚠️ **Hệ thống CHỈ phát tín hiệu tham khảo. KHÔNG tự động đặt lệnh.**

## Yêu cầu

- Windows 10/11
- Python 3.14+
- MetaTrader 5 Terminal (đã cài và đăng nhập)

## Cài đặt

```bash
# 1. Clone repository
git clone <repo-url>
cd "chibao MT5"

# 2. Tạo virtual environment
py -3.14 -m venv venv

# 3. Kích hoạt virtual environment
.\venv\Scripts\activate

# 4. Cài đặt dependencies
pip install -r requirements.txt

# 5. Tạo file .env từ template
copy .env.example .env
# Mở .env và điền thông tin MT5, Telegram

# 6. Chạy kiểm tra
python main.py
```

## Cấu trúc project (Phase 0)

```
chibao MT5/
├── main.py              # Entry point
├── config.py            # Cấu hình (đọc từ .env)
├── logger.py            # Logging setup
├── requirements.txt     # Dependencies
├── .env.example         # Template biến môi trường
├── .gitignore           # Git ignore rules
├── tests/               # Unit tests
│   ├── test_config.py
│   ├── test_logger.py
│   └── test_main.py
├── docs/                # Tài liệu dự án
│   ├── PROJECT_PLAN.md
│   ├── ARCHITECTURE.md
│   └── CHANGELOG.md
└── logs/                # Log files (tự tạo khi chạy)
```

## Chạy tests

```bash
.\venv\Scripts\activate
pytest tests/ -v
```

## Trạng thái dự án

| Phase | Tên | Trạng thái |
|-------|-----|------------|
| 0 | Environment Setup | ✅ Hoàn thành |
| 1 | MT5 Connector | ⏳ Chờ triển khai |
| 2 | Market Data Engine | ⏳ |
| 3 | Technical Analysis Engine | ⏳ |
| 4 | Signal Engine | ⏳ |
| 5 | Telegram Notification | ⏳ |
| 6 | Database | ⏳ |
| 7 | Backtest | ⏳ |
| 8 | Dashboard | ⏳ |
| 9 | Machine Learning | ⏳ |
| 10 | Demo Forward Testing | ⏳ |
| 11 | Hosting và Monitoring | ⏳ |

## Cấu hình (.env)

| Biến | Mô tả | Bắt buộc |
|------|--------|----------|
| `MT5_LOGIN` | Số tài khoản MT5 | Phase 1 |
| `MT5_PASSWORD` | Mật khẩu MT5 | Phase 1 |
| `MT5_SERVER` | Tên server MT5 | Phase 1 |
| `MT5_TERMINAL_PATH` | Đường dẫn terminal64.exe | Tùy chọn |
| `MT5_SYMBOL` | Symbol giao dịch | Mặc định: XAUUSD |
| `TELEGRAM_BOT_TOKEN` | Token Telegram Bot | Phase 5 |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram | Phase 5 |
| `DATABASE_URL` | Connection string DB | Phase 6 |
| `LOG_LEVEL` | Mức log | Mặc định: INFO |

## Quy tắc an toàn

1. ❌ Không tự động đặt lệnh.
2. ❌ Không giao dịch tài khoản thật.
3. ❌ Không lưu API key/token trong source code.
4. ❌ Không tự thay đổi chiến lược live.
5. ✅ Chỉ phát tín hiệu tham khảo.
6. ✅ Tất cả cấu hình nhạy cảm nằm trong `.env`.
7. ✅ Mọi phiên bản mới phải backtest + demo forward test.

## Tài liệu

- [Kế hoạch dự án](docs/PROJECT_PLAN.md)
- [Kiến trúc hệ thống](docs/ARCHITECTURE.md)
- [Changelog](docs/CHANGELOG.md)

## License

Private — Không phân phối.
