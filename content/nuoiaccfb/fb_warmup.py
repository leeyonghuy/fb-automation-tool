"""
fb_warmup.py
Facebook account warming - simulate natural human behavior.
- Scroll newsfeed
- Like posts (limited per day)
- Watch videos
- Search keywords
- Visit profiles
- React to stories

Daily limits (safe defaults):
  - Likes: 30-50
  - Comments: 5-10
  - Profile visits: 10-20
  - Searches: 5-10
"""

import asyncio
import random
import time
from typing import Optional

# Safe daily limits
DAILY_LIMITS = {
    "likes": 40,
    "comments": 8,
    "profile_visits": 15,
    "searches": 8,
    "video_watches": 10,
}

SEARCH_KEYWORDS = [
    "tin tuc moi nhat", "funny videos", "travel vietnam",
    "food recipes", "technology news", "music 2024",
    "sports highlights", "cooking tips", "nature photography",
    "motivational quotes", "business tips", "health fitness"
]

COMMENT_TEMPLATES = [
    "Nice!", "Great post!", "Thanks for sharing!",
    "Interesting!", "Love this!", "So true!",
    "Amazing!", "Well said!", "Keep it up!",
    "Awesome content!"
]


# ─────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────

async def _delay(min_s=1.0, max_s=4.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _scroll_down(page, times=3, scroll_px_min=300, scroll_px_max=800):
    """Scroll down naturally"""
    for _ in range(times):
        scroll_amount = random.randint(scroll_px_min, scroll_px_max)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await _delay(0.5, 2.0)


async def _scroll_up(page, times=1):
    for _ in range(times):
        scroll_amount = random.randint(200, 500)
        await page.evaluate(f"window.scrollBy(0, -{scroll_amount})")
        await _delay(0.5, 1.5)


async def _move_mouse_randomly(page):
    """Move mouse to random position to simulate human"""
    try:
        x = random.randint(100, 1200)
        y = random.randint(100, 700)
        await page.mouse.move(x, y)
    except Exception:
        pass


async def _hover_element(page, element):
    """Hover over an element"""
    try:
        await element.hover()
        await _delay(0.3, 1.0)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Warmup Actions
# ─────────────────────────────────────────────

async def scroll_newsfeed(page, duration_sec=30) -> int:
    """
    Scroll newsfeed for given duration.
    Returns number of scrolls performed.
    """
    print(f"[fb_warmup] Scrolling newsfeed for {duration_sec}s")
    scrolls = 0
    start = time.time()

    try:
        await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)

        while time.time() - start < duration_sec:
            # Random scroll amount
            scroll_px = random.randint(300, 700)
            await page.evaluate(f"window.scrollBy(0, {scroll_px})")
            scrolls += 1
            await _move_mouse_randomly(page)

            # Sometimes pause to "read"
            if random.random() < 0.3:
                await _delay(3, 8)
            else:
                await _delay(1, 3)

            # Occasionally scroll back up a bit
            if random.random() < 0.15:
                await _scroll_up(page)

    except Exception as e:
        print(f"[fb_warmup] Scroll error: {e}")

    print(f"[fb_warmup] Scrolled {scrolls} times")
    return scrolls


async def like_posts(page, max_likes: int = 5) -> int:
    """
    Like random posts on newsfeed.
    Returns number of likes performed.
    """
    print(f"[fb_warmup] Liking up to {max_likes} posts")
    liked = 0

    try:
        await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        for _ in range(max_likes * 3):  # scroll more to find enough posts
            await _scroll_down(page, times=2)
            await _delay(1, 2)

            # Find like buttons (not already liked)
            like_btns = await page.query_selector_all('[aria-label="Like"][role="button"]:not([aria-pressed="true"])')

            if like_btns:
                btn = random.choice(like_btns[:5])  # Pick from first 5 visible
                await _hover_element(page, btn)
                await _delay(0.5, 1.5)

                # Sometimes use react instead of like
                if random.random() < 0.2:
                    # Hold to open reactions
                    await btn.hover()
                    await _delay(1.5, 2.5)
                    # Just like for safety
                    await btn.click()
                else:
                    await btn.click()

                liked += 1
                print(f"[fb_warmup] Liked post {liked}/{max_likes}")
                await _delay(3, 8)  # Wait between likes

                if liked >= max_likes:
                    break

    except Exception as e:
        print(f"[fb_warmup] Like error: {e}")

    return liked


async def watch_video(page, duration_sec=20) -> bool:
    """Watch a video on the feed"""
    print(f"[fb_warmup] Watching video for ~{duration_sec}s")
    try:
        # Find video elements
        videos = await page.query_selector_all('video')
        if not videos:
            await _scroll_down(page, times=5)
            videos = await page.query_selector_all('video')

        if videos:
            video = videos[0]
            await video.scroll_into_view_if_needed()
            await _delay(1, 2)
            await video.click()  # Play/pause toggle
            await asyncio.sleep(random.uniform(duration_sec * 0.7, duration_sec * 1.2))
            print("[fb_warmup] Video watched")
            return True
    except Exception as e:
        print(f"[fb_warmup] Video error: {e}")
    return False


async def search_keyword(page, keyword: str = None) -> bool:
    """Search for a keyword on Facebook"""
    if not keyword:
        keyword = random.choice(SEARCH_KEYWORDS)

    print(f"[fb_warmup] Searching: {keyword}")
    try:
        search_box = await page.wait_for_selector(
            '[role="search"] input, input[placeholder*="Search"], [aria-label*="Search"]',
            timeout=10000
        )
        await search_box.click()
        await _delay(0.5, 1)

        # Type like human
        for char in keyword:
            await search_box.type(char, delay=random.randint(50, 150))

        await _delay(0.5, 1)
        await page.keyboard.press("Enter")
        await _delay(2, 4)

        # Scroll results
        await _scroll_down(page, times=random.randint(2, 5))
        await _delay(3, 6)

        # Go back
        await page.go_back()
        await _delay(1, 2)
        return True

    except Exception as e:
        print(f"[fb_warmup] Search error: {e}")
        return False


