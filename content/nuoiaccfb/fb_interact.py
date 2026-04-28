"""
fb_interact.py
Facebook interaction automation.
- Like/react posts by keyword search
- Comment on posts
- Add friends
- Join groups
- Follow pages
Daily limits enforced to avoid ban.
"""

import asyncio
import random
import sys
import time
import json
from pathlib import Path

DAILY_LOG_FILE = Path(__file__).parent / "daily_actions.json"

try:
    from debug_utils import screenshot_on_error  # type: ignore
except ImportError:
    async def screenshot_on_error(page, context_name="error"):  # type: ignore[no-redef]
        return ""

# Cho phép import common/* từ project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from common.json_store import load_json, locked_update  # type: ignore
except ImportError:
    from contextlib import contextmanager

    def load_json(path, default=None):  # type: ignore[no-redef]
        if not Path(path).exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @contextmanager
    def locked_update(path, default=None):  # type: ignore[no-redef]
        data = load_json(path, default)
        yield data
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# Conservative daily limits
DAILY_LIMITS = {
    "likes": 50,
    "comments": 10,
    "friend_requests": 20,
    "group_joins": 5,
    "page_follows": 10,
    "shares": 5,
}

COMMENT_TEMPLATES = [
    "Nice!", "Great!", "Thanks for sharing!",
    "Interesting!", "Love this!", "So true!",
    "Amazing!", "Well said!", "Keep it up!",
    "Awesome!", "Very helpful!", "Good info!",
    "Wonderful!", "Totally agree!", "Nice post!"
]


# ─────────────────────────────────────────────
# Daily limit tracker
# ─────────────────────────────────────────────

def _load_daily_log() -> dict:
    today = time.strftime("%Y-%m-%d")
    data = load_json(DAILY_LOG_FILE, default={}) or {}
    return data.get(today, {})


def _save_daily_log(fb_uid: str, action: str, count: int = 1):
    """Atomic increment counter cho (today, fb_uid, action)."""
    today = time.strftime("%Y-%m-%d")
    with locked_update(DAILY_LOG_FILE, default={}) as data:
        if today not in data:
            data[today] = {}
        if fb_uid not in data[today]:
            data[today][fb_uid] = {}
        data[today][fb_uid][action] = data[today][fb_uid].get(action, 0) + count


def _get_daily_count(fb_uid: str, action: str) -> int:
    today = time.strftime("%Y-%m-%d")
    data = load_json(DAILY_LOG_FILE, default={}) or {}
    return data.get(today, {}).get(fb_uid, {}).get(action, 0)


def _can_do(fb_uid: str, action: str) -> bool:
    limit = DAILY_LIMITS.get(action, 999)
    current = _get_daily_count(fb_uid, action)
    if current >= limit:
        print(f"[fb_interact] Daily limit reached for {fb_uid} [{action}]: {current}/{limit}")
        return False
    return True


