"""
fb_post.py
Facebook auto posting - text, image, video.
- Post to personal timeline
- Post to group
- Post to fanpage
- Schedule posts
"""

import asyncio
import random
import time
import os
from pathlib import Path


async def _delay(min_s=1.0, max_s=3.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _human_type(page, selector: str, text: str):
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.03, 0.12))


# ─────────────────────────────────────────────
# Post to Timeline
# ─────────────────────────────────────────────

async def post_to_timeline(page, content: str, images: list = None) -> bool:
    """Post to personal timeline"""
    print(f"[fb_post] Posting to timeline: {content[:50]}...")
    try:
        await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        # Click "What's on your mind" box
        post_box = await page.wait_for_selector(
            '[data-testid="status-attachment-mentions-input"], '
            '[role="button"][tabindex="0"][data-testid="tnt_composer_input_div"], '
            'div[aria-label*="mind"], div[data-pagelet="FeedComposer"]',
            timeout=10000
        )
        await post_box.click()
        await _delay(1, 2)

        # Type content
        text_area = await page.wait_for_selector(
            '[contenteditable="true"][role="textbox"], '
            'div[aria-label*="mind"][contenteditable="true"]',
            timeout=10000
        )
        await text_area.click()
        await _delay(0.5, 1)

        # Type text
        for char in content:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.02, 0.08))

        await _delay(1, 2)

        # Upload images if provided
        if images:
            for img_path in images:
                if os.path.exists(img_path):
                    await _upload_image(page, img_path)

        await _delay(1, 2)

        # Click Post button
        post_btn = await page.wait_for_selector(
            '[aria-label="Post"][role="button"], '
            'button[type="submit"]:has-text("Post"), '
            'div[aria-label="Post"]',
            timeout=10000
        )
        await post_btn.click()
        await _delay(3, 5)

        print("[fb_post] Timeline post submitted")
        return True

    except Exception as e:
        print(f"[fb_post] Timeline post error: {e}")
        return False


async def _upload_image(page, img_path: str):
    """Upload image in post composer"""
    try:
        # Click photo/video button
        photo_btn = await page.query_selector(
            '[data-testid="photo-video-button"], [aria-label*="Photo"], [aria-label*="photo"]'
        )
        if photo_btn:
            await photo_btn.click()
            await _delay(1, 2)

        # File input
        file_input = await page.query_selector('input[type="file"][accept*="image"]')
        if file_input:
            await file_input.set_input_files(img_path)
            await _delay(2, 4)
            print(f"[fb_post] Image uploaded: {img_path}")
    except Exception as e:
        print(f"[fb_post] Image upload error: {e}")


# ─────────────────────────────────────────────
# Post to Group
# ─────────────────────────────────────────────

async def post_to_group(page, group_url: str, content: str, images: list = None) -> bool:
    """Post to a Facebook group"""
    print(f"[fb_post] Posting to group: {group_url}")
    try:
        await page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        # Click composer
        composer = await page.wait_for_selector(
            'div[aria-label*="Write something"], div[aria-label*="mind"], '
            '[data-pagelet="GroupComposerArea"] [role="button"]',
            timeout=10000
        )
        await composer.click()
        await _delay(1, 2)

        # Type content
        text_area = await page.wait_for_selector(
            '[contenteditable="true"][role="textbox"]', timeout=10000
        )
        for char in content:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.02, 0.08))

        await _delay(1, 2)

        if images:
            for img in images:
                if os.path.exists(img):
                    await _upload_image(page, img)

        # Submit
        post_btn = await page.wait_for_selector(
            '[aria-label="Post"][role="button"], button:has-text("Post")',
            timeout=10000
        )
        await post_btn.click()
        await _delay(3, 5)

        print("[fb_post] Group post submitted")
        return True

    except Exception as e:
        print(f"[fb_post] Group post error: {e}")
        return False


# ─────────────────────────────────────────────
# Post to Fanpage
# ─────────────────────────────────────────────

