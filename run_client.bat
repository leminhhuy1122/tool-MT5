@echo off
chcp 65001 > nul
title VietKey Gold AI — Standalone Desktop Terminal

echo ============================================================
echo   VIETKEY GOLD AI — DESKTOP CLIENT (NATIVE TERMINAL)
echo ============================================================
echo.

set PYTHON_EXE=%~dp0venv\Scripts\python.exe
set DIST_DIR=%~dp0frontend\dist

if not exist "%PYTHON_EXE%" (
    echo [LỖI] Không tìm thấy virtualenv tại: %~dp0venv
    echo Vui lòng tạo virtualenv và cài đặt thư viện trước khi chạy.
    pause
    exit /b 1
)

if not exist "%DIST_DIR%\index.html" (
    echo [THÔNG BÁO] Chưa tìm thấy bản build giao diện. Đang tự động build...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0"
    echo.
)

echo Đang khởi chạy ứng dụng Desktop VietKey Gold AI...
echo (Cửa sổ ứng dụng độc lập sẽ hiển thị trong giây lát...)
echo.

"%PYTHON_EXE%" client.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [THÔNG BÁO] Ứng dụng đã kết thúc hoặc có lỗi.
    pause
)
