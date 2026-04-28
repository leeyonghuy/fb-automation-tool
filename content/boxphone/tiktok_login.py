"""
tiktok_login.py
Auto login TikTok trên thiết bị Android qua uiautomator2.
Package TikTok: com.zhiliaoapp.musically (Global) / com.ss.android.ugc.trill
"""

import time
import random
from device_controller import (
    connect, tap, tap_element, input_text, press_back,
    open_app, element_exists, wait_for_element, screenshot,
    unlock_screen, random_delay
)

# TikTok package names
TIKTOK_PACKAGE = "com.zhiliaoapp.musically"
TIKTOK_PACKAGE_ALT = "com.ss.android.ugc.trill"


def get_tiktok_package(serial: str) -> str:
    """Tự động detect package TikTok đang cài"""
    from adb_manager import run_adb
    stdout, _, _ = run_adb(["shell", "pm", "list", "packages"], serial)
    if TIKTOK_PACKAGE in stdout:
        return TIKTOK_PACKAGE
    if TIKTOK_PACKAGE_ALT in stdout:
        return TIKTOK_PACKAGE_ALT
    return TIKTOK_PACKAGE  # Default


def is_logged_in(serial: str) -> bool:
    """Kiểm tra TikTok đã đăng nhập chưa"""
    pkg = get_tiktok_package(serial)
    open_app(serial, pkg)
    time.sleep(4)

    # Nếu thấy nút "Profile" hoặc "Me" → đã đăng nhập
    if element_exists(serial, text="Profile") or element_exists(serial, text="Me"):
        return True
    # Nếu thấy "Log in" → chưa đăng nhập
    if element_exists(serial, text="Log in") or element_exists(serial, text="Sign up"):
        return False
    return False


def login_with_email(serial: str, email: str, password: str) -> dict:
    """
    Đăng nhập TikTok bằng email/password.
    Trả về {"success": bool, "error": str}
    """
    result = {"success": False, "error": ""}

    try:
        pkg = get_tiktok_package(serial)

        # Mở TikTok
        unlock_screen(serial)
        open_app(serial, pkg)
        time.sleep(4)

        # Kiểm tra đã login chưa
        if is_logged_in(serial):
            result["success"] = True
            result["error"] = "Already logged in"
            return result

        # Tìm nút "Log in"
        if not tap_element(serial, text="Log in", timeout=10):
            # Thử tìm "Use phone / email / username"
            if not tap_element(serial, text="Use phone / email / username", timeout=5):
                result["error"] = "Cannot find Log in button"
                return result

        time.sleep(2)

        # Chọn "Log in with email or username"
        if element_exists(serial, text="Log in with email or username"):
            tap_element(serial, text="Log in with email or username")
        elif element_exists(serial, text="Email or username"):
            tap_element(serial, text="Email or username")
        else:
            # Thử tap vào ô email trực tiếp
            tap_element(serial, resource_id="com.zhiliaoapp.musically:id/et_email")

        time.sleep(1.5)

        # Nhập email
        d = connect(serial)
        if d:
            # Tìm ô input email
            email_field = d(className="android.widget.EditText")
            if email_field.exists(timeout=5):
                email_field.click()
                time.sleep(0.5)
                d.send_keys(email)
                time.sleep(1)

        # Nhấn Next
        if not tap_element(serial, text="Next", timeout=5):
            tap_element(serial, text="Continue", timeout=5)
        time.sleep(2)

        # Nhập password
        d = connect(serial)
        if d:
            pwd_field = d(className="android.widget.EditText", focused=True)
            if not pwd_field.exists(timeout=3):
                pwd_field = d(className="android.widget.EditText")
            if pwd_field.exists(timeout=5):
                pwd_field.click()
                time.sleep(0.5)
                d.send_keys(password)
                time.sleep(1)

        # Nhấn Log in
        if not tap_element(serial, text="Log in", timeout=5):
            tap_element(serial, text="Sign in", timeout=5)

        time.sleep(5)

        # Kiểm tra kết quả
        if element_exists(serial, text="Profile") or element_exists(serial, text="Me"):
            result["success"] = True
        elif element_exists(serial, text="Wrong password"):
            result["error"] = "Wrong password"
        elif element_exists(serial, text="Verify"):
            result["error"] = "Captcha/Verify required - manual action needed"
        elif element_exists(serial, text="Too many attempts"):
            result["error"] = "Too many login attempts"
        else:
            # Chụp màn hình để debug
            screenshot(serial, f"login_debug_{serial.replace(':', '_')}.png")
            result["error"] = "Unknown login result - screenshot saved"

    except Exception as e:
        result["error"] = str(e)

    return result


def login_with_phone(serial: str, phone: str, password: str) -> dict:
    """Đăng nhập TikTok bằng số điện thoại"""
    result = {"success": False, "error": ""}

    try:
        pkg = get_tiktok_package(serial)
        unlock_screen(serial)
        open_app(serial, pkg)
        time.sleep(4)

        if is_logged_in(serial):
            result["success"] = True
            result["error"] = "Already logged in"
            return result

        tap_element(serial, text="Log in", timeout=10)
        time.sleep(2)

        # Chọn phone
        if element_exists(serial, text="Use phone / email / username"):
            tap_element(serial, text="Use phone / email / username")
        time.sleep(1.5)

        # Nhập số điện thoại
        d = connect(serial)
        if d:
            phone_field = d(className="android.widget.EditText")
            if phone_field.exists(timeout=5):
                phone_field.click()
                time.sleep(0.5)
                d.send_keys(phone)
                time.sleep(1)

        tap_element(serial, text="Send code", timeout=5)
        time.sleep(3)

        result["error"] = "OTP required - manual action needed"

    except Exception as e:
        result["error"] = str(e)

    return result


def logout(serial: str) -> bool:
    """Đăng xuất TikTok"""
    try:
        pkg = get_tiktok_package(serial)
        open_app(serial, pkg)
        time.sleep(3)

        # Vào Profile
        tap_element(serial, text="Profile", timeout=10)
        time.sleep(2)

        # Vào Settings (icon 3 gạch hoặc gear)
        d = connect(serial)
        if d:
            # Tìm nút settings
            settings_btn = d(description="Settings")
            if not settings_btn.exists(timeout=3):
                settings_btn = d(resourceId="com.zhiliaoapp.musically:id/iv_setting")
            if settings_btn.exists(timeout=3):
                settings_btn.click()
                time.sleep(2)

        # Scroll xuống tìm Log out
        for _ in range(5):
            if element_exists(serial, text="Log out"):
                tap_element(serial, text="Log out")
                time.sleep(2)
                tap_element(serial, text="Log out")  # Confirm
                return True
            from device_controller import swipe_up
            swipe_up(serial)
            time.sleep(1)

        return False
    except Exception:
        return False


async def batch_login(accounts: list) -> list:
    """
    Đăng nhập hàng loạt.
    accounts: [{"serial": "...", "email": "...", "password": "..."}]
    """
    import asyncio
    results = []

    for acc in accounts:
        serial = acc.get("serial")
        email = acc.get("email", "")
        password = acc.get("password", "")

        if not serial or not email or not password:
            results.append({"serial": serial, "success": False, "error": "Missing credentials"})
            continue

        print(f"[{serial}] Logging in: {email}")
        r = login_with_email(serial, email, password)
        r["serial"] = serial
        r["email"] = email
        results.append(r)
        print(f"[{serial}] {'✓' if r['success'] else '✗'} {r.get('error', 'OK')}")

        await asyncio.sleep(random.uniform(5, 15))

    return results
