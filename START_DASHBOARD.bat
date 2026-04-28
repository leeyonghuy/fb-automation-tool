@echo off
title ContenFactory Dashboard
color 0A
echo.
echo  ============================================
echo   ContenFactory Dashboard - Khoi dong...
echo  ============================================
echo.

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Python chua duoc cai dat!
    pause
    exit /b 1
)

:: Cai Flask neu chua co
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Dang cai Flask...
    pip install flask -q
)

:: Cai requests neu chua co
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Dang cai requests...
    pip install requests -q
)

echo [OK] Tat ca thu vien san sang
echo.
echo  Dashboard: http://localhost:5555
echo  Nhan Ctrl+C de dung
echo.

:: Mo trinh duyet sau 2 giay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5555"

:: Chay dashboard
cd /d "D:\Contenfactory\dashboard"
python app.py

pause
