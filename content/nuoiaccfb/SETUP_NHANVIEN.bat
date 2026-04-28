@echo off
chcp 65001 >nul
title Facebook Automation Tool - Setup Nhan Vien

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║   Facebook Automation Tool - Setup Nhan Vien    ║
echo ║   Chay 1 lan duy nhat khi cai dat lan dau       ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: Kiem tra Python
echo [1/4] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [LOI] Python chua duoc cai dat!
    echo Vui long tai Python tai: https://python.org/downloads
    echo Nho tick vao "Add Python to PATH" khi cai!
    echo.
    pause
    exit /b 1
)
python --version
echo [OK] Python da san sang!
echo.

:: Cai thu vien Python
echo [2/4] Cai dat thu vien Python...
pip install -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai dat thu vien that bai!
    echo Thu chay CMD voi quyen Administrator
    pause
    exit /b 1
)
echo [OK] Thu vien da cai xong!
echo.

:: Cai Playwright Chromium
echo [3/4] Cai dat Playwright Chromium (co the mat 3-5 phut)...
playwright install chromium
if errorlevel 1 (
    echo [CANH BAO] Playwright install that bai, thu chay lai voi quyen Admin
) else (
    echo [OK] Playwright Chromium da cai xong!
)
echo.

:: Tao thu muc can thiet
echo [4/4] Tao cau truc thu muc...
if not exist "cookies" mkdir cookies
if not exist "screenshots" mkdir screenshots
echo [OK] Thu muc da tao xong!
echo.

echo ╔══════════════════════════════════════════════════╗
echo ║              CAI DAT HOAN TAT!                  ║
echo ╠══════════════════════════════════════════════════╣
echo ║  Buoc tiep theo:                                ║
echo ║  1. Mo IX Browser (nhan tu quan ly)             ║
echo ║  2. Chay START_TOOL.bat de khoi dong            ║
echo ║  3. Mo trinh duyet: http://localhost:5000        ║
echo ╚══════════════════════════════════════════════════╝
echo.
pause
