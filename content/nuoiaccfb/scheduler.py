"""
scheduler.py
Task scheduler for Facebook automation.
- Queue tasks: warmup, post, interact
- Run tasks by time or immediately
- Retry on failure
- Log results to file
Usage:
  python scheduler.py --mode warmup
  python scheduler.py --mode post --config post_tasks.json
  python scheduler.py --mode interact
  python scheduler.py --mode all
"""

import asyncio
import json
import random
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

LOG_FILE = Path(__file__).parent / "scheduler.log"
CONFIG_DIR = Path(__file__).parent


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_accounts() -> list:
    """Load active accounts from account_manager"""
    try:
        from account_manager import get_all_accounts
        return get_all_accounts()
    except Exception:
        pass
    # Fallback: load from profiles_created.json
    pfile = CONFIG_DIR / "profiles_created.json"
    if pfile.exists():
        with open(pfile, encoding="utf-8") as f:
            profiles = json.load(f)
        return [
            {
                "fb_uid": p.get("name", str(p.get("profile_id"))),
                "profile_id": p.get("profile_id"),
                "status": "active",
                "warm_up_days": 0,
            }
            for p in profiles
        ]
    return []


# ─────────────────────────────────────────────
# Warmup Mode
# ─────────────────────────────────────────────

async def run_warmup(accounts: list = None, intensity: str = None):
    """Run warmup session for all accounts"""
    from fb_warmup import batch_warmup

    if accounts is None:
        accounts = load_accounts()

    # Filter accounts that need warming
    to_warm = [
        a for a in accounts
        if a.get("status") in ("active", "warming", "new") and a.get("profile_id")
    ]

    if not to_warm:
        log("[scheduler] No accounts to warm up")
        return

    # Auto-detect intensity based on warm_up_days
    def get_intensity(acc):
        if intensity:
            return intensity
        days = acc.get("warm_up_days", 0)
        if days < 3:
            return "light"
        elif days < 7:
            return "medium"
        return "normal"

    log(f"[scheduler] Starting warmup for {len(to_warm)} accounts")
    results = []
    for acc in to_warm:
        inten = get_intensity(acc)
        log(f"[scheduler] Warming [{acc['fb_uid']}] intensity={inten}")
        try:
            from ix_browser import connect_playwright, disconnect_playwright
            pw, browser, context, page = await connect_playwright(
                acc["profile_id"], url="https://www.facebook.com"
            )
            if not page:
                log(f"[scheduler] Browser failed for {acc['fb_uid']}")
                continue
            from fb_warmup import warmup_session
            stats = await warmup_session(page, acc["fb_uid"], inten)
            results.append(stats)
            await disconnect_playwright(pw, browser, acc["profile_id"])
        except Exception as e:
            log(f"[scheduler] Warmup error {acc['fb_uid']}: {e}")

        await asyncio.sleep(random.uniform(30, 90))

    log(f"[scheduler] Warmup complete: {len(results)} accounts done")
    return results


# ─────────────────────────────────────────────
# Post Mode
# ─────────────────────────────────────────────

async def run_posts(tasks_file: str = None, tasks: list = None):
    """Run post tasks"""
    from fb_post import post_with_schedule

    if tasks is None:
        if tasks_file and Path(tasks_file).exists():
            with open(tasks_file, encoding="utf-8") as f:
                tasks = json.load(f)
        else:
            # Default example task
            accounts = load_accounts()
            tasks = []
            for acc in accounts:
                if acc.get("status") == "active" and acc.get("profile_id"):
                    tasks.append({
                        "profile_id": acc["profile_id"],
                        "fb_uid": acc["fb_uid"],
                        "post_type": "timeline",
                        "content": "Good morning! Have a great day! {😊|🌟|👍}",
                        "images": [],
                    })

    if not tasks:
        log("[scheduler] No post tasks found")
        return

    log(f"[scheduler] Running {len(tasks)} post tasks")
    results = await post_with_schedule(tasks)
    success = sum(1 for r in results if r.get("success"))
    log(f"[scheduler] Posts done: {success}/{len(tasks)} success")
    return results


# ─────────────────────────────────────────────
# Interact Mode
# ─────────────────────────────────────────────

