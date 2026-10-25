@echo off
chcp 65001 > nul
title VietKey Gold AI — Database Backup

echo ============================================================
echo   VIETKEY GOLD AI — SAO LƯU DATABASE TỰ ĐỘNG (PHASE 11)
echo ============================================================
echo.

"%~dp0venv\Scripts\python.exe" "%~dp0scripts\backup_db.py"

echo.
pause
