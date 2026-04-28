"""
debug_utils.py
Tiện ích debug cho Facebook automation.
- Screenshot on error
- Auto-cleanup screenshots cũ
"""

import asyncio
import os
import time
from pathlib import Path

SCREENSHOT_DIR = Path(__file__).parent / "debug_screenshots"
MAX_SCREENSHOTS = 50


def _ensure_dir():
    SCREENSHOT_DIR.mkdir(exist_ok=True)


def _cleanup_old_screenshots():
    """Giữ tối đa MAX_SCREENSHOTS file, xóa cũ nhất."""
    try:
        files = sorted(SCREENSHOT_DIR.glob("*.png"), key=lambda f: f.stat().st_mtime)
        while len(files) >= MAX_SCREENSHOTS:
            files[0].unlink(missing_ok=True)
            files = files[1:]
    except Exception:
        pass


async def screenshot_on_error(page, context_name: str = "error") -> str:
    """
    Chụp screenshot khi gặp lỗi.
    Trả về đường dẫn file screenshot hoặc "" nếu thất bại.
    """
    _ensure_dir()
    _cleanup_old_screenshots()

    ts = time.strftime("%Y%m%d_%H%M%S")
    # Sanitize context_name
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in context_name)[:50]
    filename = SCREENSHOT_DIR / f"{ts}_{safe_name}.png"

    try:
        await page.screenshot(path=str(filename), full_page=False)
        print(f"[debug_utils] Screenshot saved: {filename.name}")
        return str(filename)
    except Exception as e:
        print(f"[debug_utils] Screenshot failed: {e}")
        return ""


def screenshot_sync(page, context_name: str = "error") -> str:
    """
    Wrapper đồng bộ — dùng khi không có event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Không thể chạy nested, bỏ qua
            return ""
        return loop.run_until_complete(screenshot_on_error(page, context_name))
    except Exception:
        return ""
