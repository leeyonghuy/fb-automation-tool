"""
ix_browser.py
Control IX Browser via Local API v2.
- Profile CRUD
- Open/close profiles
- Update proxy
- Connect Playwright via CDP
"""

import requests
import time
from typing import Optional

IX_API_BASE = "http://127.0.0.1:53200/api/v2"


def _post(path: str, payload: dict = None) -> dict:
    url = f"{IX_API_BASE}{path}"
    try:
        resp = requests.post(url, json=payload or {}, timeout=15)
        resp.raise_for_status()
        return resp.json() or {}
    except Exception as e:
        print(f"[ix_browser] POST {path} error: {e}")
        return {}


def _ok(result: dict) -> bool:
    return result.get("error", {}).get("code", -1) == 0


# ─────────────────────────────────────────────
# Profile Management
# ─────────────────────────────────────────────

def get_profiles(page: int = 1, page_size: int = 100) -> list:
    """Get all profiles"""
    data = _post("/profile-list", {"page": page, "page_size": page_size})
    inner = data.get("data") or {}
    profiles = inner.get("data") or inner.get("list", [])
    return profiles


def get_all_profiles() -> list:
    """Get all profiles across pages"""
    all_profiles = []
    page = 1
    while True:
        data = _post("/profile-list", {"page": page, "page_size": 100})
        inner = data.get("data") or {}
        total = inner.get("total", 0)
        profiles = inner.get("data") or inner.get("list", [])
        all_profiles.extend(profiles)
        if len(all_profiles) >= total:
            break
        page += 1
    print(f"[ix_browser] Total {len(all_profiles)} profiles")
    return all_profiles


def get_profile_by_id(profile_id) -> Optional[dict]:
    for p in get_all_profiles():
        if str(p.get("profile_id")) == str(profile_id):
            return p
    return None


def get_profile_by_name(name: str) -> Optional[dict]:
    for p in get_all_profiles():
        if p.get("name") == name:
            return p
    return None


def get_opened_profiles() -> list:
    """Get list of currently opened profiles"""
    data = _post("/profile-opened-list", {})
    if _ok(data):
        return data.get("data") or []
    return []


def create_profile(name: str, site_url: str = "https://www.facebook.com",
                   fingerprint_config: dict = None,
                   preference_config: dict = None,
                   proxy_config: dict = None,
                   group_id: int = None) -> Optional[dict]:
    """Create a new profile"""
    payload = {
        "name": name,
        "site_url": site_url,
    }
    if fingerprint_config:
        payload["fingerprint_config"] = fingerprint_config
    if preference_config:
        payload["preference_config"] = preference_config
    if proxy_config:
        payload["proxy_config"] = proxy_config
    if group_id:
        payload["group_id"] = group_id

    result = _post("/profile-create", payload)
    if _ok(result):
        data = result.get("data")
        profile_id = data if isinstance(data, int) else (data or {}).get("profile_id") or (data or {}).get("id")
        print(f"[ix_browser] Created profile [{name}] -> ID: {profile_id}")
        return {"name": name, "profile_id": profile_id}
    else:
        msg = result.get("error", {}).get("message", "unknown")
        print(f"[ix_browser] Failed to create [{name}]: {msg}")
        return None


def update_profile(profile_id, **kwargs) -> bool:
    """Update profile fields"""
    payload = {"profile_id": profile_id}
    payload.update(kwargs)
    result = _post("/profile-update", payload)
    return _ok(result)


def delete_profile(profile_id) -> bool:
    """Delete a profile"""
    result = _post("/profile-delete", {"profile_id": profile_id})
    ok = _ok(result)
    print(f"[ix_browser] Delete profile {profile_id}: {'OK' if ok else 'FAIL'}")
    return ok


def randomize_fingerprint(profile_id) -> bool:
    """Randomize fingerprint for a profile"""
    result = _post("/profile-random-fingerprint-configuration", {"profile_id": profile_id})
    ok = _ok(result)
    print(f"[ix_browser] Randomize fingerprint {profile_id}: {'OK' if ok else 'FAIL'}")
    return ok


# ─────────────────────────────────────────────
# Open / Close
# ─────────────────────────────────────────────

def open_profile(profile_id, load_extensions: bool = False) -> dict:
    """
    Open a profile browser.
    Returns {"success": bool, "ws": str, "http": str}
    """
    payload = {"profile_id": profile_id}
    if load_extensions:
        payload["load_extensions"] = True
    result = _post("/profile-open", payload)
    if _ok(result):
        data = result.get("data") or {}
        ws = data.get("ws", "")
        http = data.get("http", "")
        print(f"[ix_browser] Opened profile {profile_id} | WS: {ws[:60]}")
        return {"success": True, "ws": ws, "http": http}
    else:
        msg = result.get("error", {}).get("message", "unknown")
        print(f"[ix_browser] Failed to open {profile_id}: {msg}")
        return {"success": False, "ws": "", "http": ""}


