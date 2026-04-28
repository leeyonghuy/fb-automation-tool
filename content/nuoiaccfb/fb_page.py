"""
fb_page.py
Tạo và quản lý Facebook Fanpage tự động qua Playwright + IX Browser
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

PAGES_FILE = Path(__file__).parent / "pages.json"

# Cho phép import common/* từ project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from common.json_store import load_json, save_json, locked_update  # type: ignore
except ImportError:
    from contextlib import contextmanager

    def load_json(path, default=None):  # type: ignore[no-redef]
        if not Path(path).exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_json(path, data):  # type: ignore[no-redef]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @contextmanager
    def locked_update(path, default=None):  # type: ignore[no-redef]
        data = load_json(path, default)
        yield data
        save_json(path, data)

PAGE_CATEGORIES = {
    "public_figure": "Nhân vật công cộng",
    "entertainment": "Giải trí",
    "news_media": "Tin tức & Truyền thông",
    "education": "Giáo dục",
    "sports": "Thể thao",
    "music": "Âm nhạc",
    "food": "Ẩm thực & Nhà hàng",
    "travel": "Du lịch",
    "health": "Sức khỏe & Làm đẹp",
    "technology": "Công nghệ",
    "business": "Doanh nghiệp",
    "community": "Cộng đồng",
}


# ─────────────────────────────────────────────
# Pages DB
# ─────────────────────────────────────────────

def _load_pages() -> list:
    return load_json(PAGES_FILE, default=[]) or []


def _save_pages(pages: list):
    save_json(PAGES_FILE, pages)


def get_all_pages() -> list:
    return _load_pages()


def get_page(page_id: str) -> dict | None:
    for p in _load_pages():
        if p.get("page_id") == page_id or p.get("page_name") == page_id:
            return p
    return None


def add_page_record(owner_uid: str, page_name: str, page_url: str = "",
                    page_id: str = "", category: str = "public_figure",
                    description: str = "", editors: list = None) -> dict:
    record = {
        "page_id": page_id or f"tmp_{int(time.time())}",
        "page_name": page_name,
        "page_url": page_url,
        "owner_uid": owner_uid,
        "category": category,
        "description": description,
        "editors": editors or [],
        "status": "active",
        "like_count": 0,
        "follower_count": 0,
        "post_count": 0,
        "reel_count": 0,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_posted_at": "",
        "notes": "",
    }
    with locked_update(PAGES_FILE, default=[]) as pages:
        pages.append(record)
    return record


def update_page(page_id: str, **kwargs) -> bool:
    found = False
    with locked_update(PAGES_FILE, default=[]) as pages:
        for p in pages:
            if p.get("page_id") == page_id:
                p.update(kwargs)
                found = True
                break
    return found


def delete_page_record(page_id: str) -> bool:
    deleted = False
    with locked_update(PAGES_FILE, default=[]) as pages:
        before = len(pages)
        pages[:] = [p for p in pages if p.get("page_id") != page_id]
        deleted = len(pages) < before
    return deleted


# ─────────────────────────────────────────────
# Playwright Actions
# ─────────────────────────────────────────────

async def create_fanpage(page, owner_uid: str, page_name: str,
                          category: str = "public_figure",
                          description: str = "",
                          avatar_path: str = "",
                          cover_path: str = "") -> dict:
    """
    Tạo Fanpage mới trên Facebook.
    page: Playwright page object đã login sẵn
    """
    result = {"success": False, "page_name": page_name, "error": ""}
    try:
        print(f"[fb_page] Tạo page: {page_name}")

        # Mở trang tạo page
        await page.goto("https://www.facebook.com/pages/create", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Chọn loại page - "Public Figure" hoặc "Entertainment"
        # Facebook có thể thay đổi UI, thử click vào loại phù hợp
        cat_map = {
            "public_figure": "Nhân vật công cộng",
            "entertainment": "Giải trí",
            "community": "Cộng đồng",
        }
        cat_label = cat_map.get(category, "Nhân vật công cộng")

        # Tìm nút theo text hoặc aria-label
        try:
            cat_btn = page.locator(f'text="{cat_label}"').first
            if await cat_btn.is_visible(timeout=5000):
                await cat_btn.click()
                await asyncio.sleep(1)
        except Exception:
            # Thử click "Public Figure" trực tiếp
            try:
                await page.click('[data-testid="page-creation-category-public-figure"]', timeout=3000)
            except Exception:
                pass

        # Nhập tên page
        name_input = page.locator('input[placeholder*="name"], input[aria-label*="Page name"], input[name="name"]').first
        if await name_input.is_visible(timeout=5000):
            await name_input.click()
            await name_input.fill(page_name)
            await asyncio.sleep(1)
        else:
            result["error"] = "Không tìm thấy ô nhập tên page"
            return result

        # Tìm và điền danh mục (category)
        try:
            cat_input = page.locator('input[placeholder*="categor"], input[aria-label*="ategory"]').first
            if await cat_input.is_visible(timeout=3000):
                await cat_input.fill(cat_label)
                await asyncio.sleep(1)
                # Chọn gợi ý đầu tiên
                suggestion = page.locator('[role="option"]').first
                if await suggestion.is_visible(timeout=3000):
                    await suggestion.click()
                    await asyncio.sleep(1)
        except Exception:
            pass

        # Nhập mô tả (nếu có)
        if description:
            try:
                desc_input = page.locator('textarea[placeholder*="descript"], textarea[aria-label*="escription"]').first
                if await desc_input.is_visible(timeout=3000):
                    await desc_input.fill(description)
                    await asyncio.sleep(1)
            except Exception:
                pass

        # Bấm nút tạo page
        create_btn = page.locator('button:has-text("Create Page"), button:has-text("Tạo trang"), [data-testid*="create"]').first
        if await create_btn.is_visible(timeout=5000):
            await create_btn.click()
            await asyncio.sleep(5)
        else:
            # Thử nhấn Next/Tiếp theo
            next_btn = page.locator('button:has-text("Next"), button:has-text("Tiếp theo")').first
            if await next_btn.is_visible(timeout=3000):
                await next_btn.click()
                await asyncio.sleep(3)

        # Lấy URL page mới tạo
        current_url = page.url
        page_url = ""
        new_page_id = f"tmp_{int(time.time())}"

        if "facebook.com" in current_url and "/pages/" in current_url.lower():
            page_url = current_url
            # Trích xuất page_id từ URL nếu có
            parts = current_url.rstrip("/").split("/")
            if parts:
                new_page_id = parts[-1]

        # Upload ảnh đại diện
        if avatar_path and os.path.exists(avatar_path):
            await _upload_page_avatar(page, avatar_path)

        # Upload ảnh bìa
        if cover_path and os.path.exists(cover_path):
            await _upload_page_cover(page, cover_path)

        # Lưu vào DB
        record = add_page_record(
            owner_uid=owner_uid,
            page_name=page_name,
            page_url=page_url,
            page_id=new_page_id,
            category=category,
            description=description,
        )

        result["success"] = True
        result["page_url"] = page_url
        result["page_id"] = new_page_id
        result["record"] = record
        print(f"[fb_page] ✓ Tạo page thành công: {page_name} → {page_url}")

    except Exception as e:
        result["error"] = str(e)
        print(f"[fb_page] ✗ Lỗi tạo page {page_name}: {e}")

    return result


async def _upload_page_avatar(page, image_path: str):
    """Upload ảnh đại diện cho page"""
    try:
        avatar_btn = page.locator('[aria-label*="profile picture"], button:has-text("Add profile")').first
        if await avatar_btn.is_visible(timeout=5000):
            await avatar_btn.click()
            await asyncio.sleep(2)
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(image_path)
            await asyncio.sleep(3)
            # Xác nhận
            save_btn = page.locator('button:has-text("Save"), button:has-text("Lưu")').first
            if await save_btn.is_visible(timeout=3000):
                await save_btn.click()
                await asyncio.sleep(2)
            print(f"[fb_page] ✓ Upload avatar: {image_path}")
    except Exception as e:
        print(f"[fb_page] ✗ Upload avatar thất bại: {e}")


async def _upload_page_cover(page, image_path: str):
    """Upload ảnh bìa cho page"""
    try:
        cover_btn = page.locator('[aria-label*="cover"], button:has-text("Add cover")').first
        if await cover_btn.is_visible(timeout=5000):
            await cover_btn.click()
            await asyncio.sleep(2)
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(image_path)
            await asyncio.sleep(3)
            save_btn = page.locator('button:has-text("Save"), button:has-text("Lưu")').first
            if await save_btn.is_visible(timeout=3000):
                await save_btn.click()
                await asyncio.sleep(2)
            print(f"[fb_page] ✓ Upload cover: {image_path}")
    except Exception as e:
        print(f"[fb_page] ✗ Upload cover thất bại: {e}")


async def batch_create_pages(tasks: list) -> list:
    """
    Tạo nhiều page từ nhiều acc khác nhau.
    tasks: [{"profile_id": ..., "owner_uid": ..., "page_name": ..., "category": ..., "description": ...}]
    """
    from ix_browser import connect_playwright, disconnect_playwright

    results = []
    for i, task in enumerate(tasks):
        print(f"\n[fb_page] [{i+1}/{len(tasks)}] Tạo page: {task.get('page_name')}")
        profile_id = task.get("profile_id")
        if not profile_id:
            results.append({"success": False, "error": "Thiếu profile_id", **task})
            continue

        pw, browser, ctx, playwright_page = await connect_playwright(profile_id, "https://www.facebook.com")
        if not playwright_page:
            results.append({"success": False, "error": "Browser không mở được", **task})
            continue

        try:
            r = await create_fanpage(
                playwright_page,
                owner_uid=task.get("owner_uid", ""),
                page_name=task.get("page_name", ""),
                category=task.get("category", "public_figure"),
                description=task.get("description", ""),
                avatar_path=task.get("avatar_path", ""),
                cover_path=task.get("cover_path", ""),
            )
            results.append(r)
        except Exception as e:
            results.append({"success": False, "error": str(e), **task})
        finally:
            await disconnect_playwright(pw, browser, profile_id)

        await asyncio.sleep(30)  # Nghỉ giữa các page

    ok = sum(1 for r in results if r.get("success"))
    print(f"\n[fb_page] Hoàn tất: {ok}/{len(results)} page tạo thành công")
    return results


if __name__ == "__main__":
    pages = get_all_pages()
    print(f"Tổng số page: {len(pages)}")
    for p in pages:
        print(f"  [{p['page_id']}] {p['page_name']} - {p['status']} - owner: {p['owner_uid']}")
