@echo off
:: Chay voi quyen Admin de export Chrome cookies
:: Double-click file nay de chay

echo ============================================
echo   Export Chrome Cookies cho Douyin/TikTok
echo ============================================
echo.

:: Kiem tra quyen Admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Can quyen Administrator!
    echo [!] Dang tu dong nang cap quyen...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo [+] Da co quyen Administrator
echo.

:: Dong Chrome truoc khi copy cookies
echo [*] Dang dong Chrome de lay cookies...
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

:: Copy cookies file
set COOKIES_SRC=%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies
set COOKIES_DST=C:\Users\Admin\AppData\Local\Temp\chrome_cookies_tmp.db
set COOKIES_OUT=D:\Contenfactory\crawler\cookies\tiktok_cookies.txt

if not exist "%COOKIES_SRC%" (
    echo [-] Khong tim thay Chrome cookies tai: %COOKIES_SRC%
    pause
    exit /b 1
)

echo [*] Dang copy cookies database...
copy /Y "%COOKIES_SRC%" "%COOKIES_DST%" >nul 2>&1

if not exist "%COOKIES_DST%" (
    echo [-] Copy that bai!
    pause
    exit /b 1
)

echo [+] Copy thanh cong!
echo.

:: Chay Python script de extract cookies
echo [*] Dang extract cookies...
python -c "
import sqlite3, os, sys

cookies_db = r'C:\Users\Admin\AppData\Local\Temp\chrome_cookies_tmp.db'
output = r'D:\Contenfactory\crawler\cookies\tiktok_cookies.txt'
domains = ['.douyin.com', '.tiktok.com', 'douyin.com', 'tiktok.com']

try:
    conn = sqlite3.connect(cookies_db)
    cursor = conn.cursor()
    placeholders = ','.join(['?' for _ in domains])
    cursor.execute(f'SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly FROM cookies WHERE host_key IN ({placeholders}) ORDER BY host_key, name', domains)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print('[-] Khong tim thay cookies Douyin/TikTok!')
        print('    -> Hay dang nhap vao douyin.com tren Chrome truoc')
        sys.exit(1)
    
    print(f'[+] Tim thay {len(rows)} cookies')
    
    with open(output, 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n')
        f.write('# Generated automatically\n\n')
        for host, name, value, path, expires, secure, httponly in rows:
            if expires > 0:
                unix_ts = (expires - 11644473600000000) // 1000000
            else:
                unix_ts = 0
            secure_str = 'TRUE' if secure else 'FALSE'
            include_sub = 'TRUE' if host.startswith('.') else 'FALSE'
            f.write(f'{host}\t{include_sub}\t{path}\t{secure_str}\t{unix_ts}\t{name}\t{value}\n')
    
    print(f'[+] Da luu cookies vao: {output}')
    print('[OK] Cookies san sang!')
    
except Exception as e:
    print(f'[-] Loi: {e}')
    sys.exit(1)
"

:: Xoa file tam
del "%COOKIES_DST%" >nul 2>&1

echo.
echo ============================================
echo   XONG! Cookies da duoc export.
echo   File: D:\Contenfactory\crawler\cookies\tiktok_cookies.txt
echo ============================================
echo.
echo [*] Mo lai Chrome...
start chrome

pause