async def _delay(min_s=1.0, max_s=4.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _scroll_down(page, times=2):
    for _ in range(times):
        await page.evaluate(f"window.scrollBy(0, {random.randint(300, 700)})")
        await _delay(0.5, 1.5)


# ─────────────────────────────────────────────
# Like Posts
# ─────────────────────────────────────────────

async def like_by_hashtag(page, fb_uid: str, hashtag: str, max_likes: int = 5) -> int:
    """Search hashtag and like posts"""
    if not _can_do(fb_uid, "likes"):
        return 0

    remaining = DAILY_LIMITS["likes"] - _get_daily_count(fb_uid, "likes")
    max_likes = min(max_likes, remaining)
    liked = 0

    print(f"[fb_interact] Liking posts with #{hashtag} (max {max_likes})")
    try:
        url = f"https://www.facebook.com/hashtag/{hashtag.lstrip('#')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)

        for _ in range(max_likes * 4):
            await _scroll_down(page)
            like_btns = await page.query_selector_all(
                '[aria-label="Like"][role="button"]:not([aria-pressed="true"])'
            )
            for btn in like_btns[:3]:
                if liked >= max_likes:
                    break
                try:
                    await btn.scroll_into_view_if_needed()
                    await btn.hover()
                    await _delay(0.5, 1.5)
                    await btn.click()
                    liked += 1
                    _save_daily_log(fb_uid, "likes")
                    print(f"[fb_interact] Liked {liked}/{max_likes}")
                    await _delay(3, 7)
                except Exception:
                    pass
            if liked >= max_likes:
                break

    except Exception as e:
        print(f"[fb_interact] Like by hashtag error: {e}")

    return liked


async def like_in_group(page, fb_uid: str, group_url: str, max_likes: int = 5) -> int:
    """Like posts in a group"""
    if not _can_do(fb_uid, "likes"):
        return 0

    remaining = DAILY_LIMITS["likes"] - _get_daily_count(fb_uid, "likes")
    max_likes = min(max_likes, remaining)
    liked = 0

    try:
        await page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        for _ in range(max_likes * 3):
            await _scroll_down(page)
            like_btns = await page.query_selector_all(
                '[aria-label="Like"][role="button"]:not([aria-pressed="true"])'
            )
            for btn in like_btns[:2]:
                if liked >= max_likes:
                    break
                try:
                    await btn.scroll_into_view_if_needed()
                    await _delay(0.5, 1.0)
                    await btn.click()
                    liked += 1
                    _save_daily_log(fb_uid, "likes")
                    await _delay(4, 9)
                except Exception:
                    pass
            if liked >= max_likes:
                break

    except Exception as e:
        print(f"[fb_interact] Like in group error: {e}")

    return liked


# ─────────────────────────────────────────────
# Comment Posts
# ─────────────────────────────────────────────

async def comment_post(page, fb_uid: str, post_url: str,
                        comment_text: str = None) -> bool:
    """Comment on a specific post"""
    if not _can_do(fb_uid, "comments"):
        return False

    if not comment_text:
        comment_text = random.choice(COMMENT_TEMPLATES)

    print(f"[fb_interact] Commenting on post: {comment_text}")
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)

        # Find comment box
        comment_box = await page.wait_for_selector(
            '[aria-label*="comment"], [data-testid*="comment"] [contenteditable]',
            timeout=10000
        )
        await comment_box.click()
        await _delay(0.5, 1)

        for char in comment_text:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.04, 0.12))

        await _delay(0.5, 1)
        await page.keyboard.press("Enter")
        await _delay(2, 4)

        _save_daily_log(fb_uid, "comments")
        print(f"[fb_interact] Comment posted: {comment_text}")
        return True

    except Exception as e:
        print(f"[fb_interact] Comment error: {e}")
        return False


async def comment_in_group(page, fb_uid: str, group_url: str,
                            comment_templates: list = None, max_comments: int = 3) -> int:
    """Comment on random posts in a group"""
    if not _can_do(fb_uid, "comments"):
        return 0

    templates = comment_templates or COMMENT_TEMPLATES
    remaining = DAILY_LIMITS["comments"] - _get_daily_count(fb_uid, "comments")
    max_comments = min(max_comments, remaining)
    commented = 0

    try:
        await page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)
        await _scroll_down(page, times=3)

        comment_btns = await page.query_selector_all('[aria-label*="Comment"]')
        for btn in comment_btns[:max_comments * 2]:
            if commented >= max_comments:
                break
            try:
                await btn.scroll_into_view_if_needed()
                await btn.click()
                await _delay(1, 2)

                text_box = await page.wait_for_selector(
                    '[contenteditable="true"][role="textbox"]', timeout=5000
                )
                text = random.choice(templates)
                for char in text:
                    await page.keyboard.type(char)
                    await asyncio.sleep(random.uniform(0.04, 0.1))

                await page.keyboard.press("Enter")
                await _delay(3, 8)
                commented += 1
                _save_daily_log(fb_uid, "comments")
                print(f"[fb_interact] Commented {commented}/{max_comments}")
            except Exception:
                pass

    except Exception as e:
        print(f"[fb_interact] Group comment error: {e}")

    return commented


# ─────────────────────────────────────────────
# Add Friends
# ─────────────────────────────────────────────

async def add_friends_from_suggestions(page, fb_uid: str, max_requests: int = 5) -> int:
    """Add friends from People You May Know"""
    if not _can_do(fb_uid, "friend_requests"):
        return 0

    remaining = DAILY_LIMITS["friend_requests"] - _get_daily_count(fb_uid, "friend_requests")
    max_requests = min(max_requests, remaining)
    added = 0

    print(f"[fb_interact] Sending {max_requests} friend requests")
    try:
        await page.goto("https://www.facebook.com/friends/suggestions", wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)

        for _ in range(3):
            await _scroll_down(page, times=2)
            add_btns = await page.query_selector_all(
                'button[aria-label*="Add friend"], [data-testid*="add-friend"]'
            )
            for btn in add_btns:
                if added >= max_requests:
                    break
                try:
                    await btn.scroll_into_view_if_needed()
                    await _delay(0.5, 1.5)
                    await btn.click()
                    added += 1
                    _save_daily_log(fb_uid, "friend_requests")
                    print(f"[fb_interact] Friend request {added}/{max_requests}")
                    await _delay(5, 12)
                except Exception:
                    pass
            if added >= max_requests:
                break

    except Exception as e:
        print(f"[fb_interact] Add friend error: {e}")

    return added


