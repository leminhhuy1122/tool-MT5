@echo off
chcp 65001 > nul
title VietKey Gold AI — Live Bot Engine

echo ============================================================
echo   VIETKEY GOLD AI — KHỞI CHẠY LIVE BOT RUNNER (PHASE 10)
echo ============================================================
echo.

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [LỖI] Không tìm thấy virtualenv tại: %~dp0venv
    pause
    exit /b 1
)

echo Đang khởi động Live Signal Engine...
"%~dp0venv\Scripts\python.exe" "%~dp0main.py"

pause