async def visit_profile(page, profile_url: str = None) -> bool:
    """Visit a Facebook profile"""
    if not profile_url:
        profile_url = "https://www.facebook.com"

    print(f"[fb_warmup] Visiting profile: {profile_url}")
    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        await _delay(2, 4)
        await _scroll_down(page, times=random.randint(3, 6))
        await _delay(2, 5)
        return True
    except Exception as e:
        print(f"[fb_warmup] Visit error: {e}")
        return False


async def check_notifications(page) -> bool:
    """Check and dismiss notifications"""
    print("[fb_warmup] Checking notifications")
    try:
        await page.goto("https://www.facebook.com/notifications", wait_until="domcontentloaded", timeout=20000)
        await _delay(2, 4)
        await _scroll_down(page, times=2)
        await _delay(2, 3)
        return True
    except Exception as e:
        print(f"[fb_warmup] Notification error: {e}")
        return False


async def check_messages(page) -> bool:
    """Briefly check messages"""
    print("[fb_warmup] Checking messages")
    try:
        await page.goto("https://www.facebook.com/messages", wait_until="domcontentloaded", timeout=20000)
        await _delay(2, 4)
        return True
    except Exception as e:
        print(f"[fb_warmup] Messages error: {e}")
        return False


# ─────────────────────────────────────────────
# Full Warmup Session
# ─────────────────────────────────────────────

async def warmup_session(page, fb_uid: str, intensity: str = "light") -> dict:
    """
    Run a full warmup session for one account.

    intensity:
      'light'  - 10-15 min, few actions (day 1-3)
      'medium' - 20-30 min, moderate (day 4-7)
      'normal' - 30-45 min, regular (day 8+)

    Returns stats dict.
    """
    stats = {
        "fb_uid": fb_uid,
        "scrolls": 0,
        "likes": 0,
        "searches": 0,
        "videos_watched": 0,
        "profile_visits": 0,
    }

    configs = {
        "light":  {"scroll_time": 60,  "likes": 3,  "searches": 1, "videos": 1, "visits": 0},
        "medium": {"scroll_time": 120, "likes": 8,  "searches": 3, "videos": 2, "visits": 2},
        "normal": {"scroll_time": 180, "likes": 15, "searches": 5, "videos": 3, "visits": 5},
    }
    cfg = configs.get(intensity, configs["light"])

    print(f"\n[fb_warmup] Starting {intensity} warmup for {fb_uid}")

    # 1. Scroll newsfeed
    stats["scrolls"] = await scroll_newsfeed(page, duration_sec=cfg["scroll_time"])
    await _delay(3, 6)

    # 2. Like posts
    if cfg["likes"] > 0:
        stats["likes"] = await like_posts(page, max_likes=cfg["likes"])
        await _delay(5, 10)

    # 3. Search keywords
    for _ in range(cfg["searches"]):
        await search_keyword(page)
        await _delay(5, 10)
    stats["searches"] = cfg["searches"]

    # 4. Watch video
    for _ in range(cfg["videos"]):
        await _scroll_down(page, times=5)
        watched = await watch_video(page, duration_sec=random.randint(15, 40))
        if watched:
            stats["videos_watched"] += 1
        await _delay(5, 10)

    # 5. Check notifications (random)
    if random.random() < 0.5:
        await check_notifications(page)
        await _delay(2, 5)

    # 6. Check messages (random)
    if random.random() < 0.3:
        await check_messages(page)
        await _delay(2, 5)

    # 7. Go back to feed
    await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=20000)
    await _scroll_down(page, times=3)

    print(f"[fb_warmup] Warmup complete for {fb_uid}: {stats}")

    # Update account
    try:
        from account_manager import update_account, get_account
        acc = get_account(fb_uid)
        if acc:
            days = acc.get("warm_up_days", 0) + 1
            status = "warming"
            if days >= 14:
                status = "active"
            elif days >= 7 and intensity in ["medium", "normal"]:
                status = "warming"
            update_account(fb_uid,
                           warm_up_days=days,
                           status=status,
                           last_action_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass

    return stats


# ─────────────────────────────────────────────
# Batch warmup
# ─────────────────────────────────────────────

async def batch_warmup(accounts: list, intensity: str = "light") -> list:
    """
    Warmup multiple accounts sequentially.
    accounts: [{"profile_id": x, "fb_uid": y}, ...]
    """
    from ix_browser import connect_playwright, disconnect_playwright

    results = []
    for i, acc in enumerate(accounts):
        pid = acc.get("profile_id")
        fb_uid = acc.get("fb_uid")
        print(f"\n[fb_warmup] [{i+1}/{len(accounts)}] Warming up: {fb_uid}")

        pw, browser, context, page = await connect_playwright(pid, url="https://www.facebook.com")
        if not page:
            results.append({"fb_uid": fb_uid, "error": "browser_failed"})
            continue

        try:
            stats = await warmup_session(page, fb_uid, intensity)
            results.append(stats)
        except Exception as e:
            print(f"[fb_warmup] Error for {fb_uid}: {e}")
            results.append({"fb_uid": fb_uid, "error": str(e)})
        finally:
            await disconnect_playwright(pw, browser, pid)

        # Wait between accounts
        wait = random.uniform(30, 90)
        print(f"[fb_warmup] Waiting {wait:.0f}s before next account...")
        await asyncio.sleep(wait)

    return results