# ─────────────────────────────────────────────
# Join Groups
# ─────────────────────────────────────────────

async def join_group(page, fb_uid: str, group_url: str) -> bool:
    """Join a Facebook group"""
    if not _can_do(fb_uid, "group_joins"):
        return False

    print(f"[fb_interact] Joining group: {group_url}")
    try:
        await page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)

        join_btn = await page.query_selector(
            'button[aria-label*="Join group"], [data-testid*="join-group"]'
        )
        if join_btn:
            await join_btn.click()
            await _delay(2, 4)
            _save_daily_log(fb_uid, "group_joins")
            print("[fb_interact] Group join request sent")
            return True
        else:
            print("[fb_interact] Join button not found (already member or private)")
            return False

    except Exception as e:
        print(f"[fb_interact] Join group error: {e}")
        return False


# ─────────────────────────────────────────────
# Follow / Like Page
# ─────────────────────────────────────────────

async def follow_page(page, fb_uid: str, page_url: str) -> bool:
    """Follow/Like a Facebook page"""
    if not _can_do(fb_uid, "page_follows"):
        return False

    print(f"[fb_interact] Following page: {page_url}")
    try:
        await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)

        like_btn = await page.query_selector(
            'button[aria-label*="Like this page"], [data-testid*="page-like-button"]'
        )
        if not like_btn:
            # Try Follow button
            like_btn = await page.query_selector('button[aria-label*="Follow"]')

        if like_btn:
            await like_btn.click()
            await _delay(2, 3)
            _save_daily_log(fb_uid, "page_follows")
            print("[fb_interact] Page followed/liked")
            return True

    except Exception as e:
        print(f"[fb_interact] Follow page error: {e}")
    return False


# ─────────────────────────────────────────────
# Share Post
# ─────────────────────────────────────────────

async def share_post(page, fb_uid: str, post_url: str) -> bool:
    """Share a post to timeline"""
    if not _can_do(fb_uid, "shares"):
        return False

    print(f"[fb_interact] Sharing post: {post_url}")
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        share_btn = await page.query_selector('[aria-label*="Share"][role="button"]')
        if share_btn:
            await share_btn.click()
            await _delay(1, 2)
            # Click "Share Now" option
            share_now = await page.query_selector('[aria-label*="Share now"]')
            if share_now:
                await share_now.click()
                await _delay(2, 4)
                _save_daily_log(fb_uid, "shares")
                print("[fb_interact] Post shared")
                return True

    except Exception as e:
        print(f"[fb_interact] Share error: {e}")
    return False


# ─────────────────────────────────────────────
# Full interaction session
# ─────────────────────────────────────────────

async def interact_session(page, fb_uid: str, config: dict) -> dict:
    """
    Run a full interaction session.
    config example:
    {
        "hashtags": ["cooking", "travel"],
        "groups": ["https://facebook.com/groups/xxx"],
        "like_per_hashtag": 3,
        "comment_per_group": 2,
        "add_friends": 3,
    }
    """
    stats = {"fb_uid": fb_uid, "likes": 0, "comments": 0, "friends": 0}

    # Like by hashtags
    for tag in config.get("hashtags", []):
        n = await like_by_hashtag(page, fb_uid, tag, config.get("like_per_hashtag", 3))
        stats["likes"] += n
        await _delay(10, 20)

    # Interact in groups
    for group_url in config.get("groups", []):
        n = await like_in_group(page, fb_uid, group_url, config.get("like_per_group", 3))
        stats["likes"] += n
        await _delay(5, 10)

        c = await comment_in_group(page, fb_uid, group_url, max_comments=config.get("comment_per_group", 2))
        stats["comments"] += c
        await _delay(10, 20)

    # Add friends
    if config.get("add_friends", 0) > 0:
        n = await add_friends_from_suggestions(page, fb_uid, config["add_friends"])
        stats["friends"] += n

    print(f"[fb_interact] Session done for {fb_uid}: {stats}")
    return stats


# Alias để giữ tương thích với caller cũ (app.py route /api/tasks/run-group)
async def run_interactions(page, fb_uid: str, config: dict) -> dict:
    """Alias cho interact_session — giữ tương thích ngược."""
    return await interact_session(page, fb_uid, config)