async def post_to_fanpage(page, page_url: str, content: str, images: list = None) -> bool:
    """Post to a Facebook fanpage"""
    print(f"[fb_post] Posting to fanpage: {page_url}")
    try:
        await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        composer = await page.wait_for_selector(
            'div[aria-label*="Write something"], div[aria-label*="mind"]',
            timeout=10000
        )
        await composer.click()
        await _delay(1, 2)

        text_area = await page.wait_for_selector(
            '[contenteditable="true"][role="textbox"]', timeout=10000
        )
        for char in content:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.02, 0.08))

        await _delay(1, 2)

        if images:
            for img in images:
                if os.path.exists(img):
                    await _upload_image(page, img)

        post_btn = await page.wait_for_selector(
            '[aria-label="Post"][role="button"]', timeout=10000
        )
        await post_btn.click()
        await _delay(3, 5)

        print("[fb_post] Fanpage post submitted")
        return True

    except Exception as e:
        print(f"[fb_post] Fanpage post error: {e}")
        return False


# ─────────────────────────────────────────────
# Spin Content (simple)
# ─────────────────────────────────────────────

def spin_content(template: str) -> str:
    """
    Simple spin syntax: {option1|option2|option3}
    e.g. "Hello {world|everyone|friends}!" -> "Hello friends!"
    """
    import re
    def pick(m):
        options = m.group(1).split("|")
        return random.choice(options)
    return re.sub(r'\{([^}]+)\}', pick, template)


# ─────────────────────────────────────────────
# Scheduled Post Runner
# ─────────────────────────────────────────────

async def post_with_schedule(tasks: list) -> list:
    """
    Run scheduled posts.
    tasks: [
        {
            "profile_id": 72,
            "fb_uid": "acc_01",
            "post_type": "timeline" | "group" | "fanpage",
            "target_url": "https://www.facebook.com/groups/xxx",  # for group/fanpage
            "content": "Hello {world|everyone}!",
            "images": [],
            "scheduled_at": "2024-01-01 10:00:00"  # optional
        }
    ]
    """
    from ix_browser import connect_playwright, disconnect_playwright

    results = []
    for i, task in enumerate(tasks):
        pid = task.get("profile_id")
        fb_uid = task.get("fb_uid", "unknown")
        post_type = task.get("post_type", "timeline")
        content_template = task.get("content", "")
        images = task.get("images", [])
        target_url = task.get("target_url", "")
        scheduled_at = task.get("scheduled_at")

        # Wait for schedule
        if scheduled_at:
            target_time = time.mktime(time.strptime(scheduled_at, "%Y-%m-%d %H:%M:%S"))
            wait_sec = target_time - time.time()
            if wait_sec > 0:
                print(f"[fb_post] Waiting {wait_sec:.0f}s for scheduled post...")
                await asyncio.sleep(wait_sec)

        # Spin content
        content = spin_content(content_template)

        print(f"\n[fb_post] [{i+1}/{len(tasks)}] Posting ({post_type}) for {fb_uid}")
        pw, browser, context, page = await connect_playwright(pid)
        if not page:
            results.append({"fb_uid": fb_uid, "success": False, "error": "browser_failed"})
            continue

        try:
            success = False
            if post_type == "timeline":
                success = await post_to_timeline(page, content, images)
            elif post_type == "group":
                success = await post_to_group(page, target_url, content, images)
            elif post_type == "fanpage":
                success = await post_to_fanpage(page, target_url, content, images)

            results.append({"fb_uid": fb_uid, "success": success, "content": content[:80]})

            # Update post count
            if success:
                try:
                    from account_manager import increment_post_count
                    increment_post_count(fb_uid)
                except Exception:
                    pass

        except Exception as e:
            print(f"[fb_post] Error for {fb_uid}: {e}")
            results.append({"fb_uid": fb_uid, "success": False, "error": str(e)})
        finally:
            await disconnect_playwright(pw, browser, pid)

        await asyncio.sleep(random.uniform(10, 30))

    return results
