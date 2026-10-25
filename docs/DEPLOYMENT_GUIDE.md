# VietKey Gold AI — Hướng Dẫn Vận Hành & Triển Khai (Phase 11)

Tài liệu hướng dẫn chi tiết quy trình triển khai, chạy tự động 24/7 và giám sát hệ thống trên **Windows 11 Local** hoặc **Windows VPS**.

---

## 1. Yêu Cầu Môi Trường
- **Hệ điều hành:** Windows 10/11 64-bit hoặc Windows Server 2022 VPS.
- **Python:** Phiên bản 3.10+ (Đã cấu hình ảo hóa tại thư mục `venv/`).
- **Node.js:** Phiên bản 18+ (cho Frontend Dashboard).
- **MetaTrader 5 Terminal:** Đã đăng nhập tài khoản broker và mở sẵn terminal.

---

## 2. Cấu Trúc Khởi Động Nhanh (1-Click Launchers)

| Tập tin | Chức năng | Lệnh tương đương |
|---|---|---|
| [`run_client.bat`](file:///d:/dung/chibao%20MT5/run_client.bat) | **Mở Desktop Client độc lập** (Native Window, không cần trình duyệt web) | `python client.py` hoặc `python main.py --client` |
| [`run_bot.bat`](file:///d:/dung/chibao%20MT5/run_bot.bat) | Khởi chạy Live Bot Engine giám sát nến M5 và phát tín hiệu theo thời gian thực | `python main.py` |
| [`run_dashboard.bat`](file:///d:/dung/chibao%20MT5/run_dashboard.bat) | Khởi chạy đồng thời API Server (port 8000) và Web Dashboard (port 5173) | `uvicorn app.api.server:app` + `npm run dev` |
| [`backup.bat`](file:///d:/dung/chibao%20MT5/backup.bat) | Sao lưu nóng cơ sở dữ liệu SQLite tức thì vào `data/backups/` | `python scripts/backup_db.py` |

---

## 3. Triển Khai Tự Động Chạy 24/7 Trên Windows VPS

### Cách 1: Thiết lập tự động khởi động cùng Windows (Task Scheduler)
1. Mở **Windows Task Scheduler** (`taskschd.msc`).
2. Chọn **Create Task**:
   - Tab **General**: Đặt tên `VietKey_Gold_Bot`, tích chọn *"Run with highest privileges"*.
   - Tab **Triggers**: Chọn *"At log on"* hoặc *"At startup"*.
   - Tab **Actions**:
     - Action: *Start a program*
     - Program/script: `d:\dung\chibao MT5\run_bot.bat`
     - Start in: `d:\dung\chibao MT5`
   - Tab **Settings**: Tích chọn *"If the task fails, restart every 1 minute"*.

### Cách 2: Chạy như Windows Service (khuyến nghị cho VPS)
Sử dụng công cụ **NSSM** (Non-Sucking Service Manager):
```bat
nssm install VietKeyGoldBot "d:\dung\chibao MT5\venv\Scripts\python.exe" "d:\dung\chibao MT5\main.py"
nssm set VietKeyGoldBot AppDirectory "d:\dung\chibao MT5"
nssm start VietKeyGoldBot
```

---

## 4. Tự Động Hóa Sao Lưu Database (Daily Backup)
Để tự động sao lưu dữ liệu mỗi ngày lúc 00:00:
1. Mở **Task Scheduler**.
2. Tạo task `VietKey_Daily_Backup`:
   - Trigger: Hàng ngày lúc `00:00:00`.
   - Action: `d:\dung\chibao MT5\venv\Scripts\python.exe d:\dung\chibao MT5\scripts\backup_db.py`
3. Hệ thống sẽ tự động tạo file snapshot `data/backups/vietkey_gold_YYYYMMDD_HHMMSS.db` và xoay vòng giữ lại 14 ngày gần nhất.

---

## 5. Chẩn Đoán & Kiểm Tra Sức Khỏe (Health Check)
Chạy lệnh kiểm tra định kỳ:
```bat
python scripts/health_check.py
```
Lệnh sẽ kiểm tra tính toàn vẹn SQLite (`PRAGMA integrity_check`), kết nối MT5 Terminal và lượng tài nguyên RAM/CPU.
