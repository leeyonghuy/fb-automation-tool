#!/usr/bin/env python3
"""
xiaohongshu.py — Tải video / image post Xiaohongshu (小红书) KHÔNG cần đăng nhập.

Strategy 2-tier fallback (tier 0 = yt-dlp đã handle ở `video_downloader.py`):
  Tier 1: HTTP request với mobile UA + parse `window.__INITIAL_STATE__`
          → đủ cho note public, không cần JS.
  Tier 2: Playwright headless mở web (no login) → cookie `webId`/`a1` sinh
          từ JS → reuse cho request → parse JSON.

Hỗ trợ URL formats:
  - https://www.xiaohongshu.com/explore/<note_id>
  - https://www.xiaohongshu.com/discovery/item/<note_id>
  - https://xhslink.com/x/<short_id>  (mobile share, sẽ resolve redirect)

Public API:
    download_xhs(url, output_path) -> dict
        Returns: {success, file_path, error, video_id, title, platform, type}
                  type ∈ {"video", "image", "unknown"}

Cài thêm: requests (đã có), playwright (optional, chỉ dùng tier 2)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Cho phép import config.py ở project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import COOKIES_DIR  # noqa: E402

logger = logging.getLogger(__name__)

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False
    logger.warning("xhs: thiếu `requests` — Tier 1 không khả dụng")

# Mobile UA giúp XHS trả page đầy đủ data SSR (desktop UA hay bị redirect login)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 "
    "Mobile/15E148 Safari/604.1"
)
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_COOKIE_FILE = os.path.join(COOKIES_DIR, "xhs_cookies.json")
_REQUEST_TIMEOUT = 20


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_SHORT_HOSTS = {"xhslink.com"}
_NOTE_HOSTS = {"xiaohongshu.com", "www.xiaohongshu.com"}
_NOTE_ID_RE = re.compile(r"/(?:explore|discovery/item)/([a-zA-Z0-9]+)")


def resolve_url(url: str) -> str:
    """Resolve xhslink.com short URL → full xiaohongshu.com URL."""
    if not _HAS_REQUESTS:
        return url
    host = urlparse(url).netloc.lower()
    if host not in _SHORT_HOSTS:
        return url
    try:
        r = requests.head(
            url, allow_redirects=True, timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": _MOBILE_UA},
        )
        return r.url
    except requests.RequestException as e:
        logger.warning(f"xhs: resolve_url fail: {e}")
        return url


def extract_note_id(url: str) -> str:
    m = _NOTE_ID_RE.search(url)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Cookie persistence
# ---------------------------------------------------------------------------

def _load_cookies() -> dict:
    if not os.path.exists(_COOKIE_FILE):
        return {}
    try:
        with open(_COOKIE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cookies(cookies: dict) -> None:
    os.makedirs(os.path.dirname(_COOKIE_FILE), exist_ok=True)
    try:
        with open(_COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"xhs: _save_cookies fail: {e}")


# ---------------------------------------------------------------------------
# Parse logic — extract download URLs from `__INITIAL_STATE__`
# ---------------------------------------------------------------------------

_INITIAL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*({.*?})</script>",
    re.DOTALL,
)


def _parse_initial_state(html: str) -> Optional[dict]:
    m = _INITIAL_STATE_RE.search(html)
    if not m:
        return None
    raw = m.group(1)
    # XHS đôi khi inject `undefined` thay null → JSON parse fail
    raw = raw.replace("undefined", "null")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"xhs: parse __INITIAL_STATE__ fail: {e}")
        return None


def _extract_media(state: dict, note_id: str) -> dict:
    """
    Trả về dict {type, video_url, image_urls, title, desc} từ __INITIAL_STATE__.
    Cấu trúc state khá nested và thay đổi theo version XHS — code này tolerate
    khá nhiều shape khác nhau bằng cách lookup an toàn.
    """
    out = {"type": "unknown", "video_url": "", "image_urls": [],
           "title": "", "desc": ""}

    # Tìm note object theo nhiều path khả dĩ
    note = None
    candidates = [
        ("note", "noteDetailMap", note_id, "note"),
        ("note", "noteDetail", "data"),
        ("noteDetail", "data"),
    ]
    for path in candidates:
        cur = state
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, dict):
            note = cur
            break

    if not note:
        # Fallback: scan toàn bộ state tìm key "type" + "video"/"imageList"
        def _walk(obj):
            if isinstance(obj, dict):
                if obj.get("type") in ("normal", "video") and (
                    "video" in obj or "imageList" in obj or "images" in obj
                ):
                    return obj
                for v in obj.values():
                    r = _walk(v)
                    if r:
                        return r
            elif isinstance(obj, list):
                for it in obj:
                    r = _walk(it)
                    if r:
                        return r
            return None
        note = _walk(state)

    if not note:
        return out

    out["title"] = note.get("title", "") or note.get("desc", "")[:80]
    out["desc"] = note.get("desc", "")

    # Video
    video = note.get("video") or {}
    if video:
        out["type"] = "video"
        # Path phổ biến: video.media.stream.h264[0].master_url
        media = video.get("media") or {}
        stream = media.get("stream") or {}
        for codec in ("h264", "h265", "av1"):
            tracks = stream.get(codec) or []
            if tracks and isinstance(tracks, list):
                url = tracks[0].get("master_url") or tracks[0].get("backup_urls", [""])[0]
                if url:
                    out["video_url"] = url
                    break
        # Fallback path khác
        if not out["video_url"]:
            out["video_url"] = (
                video.get("url")
                or (video.get("urlInfoList") or [{}])[0].get("url", "")
            )

    # Image (note loại "normal")
    if not out["video_url"]:
        images = note.get("imageList") or note.get("images") or []
        urls = []
        for img in images:
            if isinstance(img, dict):
                u = img.get("urlDefault") or img.get("url") or img.get("urlPre")
                if u:
                    urls.append(u)
        if urls:
            out["type"] = "image"
            out["image_urls"] = urls

    return out


# ---------------------------------------------------------------------------
# Tier 1: pure HTTP
# ---------------------------------------------------------------------------

def _tier1_http(url: str, note_id: str) -> dict:
    if not _HAS_REQUESTS:
        return {"success": False, "error": "requests not installed"}

    headers = {
        "User-Agent": _MOBILE_UA,
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    cookies = _load_cookies()
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=_REQUEST_TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:
        return {"success": False, "error": f"http error: {e}"}

    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}

    # Save cookies (XHS sets webId, a1, gid trên first visit)
    new_cookies = {**cookies, **{c.name: c.value for c in r.cookies}}
    if new_cookies != cookies:
        _save_cookies(new_cookies)

    state = _parse_initial_state(r.text)
    if not state:
        return {"success": False, "error": "no __INITIAL_STATE__ (có thể bị anti-bot)"}

    media = _extract_media(state, note_id)
    if media["type"] == "unknown" or (
        not media["video_url"] and not media["image_urls"]
    ):
        return {"success": False, "error": "không trích được media URL"}

    return {"success": True, "media": media}


# ---------------------------------------------------------------------------
# Tier 2: Playwright headless (cookie refresh)
# ---------------------------------------------------------------------------

def _tier2_playwright(url: str, note_id: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return {"success": False, "error": "playwright not installed"}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=_DESKTOP_UA,
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded",
                           timeout=_REQUEST_TIMEOUT * 1000)
                # Đợi __INITIAL_STATE__ inject
                page.wait_for_function(
                    "() => window.__INITIAL_STATE__ !== undefined",
                    timeout=10_000,
                )
                state = page.evaluate("() => window.__INITIAL_STATE__")
                # Save cookies cho lần sau
                cookies = {c["name"]: c["value"] for c in context.cookies()}
                _save_cookies(cookies)
            finally:
                browser.close()

        if not state:
            return {"success": False, "error": "playwright: state empty"}
        media = _extract_media(state, note_id)
        if media["type"] == "unknown" or (
            not media["video_url"] and not media["image_urls"]
        ):
            return {"success": False, "error": "playwright: không trích được media URL"}
        return {"success": True, "media": media}

    except Exception as e:
        return {"success": False, "error": f"playwright error: {e}"}


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_to(url: str, dest_path: str) -> bool:
    if not _HAS_REQUESTS:
        return False
    try:
        with requests.get(url, headers={"User-Agent": _MOBILE_UA,
                                          "Referer": "https://www.xiaohongshu.com/"},
                           stream=True, timeout=60) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024
    except Exception as e:
        logger.error(f"xhs: download {url} fail: {e}")
        try:
            os.remove(dest_path)
        except OSError:
            pass
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_xhs(url: str, output_dir: str, video_id: str = "") -> dict:
    """
    Tải XHS note về `output_dir`.
    Trả dict cùng schema với `video_downloader.download_video`:
        {success, file_path, error, video_id, title, platform, type}

    Với note ảnh: file_path là path tới ảnh đầu tiên, kèm field `image_paths`.
    """
    result = {
        "success": False, "file_path": None, "error": "",
        "video_id": video_id, "title": "", "platform": "xiaohongshu",
        "type": "unknown",
    }

    full_url = resolve_url(url)
    note_id = extract_note_id(full_url) or video_id
    if not note_id:
        result["error"] = "Không trích được note_id từ URL"
        return result
    result["video_id"] = note_id

    # Tier 1
    logger.info(f"[xhs] Tier 1 (HTTP) cho note {note_id}")
    r = _tier1_http(full_url, note_id)
    if not r["success"]:
        logger.warning(f"[xhs] Tier 1 fail: {r['error']} → thử Tier 2")
        # Tier 2
        r = _tier2_playwright(full_url, note_id)
        if not r["success"]:
            result["error"] = f"Cả 2 tier fail. Last: {r['error']}"
            return result

    media = r["media"]
    result["title"] = media["title"]
    result["type"] = media["type"]

    os.makedirs(output_dir, exist_ok=True)

    if media["type"] == "video":
        dest = os.path.join(output_dir, f"{note_id}.mp4")
        ok = _download_to(media["video_url"], dest)
        if ok:
            result["success"] = True
            result["file_path"] = dest
        else:
            result["error"] = "Tải video file fail"
        return result

    if media["type"] == "image":
        paths = []
        for i, img_url in enumerate(media["image_urls"]):
            ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
            dest = os.path.join(output_dir, f"{note_id}_{i:02d}{ext}")
            if _download_to(img_url, dest):
                paths.append(dest)
        if paths:
            result["success"] = True
            result["file_path"] = paths[0]
            result["image_paths"] = paths
        else:
            result["error"] = "Tải ảnh fail toàn bộ"
        return result

    result["error"] = f"Loại note không hỗ trợ: {media['type']}"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Xiaohongshu downloader (no login)")
    parser.add_argument("url", help="URL note hoặc link xhslink.com/...")
    parser.add_argument("--out", default="./xhs_out", help="Output directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    res = download_xhs(args.url, args.out)
    print(json.dumps(res, ensure_ascii=False, indent=2))
