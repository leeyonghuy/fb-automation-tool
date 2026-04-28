@echo off
title Setup Auto-Start ContenFactory
echo.
echo  ============================================
echo   Cai dat tu dong khoi dong khi bat may
echo  ============================================
echo.

:: Tao VBS script chay an (khong hien cua so CMD)
set VBS_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ContenFactory_Dashboard.vbs
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_PATH%"
echo WshShell.Run "D:\Contenfactory\START_DASHBOARD_SILENT.bat", 0, False >> "%VBS_PATH%"

:: Tao silent bat (khong hien cua so)
echo @echo off > "D:\Contenfactory\START_DASHBOARD_SILENT.bat"
echo cd /d "D:\Contenfactory\dashboard" >> "D:\Contenfactory\START_DASHBOARD_SILENT.bat"
echo python app.py >> "D:\Contenfactory\START_DASHBOARD_SILENT.bat"

echo [OK] Da them vao Startup folder
echo [OK] Dashboard se tu dong chay khi bat may
echo.
echo  File startup: %VBS_PATH%
echo.
echo  De tat auto-start: Xoa file VBS o tren
echo  De kiem tra: Restart may va mo http://localhost:5555
echo.
pause