async def run_interact(accounts: list = None, interact_config: dict = None):
    """Run interaction session"""
    from fb_interact import interact_session
    from ix_browser import connect_playwright, disconnect_playwright

    if accounts is None:
        accounts = load_accounts()

    to_interact = [
        a for a in accounts
        if a.get("status") in ("active", "warming") and a.get("profile_id")
    ]

    if not to_interact:
        log("[scheduler] No accounts for interaction")
        return

    if interact_config is None:
        interact_config = {
            "hashtags": ["travel", "food", "technology"],
            "groups": [],
            "like_per_hashtag": 3,
            "comment_per_group": 2,
            "add_friends": 3,
        }

    log(f"[scheduler] Starting interact for {len(to_interact)} accounts")
    results = []
    for acc in to_interact:
        log(f"[scheduler] Interacting [{acc['fb_uid']}]")
        try:
            pw, browser, context, page = await connect_playwright(
                acc["profile_id"], url="https://www.facebook.com"
            )
            if not page:
                log(f"[scheduler] Browser failed for {acc['fb_uid']}")
                continue
            stats = await interact_session(page, acc["fb_uid"], interact_config)
            results.append(stats)
            await disconnect_playwright(pw, browser, acc["profile_id"])
        except Exception as e:
            log(f"[scheduler] Interact error {acc['fb_uid']}: {e}")

        await asyncio.sleep(random.uniform(30, 60))

    log(f"[scheduler] Interact complete: {len(results)} accounts done")
    return results


# ─────────────────────────────────────────────
# Login Mode
# ─────────────────────────────────────────────

async def run_login(accounts: list = None):
    """Login all accounts"""
    from fb_login import batch_login

    if accounts is None:
        all_accs = load_accounts()
        accounts = [
            a for a in all_accs
            if a.get("profile_id") and a.get("email") and a.get("password")
        ]

    if not accounts:
        log("[scheduler] No accounts with credentials to login")
        return

    log(f"[scheduler] Logging in {len(accounts)} accounts")
    results = await batch_login(accounts)
    success = sum(1 for r in results if r.get("success"))
    log(f"[scheduler] Login done: {success}/{len(accounts)} success")
    return results


# ─────────────────────────────────────────────
# Daily routine (all-in-one)
# ─────────────────────────────────────────────

async def run_daily_routine(config_file: str = None):
    """
    Run full daily routine:
    1. Login (if needed)
    2. Warmup
    3. Interact
    4. Post (if scheduled)
    """
    config = {}
    if config_file and Path(config_file).exists():
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)

    accounts = load_accounts()
    if not accounts:
        log("[scheduler] No accounts found. Add accounts first.")
        return

    log(f"[scheduler] === Daily Routine Start | {len(accounts)} accounts ===")

    # 1. Warmup (all accounts)
    warmup_hour = config.get("warmup_hour", 8)  # default 8 AM
    post_hour = config.get("post_hour", 12)     # default 12 PM
    interact_hour = config.get("interact_hour", 18)  # default 6 PM

    now_hour = datetime.now().hour
    log(f"[scheduler] Current hour: {now_hour}")

    if now_hour >= warmup_hour:
        log("[scheduler] === Running Warmup ===")
        await run_warmup(accounts)
        await asyncio.sleep(60)

    if now_hour >= post_hour:
        log("[scheduler] === Running Posts ===")
        tasks_file = config.get("post_tasks_file")
        await run_posts(tasks_file)
        await asyncio.sleep(60)

    if now_hour >= interact_hour:
        log("[scheduler] === Running Interactions ===")
        interact_cfg = config.get("interact_config")
        await run_interact(accounts, interact_cfg)

    log("[scheduler] === Daily Routine Complete ===")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Facebook Automation Scheduler")
    parser.add_argument("--mode", choices=["warmup", "post", "interact", "login", "all"],
                        default="warmup", help="Task mode")
    parser.add_argument("--config", help="Config JSON file path")
    parser.add_argument("--intensity", choices=["light", "medium", "normal"],
                        help="Warmup intensity override")
    parser.add_argument("--accounts", help="Specific account fb_uids comma separated")

    args = parser.parse_args()

    # Filter accounts if specified
    accounts = None
    if args.accounts:
        uids = [u.strip() for u in args.accounts.split(",")]
        all_accs = load_accounts()
        accounts = [a for a in all_accs if a.get("fb_uid") in uids]

    log(f"[scheduler] Mode: {args.mode}")

    if args.mode == "warmup":
        await run_warmup(accounts, intensity=args.intensity)
    elif args.mode == "post":
        await run_posts(tasks_file=args.config)
    elif args.mode == "interact":
        await run_interact(accounts)
    elif args.mode == "login":
        await run_login(accounts)
    elif args.mode == "all":
        await run_daily_routine(args.config)


if __name__ == "__main__":
    asyncio.run(main())
