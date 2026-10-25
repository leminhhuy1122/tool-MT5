@echo off
chcp 65001 > nul
title VietKey Gold AI — Dashboard & API Server

echo ============================================================
echo   VIETKEY GOLD AI — KHỞI CHẠY DASHBOARD & REST API (PHASE 8)
echo ============================================================
echo.

set PYTHON_EXE=%~dp0venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [LỖI] Không tìm thấy virtualenv tại: %~dp0venv
    pause
    exit /b 1
)

echo [1/2] Đang khởi động Backend API Server (port 8000)...
start "VietKey Gold API Server" "%PYTHON_EXE%" -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000

timeout /t 2 /nobreak > nul

echo [2/2] Đang khởi động Frontend Terminal Dashboard (port 5173)...
cd /d "%~dp0frontend"
start "VietKey Gold Web Terminal" npm run dev

echo.
echo ============================================================
echo   DASHBOARD ĐÃ KHỞI CHẠY THÀNH CÔNG!
echo   • API Backend: http://127.0.0.1:8000
echo   • UI Terminal: http://localhost:5173/
echo ============================================================
echo.
pause
