"""
fb_page_post.py
Đăng bài viết và Reel lên Fanpage qua Playwright + IX Browser
"""

import asyncio
import os
import random
import re
import time
from pathlib import Path

try:
    from debug_utils import screenshot_on_error  # type: ignore
except ImportError:
    async def screenshot_on_error(page, context_name="error"):  # type: ignore[no-redef]
        return ""

try:
    from video_dedup import check_and_record, record_post  # type: ignore
except ImportError:
    def check_and_record(video_path, page_url, fb_uid=""):  # type: ignore[no-redef]
        return {"hash": "", "already_posted": False, "skip": False}

    def record_post(video_hash, page_url, fb_uid="", video_path=""):  # type: ignore[no-redef]
        return False


# ─────────────────────────────────────────────
# Content Spin
# ─────────────────────────────────────────────

def spin_content(template: str) -> str:
    """Spin content: {option1|option2|option3} → chọn ngẫu nhiên"""
    def replace_spin(match):
        options = match.group(1).split("|")
        return random.choice(options)
    return re.sub(r'\{([^{}]+)\}', replace_spin, template)


# ─────────────────────────────────────────────
# Post bài viết lên Page
# ─────────────────────────────────────────────

async def post_to_page(page, page_url: str, content: str,
                        images: list = None,
                        schedule_time: str = "",
                        spin: bool = True) -> dict:
    """
    Đăng bài viết lên Fanpage.
    page: Playwright page đã login với acc có quyền Editor trên page
    page_url: URL fanpage
    content: Nội dung bài đăng (hỗ trợ {spin|content})
    images: List đường dẫn ảnh cần đính kèm
    schedule_time: "HH:MM DD/MM/YYYY" nếu muốn lên lịch, để trống = đăng ngay
    spin: Có spin content không
    """
    result = {"success": False, "page_url": page_url, "error": ""}
    images = images or []

    try:
        if spin:
            content = spin_content(content)

        print(f"[fb_page_post] Đăng bài lên: {page_url}")

        # Mở page
        await page.goto(page_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Bấm vào ô "Create post" / "Tạo bài viết"
        create_post_selectors = [
            '[aria-label*="Create post"]',
            '[placeholder*="Write something"]',
            '[placeholder*="Viết gì đó"]',
            'div[role="button"]:has-text("Create post")',
            'div[role="button"]:has-text("Tạo bài viết")',
        ]
        clicked = False
        for sel in create_post_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=4000):
                    await btn.click()
                    clicked = True
                    await asyncio.sleep(2)
                    break
            except Exception:
                continue

        if not clicked:
            result["error"] = "Không tìm thấy ô tạo bài viết"
            return result

        # Nhập nội dung
        text_area_selectors = [
            '[contenteditable="true"][data-lexical-editor]',
            '[contenteditable="true"][aria-label*="post"]',
            '[contenteditable="true"]',
        ]
        for sel in text_area_selectors:
            try:
                text_area = page.locator(sel).first
                if await text_area.is_visible(timeout=4000):
                    await text_area.click()
                    await asyncio.sleep(1)
                    await text_area.type(content, delay=20)
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue

        # Đính kèm ảnh (nếu có)
        if images:
            try:
                photo_btn = page.locator('button:has-text("Photo"), [aria-label*="Photo/video"], [aria-label*="Ảnh"]').first
                if await photo_btn.is_visible(timeout=5000):
                    await photo_btn.click()
                    await asyncio.sleep(2)
                    file_input = page.locator('input[type="file"]').first
                    await file_input.set_input_files(images)
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"[fb_page_post] ⚠ Upload ảnh thất bại: {e}")

        # Lên lịch (nếu có)
        if schedule_time:
            scheduled = await _schedule_post(page, schedule_time)
            if not scheduled:
                print(f"[fb_page_post] ⚠ Lên lịch thất bại, sẽ đăng ngay")

        # Đăng bài
        post_btn_selectors = [
            'button:has-text("Post")',
            'button:has-text("Đăng")',
            'button:has-text("Publish")',
            'button:has-text("Xuất bản")',
            'button[data-testid*="post"]',
        ]
        posted = False
        for sel in post_btn_selectors:
            try:
                btn = page.locator(sel).last
                if await btn.is_visible(timeout=4000) and await btn.is_enabled():
                    await btn.click()
                    posted = True
                    await asyncio.sleep(4)
                    break
            except Exception:
                continue

        if posted:
            result["success"] = True
            result["content_preview"] = content[:80] + "..." if len(content) > 80 else content
            # Cập nhật post_count trong DB
            from fb_page import get_all_pages, update_page
            for p in get_all_pages():
                if page_url.rstrip("/").endswith(p.get("page_id", "")) or \
                   p.get("page_url", "").rstrip("/") == page_url.rstrip("/"):
                    update_page(p["page_id"],
                                post_count=p.get("post_count", 0) + 1,
                                last_posted_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                    break
            print(f"[fb_page_post] ✓ Đăng bài thành công: {content[:50]}")
        else:
            result["error"] = "Không tìm thấy nút Đăng"
            await screenshot_on_error(page, f"post_to_page_no_btn")

    except Exception as e:
        result["error"] = str(e)
        print(f"[fb_page_post] ✗ Lỗi: {e}")
        await screenshot_on_error(page, f"post_to_page_exception")

    return result


async def _schedule_post(page, schedule_time: str) -> bool:
    """Lên lịch đăng bài - schedule_time: 'HH:MM DD/MM/YYYY'"""
    try:
        # Tìm nút lên lịch (dropdown bên cạnh nút Post)
        sched_btn = page.locator('[aria-label*="Schedule"], button:has-text("Schedule"), [aria-label*="Lên lịch"]').first
        if await sched_btn.is_visible(timeout=4000):
            await sched_btn.click()
            await asyncio.sleep(2)

            # Nhập ngày giờ
            parts = schedule_time.split()
            if len(parts) == 2:
                time_str, date_str = parts[0], parts[1]
                date_parts = date_str.split("/")
                if len(date_parts) == 3:
                    day, month, year = date_parts
                    # Điền ngày
                    date_input = page.locator('input[type="date"], input[placeholder*="date"]').first
                    if await date_input.is_visible(timeout=3000):
                        await date_input.fill(f"{year}-{month}-{day}")

                    # Điền giờ
                    time_input = page.locator('input[type="time"], input[placeholder*="time"]').first
                    if await time_input.is_visible(timeout=3000):
                        await time_input.fill(time_str)
                    await asyncio.sleep(1)

            # Xác nhận lên lịch
            confirm = page.locator('button:has-text("Schedule"), button:has-text("Lên lịch")').last
            if await confirm.is_visible(timeout=3000):
                await confirm.click()
                await asyncio.sleep(2)
                return True
    except Exception as e:
        print(f"[fb_page_post] Schedule error: {e}")
    return False


# ─────────────────────────────────────────────
# Upload Reel lên Page
# ─────────────────────────────────────────────

async def post_reel_to_page(page, page_url: str, video_path: str,
                              caption: str = "", spin: bool = True,
                              thumbnail_path: str = "") -> dict:
    """
    Upload và đăng Reel lên Fanpage.
    video_path: Đường dẫn file video (.mp4)
    caption: Mô tả video (hỗ trợ spin)
    """
    result = {"success": False, "page_url": page_url, "error": ""}

    if not os.path.exists(video_path):
        result["error"] = f"Không tìm thấy video: {video_path}"
        return result

    # ── Dedup check ──
    dedup = check_and_record(video_path, page_url)
    if dedup["skip"]:
        result["error"] = "dedup: video đã đăng lên page này"
        result["skipped"] = True
        return result
    _video_hash = dedup["hash"]

    if spin and caption:
        caption = spin_content(caption)

    try:
        print(f"[fb_page_post] Upload Reel: {video_path}")

        # Mở trang tạo Reel của page
        reel_url = page_url.rstrip("/") + "/reels/create/"
        await page.goto(reel_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Nếu không vào được trang reel trực tiếp, thử từ page
        if "reels/create" not in page.url:
            await page.goto(page_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(2)

            # Tìm nút "Reel" hoặc "Video"
            reel_selectors = [
                'button:has-text("Reel")',
                '[aria-label*="Reel"]',
                'button:has-text("Video")',
                '[data-testid*="reel"]',
            ]
            for sel in reel_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

        # Upload video file
        upload_selectors = [
            'input[type="file"][accept*="video"]',
            'input[type="file"]',
        ]
        uploaded = False
        for sel in upload_selectors:
            try:
                file_input = page.locator(sel).first
                if await file_input.count() > 0:
                    await file_input.set_input_files(video_path)
                    uploaded = True
                    await asyncio.sleep(5)  # Chờ upload
                    break
            except Exception:
                continue

        if not uploaded:
            # Thử click vào khu vực upload
            try:
                upload_area = page.locator('[aria-label*="upload"], div:has-text("drag and drop"), div:has-text("tải lên")').first
                if await upload_area.is_visible(timeout=5000):
                    await upload_area.click()
                    await asyncio.sleep(2)
                    file_input = page.locator('input[type="file"]').first
                    await file_input.set_input_files(video_path)
                    await asyncio.sleep(5)
            except Exception as e:
                result["error"] = f"Không upload được video: {e}"
                return result

        # Chờ video xử lý (có thể mất 10-30s)
        print(f"[fb_page_post] Chờ xử lý video...")
        await asyncio.sleep(15)

        # Upload thumbnail nếu có
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                thumb_btn = page.locator('button:has-text("thumbnail"), [aria-label*="thumbnail"]').first
                if await thumb_btn.is_visible(timeout=5000):
                    await thumb_btn.click()
                    await asyncio.sleep(2)
                    thumb_input = page.locator('input[type="file"]').first
                    await thumb_input.set_input_files(thumbnail_path)
                    await asyncio.sleep(3)
            except Exception:
                pass

        # Nhập caption
        if caption:
            caption_selectors = [
                '[contenteditable="true"]',
                'textarea[placeholder*="caption"]',
                'textarea[aria-label*="description"]',
                'textarea',
            ]
            for sel in caption_selectors:
                try:
                    cap_input = page.locator(sel).first
                    if await cap_input.is_visible(timeout=4000):
                        await cap_input.click()
                        await cap_input.type(caption, delay=15)
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

        # Publish / Post Reel
        publish_selectors = [
            'button:has-text("Publish")',
            'button:has-text("Post")',
            'button:has-text("Share")',
            'button:has-text("Xuất bản")',
            'button:has-text("Đăng")',
            'button:has-text("Chia sẻ")',
        ]
        for sel in publish_selectors:
            try:
                btn = page.locator(sel).last
                if await btn.is_visible(timeout=4000) and await btn.is_enabled():
                    await btn.click()
                    await asyncio.sleep(5)
                    result["success"] = True
                    print(f"[fb_page_post] ✓ Đăng Reel thành công!")
                    # Cập nhật reel_count
                    from fb_page import get_all_pages, update_page
                    for p in get_all_pages():
                        if page_url.rstrip("/").endswith(p.get("page_id", "")) or \
                           p.get("page_url", "").rstrip("/") == page_url.rstrip("/"):
                            update_page(p["page_id"],
                                        reel_count=p.get("reel_count", 0) + 1,
                                        last_posted_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                            break
                    break
            except Exception:
                continue

        if result["success"]:
            # Ghi nhận dedup sau khi đăng thành công
            if _video_hash:
                record_post(_video_hash, page_url, video_path=video_path)
        else:
            result["error"] = "Không tìm thấy nút Publish"
            await screenshot_on_error(page, "post_reel_no_publish_btn")

    except Exception as e:
        result["error"] = str(e)
        print(f"[fb_page_post] ✗ Lỗi upload Reel: {e}")
        await screenshot_on_error(page, "post_reel_exception")

    return result


# ─────────────────────────────────────────────
# Batch post
# ─────────────────────────────────────────────

async def batch_post_to_pages(tasks: list, post_type: str = "post") -> list:
    """
    Đăng bài/Reel hàng loạt lên nhiều page.
    post_type: 'post' | 'reel'
    tasks: [{
        "profile_id": int,
        "page_url": str,
        "content": str,           # cho post
        "video_path": str,        # cho reel
        "images": [],             # cho post
        "caption": str,           # cho reel
        "schedule_time": str,     # tùy chọn
    }]
    """
    from ix_browser import connect_playwright, disconnect_playwright

    results = []
    for i, task in enumerate(tasks):
        print(f"\n[fb_page_post] [{i+1}/{len(tasks)}] Page: {task.get('page_url')}")
        profile_id = task.get("profile_id")
        if not profile_id:
            results.append({"success": False, "error": "Thiếu profile_id", **task})
            continue

        pw, browser, ctx, playwright_page = await connect_playwright(
            profile_id, task.get("page_url", "https://www.facebook.com")
        )
        if not playwright_page:
            results.append({"success": False, "error": "Browser không mở được", **task})
            continue

        try:
            if post_type == "reel":
                r = await post_reel_to_page(
                    playwright_page,
                    page_url=task.get("page_url", ""),
                    video_path=task.get("video_path", ""),
                    caption=task.get("caption", task.get("content", "")),
                )
            else:
                r = await post_to_page(
                    playwright_page,
                    page_url=task.get("page_url", ""),
                    content=task.get("content", ""),
                    images=task.get("images", []),
                    schedule_time=task.get("schedule_time", ""),
                )
            results.append(r)
        except Exception as e:
            results.append({"success": False, "error": str(e), **task})
        finally:
            await disconnect_playwright(pw, browser, profile_id)

        # Delay ngẫu nhiên giữa các page
        delay = random.randint(15, 45)
        print(f"[fb_page_post] Nghỉ {delay}s...")
        await asyncio.sleep(delay)

    ok = sum(1 for r in results if r.get("success"))
    print(f"\n[fb_page_post] Hoàn tất: {ok}/{len(results)} thành công")
    return results