def close_profile(profile_id) -> bool:
    """Close a profile browser"""
    result = _post("/profile-close", {"profile_id": profile_id})
    ok = _ok(result)
    print(f"[ix_browser] Close profile {profile_id}: {'OK' if ok else 'FAIL'}")
    return ok


def close_all_profiles() -> bool:
    """Close all opened profiles"""
    opened = get_opened_profiles()
    for p in opened:
        pid = p.get("profile_id") or p.get("id")
        if pid:
            close_profile(pid)
            time.sleep(0.5)
    return True


def open_profile_with_retry(profile_id, retries: int = 3, delay: int = 3) -> dict:
    """Open profile with retry on failure"""
    for attempt in range(retries):
        result = open_profile(profile_id)
        if result["success"]:
            return result
        print(f"[ix_browser] Retry {attempt+1}/{retries} for profile {profile_id}")
        time.sleep(delay)
    return {"success": False, "ws": "", "http": ""}


# ─────────────────────────────────────────────
# Proxy Management
# ─────────────────────────────────────────────

def update_proxy(profile_id, host: str, port, user: str = "",
                 password: str = "", proxy_type: str = "socks5") -> bool:
    """Update proxy for a profile"""
    proxy_config = {
        "proxy_type": proxy_type,
        "proxy_host": host,
        "proxy_port": int(port),
    }
    if user:
        proxy_config["proxy_user"] = user
    if password:
        proxy_config["proxy_password"] = password

    result = _post("/profile-update", {
        "profile_id": profile_id,
        "proxy_config": proxy_config
    })
    ok = _ok(result)
    if ok:
        print(f"[ix_browser] Proxy updated for {profile_id}: {host}:{port}")
    return ok


def set_proxy_direct(profile_id) -> bool:
    """Set profile to use direct connection (no proxy)"""
    result = _post("/profile-update", {
        "profile_id": profile_id,
        "proxy_config": {"proxy_type": "direct"}
    })
    return _ok(result)


# ─────────────────────────────────────────────
# Cookies
# ─────────────────────────────────────────────

def get_cookies(profile_id) -> list:
    """Get cookies for a profile"""
    result = _post("/profile-get-cookies", {"profile_id": profile_id})
    if _ok(result):
        return result.get("data") or []
    return []


def update_cookies(profile_id, cookies: list) -> bool:
    """Update cookies for a profile"""
    result = _post("/profile-update-cookies", {
        "profile_id": profile_id,
        "cookies": cookies
    })
    return _ok(result)


def clear_cookies(profile_id) -> bool:
    """Clear cookies for a profile"""
    result = _post("/profile-clear-cache-and-cookies", {"profile_id": profile_id})
    return _ok(result)


# ─────────────────────────────────────────────
# Playwright Integration
# ─────────────────────────────────────────────

async def connect_playwright(profile_id, url: str = None):
    """
    Open profile and connect Playwright via CDP.
    Returns (playwright_instance, browser, context, page)
    Call disconnect_playwright() when done.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[ix_browser] Install playwright: pip install playwright && playwright install chromium")
        return None, None, None, None

    result = open_profile_with_retry(profile_id)
    if not result["success"]:
        return None, None, None, None

    ws_endpoint = result["ws"]
    pw = await async_playwright().__aenter__()
    browser = await pw.chromium.connect_over_cdp(ws_endpoint)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()

    if url:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    return pw, browser, context, page


async def disconnect_playwright(pw, browser, profile_id=None):
    """Close playwright connection and optionally close the profile"""
    try:
        if browser:
            await browser.close()
    except Exception:
        pass
    try:
        if pw:
            await pw.__aexit__(None, None, None)
    except Exception:
        pass
    if profile_id:
        close_profile(profile_id)


# ─────────────────────────────────────────────
# Groups
# ─────────────────────────────────────────────

def get_groups() -> list:
    """Get all profile groups"""
    result = _post("/group-list", {})
    if _ok(result):
        return result.get("data") or []
    return []


def create_group(name: str) -> Optional[int]:
    """Create a profile group, return group_id"""
    result = _post("/group-create", {"group_name": name})
    if _ok(result):
        data = result.get("data") or {}
        gid = data.get("group_id") or data.get("id") if isinstance(data, dict) else data
        print(f"[ix_browser] Created group [{name}] ID: {gid}")
        return gid
    return None


# ─────────────────────────────────────────────
# Quick test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== IX Browser API Test ===")
    profiles = get_profiles()
    print(f"Total profiles: {len(profiles)}")
    for p in profiles[:5]:
        pid = p.get("profile_id")
        name = p.get("name", "N/A")
        status = "open" if p.get("last_open_time", 0) > 0 else "closed"
        print(f"  [{pid}] {name} | {status}")
