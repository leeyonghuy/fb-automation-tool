@echo off
chcp 65001 >nul
title Cài Đặt Tool FB Automation
color 0A

echo ============================================
echo   SETUP TOOL NUOI TAI KHOAN FACEBOOK
echo   Vui long doi den khi hoan tat...
echo ============================================
echo.

:: ─────────────────────────────────────────────
:: Bước 1: Kiểm tra và cài Git
:: ─────────────────────────────────────────────
echo [1/5] Kiem tra Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo     Git chua duoc cai. Dang tai va cai Git...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe' -OutFile '%TEMP%\git_installer.exe'"
    echo     Dang cai Git (co the mat 1-2 phut)...
    start /wait %TEMP%\git_installer.exe /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"
    :: Reload PATH
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
    echo     Git da cai xong!
) else (
    echo     Git da co san. OK!
)

:: ─────────────────────────────────────────────
:: Bước 2: Kiểm tra và cài Python
:: ─────────────────────────────────────────────
echo.
echo [2/5] Kiem tra Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo     Python chua duoc cai. Dang tai Python 3.11...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    echo     Dang cai Python (co the mat 2-3 phut)...
    start /wait %TEMP%\python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    :: Reload PATH
    set "PATH=%PATH%;C:\Python311;C:\Python311\Scripts"
    echo     Python da cai xong!
) else (
    echo     Python da co san. OK!
)

:: ─────────────────────────────────────────────
:: Bước 3: Clone hoặc Update code từ GitHub
:: ─────────────────────────────────────────────
echo.
echo [3/5] Lay code tu GitHub...

if exist "C:\fb-tool\.git" (
    echo     Thu muc da ton tai. Dang cap nhat code moi nhat...
    cd /d C:\fb-tool
    git pull origin main
    echo     Cap nhat hoan tat!
) else (
    echo     Dang tai code ve may (lan dau)...
    git clone https://github.com/leeyonghuy/fb-automation-tool.git C:\fb-tool
    if %errorlevel% neq 0 (
        echo.
        echo     LOI: Khong the tai code. Kiem tra ket noi Internet.
        pause
        exit /b 1
    )
    echo     Tai code hoan tat!
)

:: ─────────────────────────────────────────────
:: Bước 4: Cài Python libraries
:: ─────────────────────────────────────────────
echo.
echo [4/5] Cai cac thu vien Python...
cd /d C:\fb-tool\content\nuoiaccfb
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo     Dang thu lai voi pip3...
    pip3 install -r requirements.txt --quiet
)
echo     Thu vien da cai xong!

:: ─────────────────────────────────────────────
:: Bước 5: Cài Playwright Chromium
:: ─────────────────────────────────────────────
echo.
echo [5/5] Cai trinh duyet Chromium cho Playwright...
echo     (Co the mat 3-5 phut, vui long doi...)
python -m playwright install chromium
echo     Chromium da cai xong!

:: ─────────────────────────────────────────────
:: Tạo shortcut trên Desktop
:: ─────────────────────────────────────────────
echo.
echo Dang tao shortcut tren Desktop...

:: Tạo file chạy tool
echo @echo off > "C:\fb-tool\Chay_Tool.bat"
echo title FB Automation Tool >> "C:\fb-tool\Chay_Tool.bat"
echo cd /d C:\fb-tool\content\nuoiaccfb >> "C:\fb-tool\Chay_Tool.bat"
echo echo Dang khoi dong tool... >> "C:\fb-tool\Chay_Tool.bat"
echo echo Mo trinh duyet va vao: http://localhost:5000 >> "C:\fb-tool\Chay_Tool.bat"
echo python app.py >> "C:\fb-tool\Chay_Tool.bat"
echo pause >> "C:\fb-tool\Chay_Tool.bat"

:: Tạo file update tool
echo @echo off > "C:\fb-tool\Cap_Nhat_Tool.bat"
echo title Cap Nhat Tool >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo cd /d C:\fb-tool >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo echo Dang cap nhat code moi nhat tu GitHub... >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo git pull origin main >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo cd content\nuoiaccfb >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo pip install -r requirements.txt --quiet >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo echo Cap nhat hoan tat! >> "C:\fb-tool\Cap_Nhat_Tool.bat"
echo pause >> "C:\fb-tool\Cap_Nhat_Tool.bat"

:: Tạo shortcut trên Desktop
set DESKTOP=%USERPROFILE%\Desktop
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Chay Tool FB.lnk'); $s.TargetPath = 'C:\fb-tool\Chay_Tool.bat'; $s.IconLocation = 'C:\Windows\System32\shell32.dll,14'; $s.Save()"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Cap Nhat Tool.lnk'); $s.TargetPath = 'C:\fb-tool\Cap_Nhat_Tool.bat'; $s.IconLocation = 'C:\Windows\System32\shell32.dll,25'; $s.Save()"

echo.
echo ============================================
echo   CAI DAT HOAN TAT!
echo ============================================
echo.
echo  Tren Desktop da co 2 shortcut:
echo   - "Chay Tool FB"     : Mo tool moi ngay
echo   - "Cap Nhat Tool"    : Khi co phien ban moi
echo.
echo  Buoc tiep theo:
echo   1. Cai IX Browser tai: https://ixbrowser.com
echo   2. Dang nhap IX Browser bang tai khoan duoc cap
echo   3. Double-click "Chay Tool FB" tren Desktop
echo   4. Mo trinh duyet vao: http://localhost:5000
echo.
pause
