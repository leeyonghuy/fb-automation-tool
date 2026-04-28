@echo off
chcp 65001 >nul
title Facebook Automation Tool

echo.
echo [*] Khoi dong Facebook Automation Tool...
echo [*] Dam bao IX Browser dang chay truoc!
echo.

:: Chuyen den thu muc chua script
cd /d "%~dp0"

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Python chua cai dat. Chay SETUP_NHANVIEN.bat truoc!
    pause
    exit /b 1
)

:: Chay app
echo [*] Dang khoi dong Web UI...
echo [*] Sau khi thay "Running on http://..." thi mo trinh duyet:
echo [*] http://localhost:5000
echo.
python app.py

pause
