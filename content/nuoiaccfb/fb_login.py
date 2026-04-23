"""
fb_login.py
Facebook login automation via Playwright + IX Browser.
- Login with email/password
- Handle checkpoint, 2FA
- Save/restore cookies
- Check login status
"""

import asyncio
import json
import os
import random
import time
from pathlib import Path
from typing import Optional

COOKIES_DIR = Path(__file__).parent / "cookies"
COOKIES_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def cookies_path(fb_uid: str) -> Path:
    return COOKIES_DIR / f"{fb_uid}.json"


def save_cookies(fb_uid: str, cookies: list):
    with open(cookies_path(fb_uid), "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    print(f"[fb_login] Cookies saved for {fb_uid}")


def load_cookies(fb_uid: str) -> list:
    path = cookies_path(fb_uid)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def has_cookies(fb_uid: str) -> bool:
    return cookies_path(fb_uid).exists()


async def _human_type(page, selector: str, text: str, delay_min=50, delay_max=150):
    """Type text like a human with random delays"""
    await page.click(selector)
    await page.fill(selector, "")
    for char in text:
        await page.type(selector, char, delay=random.randint(delay_min, delay_max))


async def _random_delay(min_sec=1.0, max_sec=3.0):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


# ─────────────────────────────────────────────
# Login Status Check
# ─────────────────────────────────────────────

async def check_login_status(page) -> str:
    """
    Check if page is logged in.
    Returns: 'logged_in' | 'logged_out' | 'checkpoint' | 'disabled'
    """
    try:
        url = page.url
        if "checkpoint" in url or "checkpoint" in await page.content():
            return "checkpoint"
        if "disabled" in url:
            return "disabled"

        # Check for logged-in indicators
        # Facebook shows different elements when logged in
        logged_in = await page.query_selector('[data-pagelet="LeftRail"], [role="navigation"], [aria-label="Facebook"]')
        if logged_in:
            return "logged_in"

        # Check for login form
        login_form = await page.query_selector('#email, input[name="email"]')
        if login_form:
            return "logged_out"

        return "unknown"
    except Exception as e:
        print(f"[fb_login] Status check error: {e}")
        return "unknown"


# ─────────────────────────────────────────────
# Cookie-based Login
# ─────────────────────────────────────────────

async def login_with_cookies(context, fb_uid: str) -> bool:
    """
    Restore session from saved cookies.
    Returns True if login successful.
    """
    cookies = load_cookies(fb_uid)
    if not cookies:
        return False

    await context.add_cookies(cookies)
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
    await _random_delay(2, 4)

    status = await check_login_status(page)
    if status == "logged_in":
        print(f"[fb_login] Cookie login OK for {fb_uid}")
        return True
    else:
        print(f"[fb_login] Cookie login failed ({status}) for {fb_uid}")
        return False


# ─────────────────────────────────────────────
# Password Login
# ─────────────────────────────────────────────

async def login_with_password(page, email: str, password: str,
                               two_fa_secret: str = "") -> str:
    """
    Login to Facebook with email/password.
    Returns status: 'logged_in' | 'checkpoint' | 'wrong_password' | 'disabled' | 'error'
    """
    try:
        await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        await _random_delay(1.5, 3)

        # Check if already logged in
        status = await check_login_status(page)
        if status == "logged_in":
            return "logged_in"

        # Fill email
        email_input = await page.wait_for_selector('#email', timeout=10000)
        await email_input.click()
        await _random_delay(0.3, 0.8)
        await _human_type(page, '#email', email)
        await _random_delay(0.5, 1.5)

        # Fill password
        await _human_type(page, '#pass', password)
        await _random_delay(0.5, 1.0)

        # Click login button
        await page.click('[name="login"]')
        await _random_delay(3, 5)

        # Check result
        current_url = page.url

        if "checkpoint" in current_url:
            print(f"[fb_login] Checkpoint detected for {email}")
            return "checkpoint"

        if "two_step_verification" in current_url or "approvals" in current_url:
            if two_fa_secret:
                result = await handle_2fa(page, two_fa_secret)
                return result
            print(f"[fb_login] 2FA required for {email} but no secret provided")
            return "2fa_required"

        if "disabled" in current_url:
            print(f"[fb_login] Account disabled: {email}")
            return "disabled"

        # Check login success
        status = await check_login_status(page)
        if status == "logged_in":
            print(f"[fb_login] Login success: {email}")
            return "logged_in"
        else:
            # Check for wrong password message
            error_msg = await page.query_selector('[data-testid="royal_login_error"], .login_error_box')
            if error_msg:
                print(f"[fb_login] Wrong password for {email}")
                return "wrong_password"
            return status

    except Exception as e:
        print(f"[fb_login] Login error for {email}: {e}")
        return "error"


async def handle_2fa(page, secret: str) -> str:
    """Handle 2FA code entry"""
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        code = totp.now()
    except ImportError:
        print("[fb_login] Install pyotp: pip install pyotp")
        return "2fa_required"

    try:
        code_input = await page.wait_for_selector('input[name="approvals_code"], #approvals_code', timeout=10000)
        await code_input.click()
        await _human_type(page, 'input[name="approvals_code"]', code)
        await _random_delay(0.5, 1)
        await page.keyboard.press("Enter")
        await _random_delay(3, 5)

        status = await check_login_status(page)
        return status
    except Exception as e:
        print(f"[fb_login] 2FA error: {e}")
        return "error"


# ─────────────────────────────────────────────
# Main login flow
# ─────────────────────────────────────────────

async def login(profile_id, fb_uid: str, email: str = "", password: str = "",
                two_fa_secret: str = "") -> dict:
    """
    Full login flow:
    1. Try cookies first
    2. Fall back to email/password
    3. Save cookies on success
    Returns {"success": bool, "status": str, "profile_id": profile_id}
    """
    from ix_browser import connect_playwright, disconnect_playwright

    pw, browser, context, page = await connect_playwright(profile_id, url=None)
    if not page:
        return {"success": False, "status": "browser_error", "profile_id": profile_id}

    try:
        # Try cookie login first
        if has_cookies(fb_uid):
            ok = await login_with_cookies(context, fb_uid)
            if ok:
                # Refresh cookies
                new_cookies = await context.cookies()
                save_cookies(fb_uid, new_cookies)
                return {"success": True, "status": "logged_in", "profile_id": profile_id}

        # Fall back to password login
        if not email or not password:
            print(f"[fb_login] No credentials for {fb_uid}")
            return {"success": False, "status": "no_credentials", "profile_id": profile_id}

        status = await login_with_password(page, email, password, two_fa_secret)

        if status == "logged_in":
            cookies = await context.cookies()
            save_cookies(fb_uid, cookies)
            return {"success": True, "status": "logged_in", "profile_id": profile_id}
        else:
            return {"success": False, "status": status, "profile_id": profile_id}

    finally:
        # Don't close browser after login - keep for subsequent tasks
        pass


async def logout(context, fb_uid: str):
    """Logout and clear cookies"""
    try:
        page = context.pages[0]
        await page.goto("https://www.facebook.com/logout.php", timeout=15000)
        # Remove saved cookies
        path = cookies_path(fb_uid)
        if path.exists():
            path.unlink()
        print(f"[fb_login] Logged out: {fb_uid}")
    except Exception as e:
        print(f"[fb_login] Logout error: {e}")


# ─────────────────────────────────────────────
# Batch login
# ─────────────────────────────────────────────

async def batch_login(accounts: list) -> list:
    """
    Login multiple accounts sequentially.
    accounts: [{"profile_id": x, "fb_uid": y, "email": z, "password": w}, ...]
    Returns results list.
    """
    results = []
    for i, acc in enumerate(accounts):
        print(f"\n[fb_login] [{i+1}/{len(accounts)}] Logging in: {acc.get('fb_uid')}")
        result = await login(
            profile_id=acc["profile_id"],
            fb_uid=acc["fb_uid"],
            email=acc.get("email", ""),
            password=acc.get("password", ""),
            two_fa_secret=acc.get("two_fa_secret", "")
        )
        results.append(result)

        # Update account manager status
        try:
            from account_manager import set_status, update_account
            status_map = {
                "logged_in": "active",
                "checkpoint": "checkpoint",
                "disabled": "die",
                "wrong_password": "die",
            }
            new_status = status_map.get(result["status"], "warming")
            set_status(acc["fb_uid"], new_status)
            if result["success"]:
                update_account(acc["fb_uid"], last_action_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

        # Delay between logins
        await asyncio.sleep(random.uniform(3, 8))

    return results
