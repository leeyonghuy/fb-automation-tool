"""
app.py
Web UI for Facebook Automation Tool
Run: python app.py
Open: http://localhost:5000
"""

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "fb_automation_2024"

# Store running task status
task_status = {
    "running": False,
    "task": "",
    "progress": 0,
    "logs": [],
    "last_updated": ""
}

# Task cancellation flag
_cancel_flag = {"requested": False}

# Sync mode: True = chạy song song tất cả acc, False = tuần tự từng acc
sync_mode = {"enabled": False}


def add_log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    task_status["logs"].append(entry)
    if len(task_status["logs"]) > 200:
        task_status["logs"] = task_status["logs"][-200:]
    task_status["last_updated"] = ts
    print(entry)


# ─────────────────────────────────────────────
# Routes - Dashboard
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    return jsonify(task_status)


@app.route("/api/summary")
def get_summary():
    try:
        from account_manager import get_all_accounts
        accounts = get_all_accounts()
        from collections import Counter
        status_count = Counter(a.get("status", "unknown") for a in accounts)
    except Exception:
        accounts = []
        status_count = {}

    try:
        from ix_browser import get_profiles
        profiles = get_profiles()
    except Exception:
        profiles = []

    return jsonify({
        "total_accounts": len(accounts),
        "total_profiles": len(profiles),
        "status_count": dict(status_count),
    })


# ─────────────────────────────────────────────
# Routes - Accounts
# ─────────────────────────────────────────────

@app.route("/api/accounts", methods=["GET"])
def list_accounts():
    try:
        from account_manager import get_all_accounts
        return jsonify(get_all_accounts())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/accounts/add", methods=["POST"])
def add_account():
    data = request.json
    try:
        from account_manager import add_account as _add
        acc = _add(
            fb_uid=data.get("fb_uid", ""),
            name=data.get("name", ""),
            email=data.get("email", ""),
            password=data.get("password", ""),
            two_fa_secret=data.get("two_fa_secret", ""),
            profile_id=data.get("profile_id") or None,
            note=data.get("note", ""),
        )
        return jsonify({"success": True, "account": acc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/accounts/import", methods=["POST"])
def import_accounts():
    data = request.json
    text = data.get("text", "")
    lines = text.strip().split("\n")
    try:
        from account_manager import import_accounts_from_list
        added = import_accounts_from_list(lines)
        return jsonify({"success": True, "count": len(added)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/accounts/delete/<fb_uid>", methods=["DELETE"])
def delete_account(fb_uid):
    try:
        from account_manager import delete_account as _del
        ok = _del(fb_uid)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/accounts/status/<fb_uid>", methods=["POST"])
def set_status(fb_uid):
    data = request.json
    try:
        from account_manager import set_status as _set
        ok = _set(fb_uid, data.get("status"))
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/accounts/auto-assign", methods=["POST"])
def auto_assign():
    try:
        from account_manager import auto_assign_profiles
        n = auto_assign_profiles()
        return jsonify({"success": True, "assigned": n})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# Routes - IX Browser Profiles
# ─────────────────────────────────────────────

@app.route("/api/profiles", methods=["GET"])
def list_profiles():
    try:
        from ix_browser import get_profiles
        return jsonify(get_profiles())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profiles/open/<int:profile_id>", methods=["POST"])
def open_profile(profile_id):
    try:
        from ix_browser import open_profile as _open
        result = _open(profile_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/profiles/close/<int:profile_id>", methods=["POST"])
def close_profile(profile_id):
    try:
        from ix_browser import close_profile as _close
        ok = _close(profile_id)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/profiles/close-all", methods=["POST"])
def close_all():
    try:
        from ix_browser import close_all_profiles
        close_all_profiles()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/profiles/randomize/<int:profile_id>", methods=["POST"])
def randomize_fp(profile_id):
    try:
        from ix_browser import randomize_fingerprint
        ok = randomize_fingerprint(profile_id)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# Routes - Sync Mode
# ─────────────────────────────────────────────

@app.route("/api/sync-mode", methods=["GET"])
def get_sync_mode():
    return jsonify({"enabled": sync_mode["enabled"]})


@app.route("/api/sync-mode", methods=["POST"])
def set_sync_mode():
    data = request.json or {}
    sync_mode["enabled"] = bool(data.get("enabled", False))
    mode = "SONG SONG" if sync_mode["enabled"] else "TUẦN TỰ"
    add_log(f"⚡ Sync Mode: {mode}")
    return jsonify({"enabled": sync_mode["enabled"]})


# ─────────────────────────────────────────────
# Routes - Tasks (async)
# ─────────────────────────────────────────────

def run_async(coro):
    """Run async coroutine in background thread"""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


@app.route("/api/tasks/warmup", methods=["POST"])
def task_warmup():
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}
    intensity = data.get("intensity", "light")
    uids = data.get("accounts", [])  # specific uids or empty for all

    async def _warmup():
        task_status["running"] = True
        task_status["task"] = "warmup"
        task_status["logs"] = []
        try:
            from account_manager import get_all_accounts
            from ix_browser import connect_playwright, disconnect_playwright
            from fb_warmup import warmup_session
            import asyncio as _a

            accounts = get_all_accounts()
            if uids:
                accounts = [a for a in accounts if a["fb_uid"] in uids]
            accounts = [a for a in accounts if a.get("profile_id") and a.get("status") != "die"]

            is_sync = sync_mode["enabled"]
            mode_label = "⚡ SONG SONG" if is_sync else "▶ TUẦN TỰ"
            add_log(f"Warmup {len(accounts)} acc | intensity={intensity} | {mode_label}")

            async def _do_one(acc, idx, total):
                add_log(f"[{idx+1}/{total}] Warming: {acc.get('email', acc['fb_uid'])}")
                pw, browser, ctx, page = await connect_playwright(acc["profile_id"], "https://www.facebook.com")
                if not page:
                    add_log(f"  ✗ Browser failed: {acc['fb_uid']}")
                    return
                try:
                    await warmup_session(page, acc["fb_uid"], intensity)
                    add_log(f"  ✓ Done: {acc.get('email', acc['fb_uid'])}")
                except Exception as e:
                    add_log(f"  ✗ Error: {e}")
                finally:
                    await disconnect_playwright(pw, browser, acc["profile_id"])

            if is_sync:
                # Song song: chạy tất cả cùng lúc
                add_log(f"Mở {len(accounts)} profile cùng lúc...")
                await _a.gather(*[_do_one(acc, i, len(accounts)) for i, acc in enumerate(accounts)])
            else:
                # Tuần tự: từng acc một
                for i, acc in enumerate(accounts):
                    task_status["progress"] = int((i / len(accounts)) * 100)
                    await _do_one(acc, i, len(accounts))
                    await _a.sleep(30)

            task_status["progress"] = 100
            add_log("✅ Warmup complete!")
        except Exception as e:
            add_log(f"Task error: {e}")
        finally:
            task_status["running"] = False

    run_async(_warmup())
    return jsonify({"success": True, "message": "Warmup started"})


@app.route("/api/tasks/post", methods=["POST"])
def task_post():
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}

    async def _post():
        task_status["running"] = True
        task_status["task"] = "post"
        task_status["logs"] = []
        try:
            from fb_post import post_with_schedule
            tasks = data.get("tasks", [])
            if not tasks:
                # Build tasks from active accounts
                from account_manager import get_accounts_ready
                accs = get_accounts_ready()
                content = data.get("content", "Hello everyone! {😊|🌟|👍}")
                post_type = data.get("post_type", "timeline")
                target_url = data.get("target_url", "")
                tasks = [
                    {
                        "profile_id": a["profile_id"],
                        "fb_uid": a["fb_uid"],
                        "post_type": post_type,
                        "content": content,
                        "target_url": target_url,
                        "images": [],
                    }
                    for a in accs
                ]
            add_log(f"Posting to {len(tasks)} accounts")
            results = await post_with_schedule(tasks)
            ok = sum(1 for r in results if r.get("success"))
            add_log(f"Done: {ok}/{len(results)} posted successfully")
            task_status["progress"] = 100
        except Exception as e:
            add_log(f"Task error: {e}")
        finally:
            task_status["running"] = False

    run_async(_post())
    return jsonify({"success": True, "message": "Post task started"})


@app.route("/api/tasks/interact", methods=["POST"])
def task_interact():
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}

    async def _interact():
        task_status["running"] = True
        task_status["task"] = "interact"
        task_status["logs"] = []
        try:
            from scheduler import run_interact
            interact_cfg = {
                "hashtags": data.get("hashtags", ["travel", "food"]),
                "groups": data.get("groups", []),
                "like_per_hashtag": int(data.get("like_per_hashtag", 3)),
                "comment_per_group": int(data.get("comment_per_group", 2)),
                "add_friends": int(data.get("add_friends", 3)),
            }
            add_log(f"Starting interactions | config: {interact_cfg}")
            await run_interact(interact_config=interact_cfg)
            task_status["progress"] = 100
            add_log("Interactions complete!")
        except Exception as e:
            add_log(f"Task error: {e}")
        finally:
            task_status["running"] = False

    run_async(_interact())
    return jsonify({"success": True, "message": "Interact task started"})


@app.route("/api/tasks/login", methods=["POST"])
def task_login():
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})

    async def _login():
        task_status["running"] = True
        task_status["task"] = "login"
        task_status["logs"] = []
        try:
            from scheduler import run_login
            add_log("Starting batch login...")
            results = await run_login()
            if results:
                ok = sum(1 for r in results if r.get("success"))
                add_log(f"Login done: {ok}/{len(results)} success")
            task_status["progress"] = 100
        except Exception as e:
            add_log(f"Task error: {e}")
        finally:
            task_status["running"] = False

    run_async(_login())
    return jsonify({"success": True, "message": "Login task started"})


@app.route("/api/tasks/stop", methods=["POST"])
def stop_task():
    _cancel_flag["requested"] = True
    task_status["running"] = False
    add_log("⛔ Task stopped by user")
    return jsonify({"success": True})


@app.route("/api/tasks/cancel-status", methods=["GET"])
def cancel_status():
    return jsonify({"cancel_requested": _cancel_flag["requested"]})


# ─────────────────────────────────────────────
# Routes - Groups
# ─────────────────────────────────────────────

@app.route("/api/groups", methods=["GET"])
def list_groups():
    try:
        from account_manager import get_group_summary
        return jsonify(get_group_summary())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/groups/auto-assign", methods=["POST"])
def auto_assign_groups():
    data = request.json or {}
    group_size = int(data.get("group_size", 5))
    try:
        from account_manager import auto_assign_groups as _fn
        changed = _fn(group_size)
        return jsonify({"success": True, "changed": changed, "group_size": group_size})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/groups/set-account", methods=["POST"])
def set_account_group():
    data = request.json or {}
    fb_uid = data.get("fb_uid")
    group = int(data.get("group", 1))
    try:
        from account_manager import set_group
        ok = set_group(fb_uid, group)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/run-group", methods=["POST"])
def run_group_task():
    """Run a task (warmup/interact/post/login) for one or more groups sequentially"""
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}
    task_type = data.get("task_type", "warmup")   # warmup | interact | post | login
    groups = data.get("groups", [])                # [] = all groups
    delay_between_groups = int(data.get("delay_between_groups", 60))
    # task-specific params
    task_params = data.get("params", {})

    async def _run():
        task_status["running"] = True
        task_status["task"] = task_type
        task_status["logs"] = []
        task_status["progress"] = 0
        try:
            from account_manager import get_group_summary, get_accounts_by_group
            from ix_browser import open_profile, close_profile

            summary = get_group_summary()
            if groups:
                selected_groups = [g for g in summary if g["group"] in groups]
            else:
                selected_groups = summary

            total_groups = len(selected_groups)
            add_log(f"Starting '{task_type}' for {total_groups} group(s)")

            for gi, grp_info in enumerate(selected_groups):
                grp_num = grp_info["group"]
                accounts = get_accounts_by_group(grp_num)
                add_log(f"")
                add_log(f"{'='*40}")
                add_log(f"  NHÓM {grp_num} — {len(accounts)} tài khoản")
                add_log(f"{'='*40}")

                # Open profiles
                add_log(f"Đang mở {len(accounts)} profile...")
                for acc in accounts:
                    if acc.get("profile_id"):
                        try:
                            open_profile(acc["profile_id"])
                            add_log(f"  ✓ Mở profile {acc['profile_id']} ({acc.get('email','')})")
                        except Exception as e:
                            add_log(f"  ✗ Profile {acc['profile_id']}: {e}")
                import asyncio as _a
                await _a.sleep(5)  # Wait browsers to load

                # Run task
                try:
                    if task_type == "warmup":
                        from ix_browser import connect_playwright, disconnect_playwright
                        from fb_warmup import warmup_session
                        intensity = task_params.get("intensity", "light")
                        for acc in accounts:
                            if not acc.get("profile_id"):
                                continue
                            add_log(f"Warming: {acc.get('email','')}")
                            pw, browser, ctx, page = await connect_playwright(acc["profile_id"], "https://www.facebook.com")
                            if page:
                                try:
                                    await warmup_session(page, acc["fb_uid"], intensity)
                                    add_log(f"  ✓ Done")
                                except Exception as e:
                                    add_log(f"  ✗ {e}")
                                finally:
                                    await disconnect_playwright(pw, browser, acc["profile_id"])
                            await _a.sleep(10)

                    elif task_type == "interact":
                        from ix_browser import connect_playwright, disconnect_playwright
                        from fb_interact import run_interactions
                        for acc in accounts:
                            if not acc.get("profile_id"):
                                continue
                            add_log(f"Interacting: {acc.get('email','')}")
                            pw, browser, ctx, page = await connect_playwright(acc["profile_id"], "https://www.facebook.com")
                            if page:
                                try:
                                    await run_interactions(page, acc["fb_uid"], task_params)
                                    add_log(f"  ✓ Done")
                                except Exception as e:
                                    add_log(f"  ✗ {e}")
                                finally:
                                    await disconnect_playwright(pw, browser, acc["profile_id"])
                            await _a.sleep(10)

                    elif task_type == "login":
                        from ix_browser import connect_playwright, disconnect_playwright
                        from fb_login import login_by_password
                        from account_manager import update_account
                        ok_count = 0
                        for acc in accounts:
                            if not acc.get("profile_id"):
                                continue
                            add_log(f"Login: {acc.get('email','')}")
                            pw, browser, ctx, page = await connect_playwright(acc["profile_id"], "https://www.facebook.com")
                            if page:
                                try:
                                    r = await login_by_password(page, acc["email"], acc["password"], acc.get("two_fa_secret", ""))
                                    if r.get("success"):
                                        ok_count += 1
                                        add_log(f"  ✓ Login OK")
                                        update_account(acc["fb_uid"], status="warming", last_login=datetime.now().isoformat())
                                    else:
                                        add_log(f"  ✗ {r.get('error','')}")
                                except Exception as e:
                                    add_log(f"  ✗ {e}")
                                finally:
                                    await disconnect_playwright(pw, browser, acc["profile_id"])
                            await _a.sleep(15)
                        add_log(f"Login group {grp_num}: {ok_count}/{len(accounts)} OK")

                except Exception as e:
                    add_log(f"Task error in group {grp_num}: {e}")

                # Close profiles
                add_log(f"Đang đóng profile nhóm {grp_num}...")
                for acc in accounts:
                    if acc.get("profile_id"):
                        try:
                            close_profile(acc["profile_id"])
                        except Exception:
                            pass
                add_log(f"✓ Nhóm {grp_num} xong!")

                task_status["progress"] = int(((gi + 1) / total_groups) * 100)

                # Delay before next group
                if gi < total_groups - 1:
                    add_log(f"Nghỉ {delay_between_groups}s trước nhóm tiếp theo...")
                    await _a.sleep(delay_between_groups)

            task_status["progress"] = 100
            add_log(f"✅ Hoàn tất tất cả {total_groups} nhóm!")
        except Exception as e:
            add_log(f"Fatal error: {e}")
        finally:
            task_status["running"] = False

    run_async(_run())
    return jsonify({"success": True, "message": f"Group task '{task_type}' started"})


# ─────────────────────────────────────────────
# Routes - Proxy
# ─────────────────────────────────────────────

PROXY_FILE = Path(__file__).parent / "proxies.txt"


@app.route("/api/proxies", methods=["GET"])
def list_proxies():
    try:
        from proxy_manager import load_proxies
        proxies = load_proxies()
        return jsonify(proxies)
    except Exception:
        # Fallback: read file directly
        lines = []
        if PROXY_FILE.exists():
            with open(PROXY_FILE, encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        return jsonify([{"raw": l} for l in lines])


@app.route("/api/proxies/save", methods=["POST"])
def save_proxies():
    data = request.json
    text = data.get("text", "")
    try:
        with open(PROXY_FILE, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
        lines = [l for l in text.strip().split("\n") if l.strip()]
        return jsonify({"success": True, "count": len(lines)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/proxies/test", methods=["POST"])
def test_proxy():
    data = request.json
    proxy = data.get("proxy", "")
    try:
        import requests as req
        proxies = {"http": proxy, "https": proxy}
        r = req.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
        ip = r.json().get("ip", "?")
        return jsonify({"success": True, "ip": ip})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─────────────────────────────────────────────
# Routes - Login
# ─────────────────────────────────────────────

@app.route("/api/tasks/login-batch", methods=["POST"])
def task_login_batch():
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}

    async def _login():
        task_status["running"] = True
        task_status["task"] = "login"
        task_status["logs"] = []
        try:
            from account_manager import get_all_accounts
            from ix_browser import connect_playwright, disconnect_playwright
            from fb_login import login_by_password

            accounts = get_all_accounts()
            uids = data.get("accounts", [])
            if uids:
                accounts = [a for a in accounts if a["fb_uid"] in uids]
            else:
                accounts = [a for a in accounts if a.get("profile_id") and a.get("status") in ("new", "warming", "active")]

            add_log(f"Batch login for {len(accounts)} accounts")
            ok_count = 0
            for i, acc in enumerate(accounts):
                task_status["progress"] = int((i / max(len(accounts), 1)) * 100)
                add_log(f"[{i+1}/{len(accounts)}] Login: {acc.get('email','')}")
                pw, browser, ctx, page = await connect_playwright(acc["profile_id"], "https://www.facebook.com")
                if not page:
                    add_log(f"  ✗ Browser failed")
                    continue
                try:
                    result = await login_by_password(page, acc["email"], acc["password"], acc.get("two_fa_secret", ""))
                    if result.get("success"):
                        ok_count += 1
                        add_log(f"  ✓ Login OK")
                        from account_manager import update_account
                        update_account(acc["fb_uid"], status="warming", last_login=datetime.now().isoformat())
                    else:
                        add_log(f"  ✗ {result.get('error','Failed')}")
                except Exception as e:
                    add_log(f"  ✗ Error: {e}")
                finally:
                    await disconnect_playwright(pw, browser, acc["profile_id"])
                import asyncio as _a
                await _a.sleep(15)
            task_status["progress"] = 100
            add_log(f"Login done: {ok_count}/{len(accounts)} success")
        except Exception as e:
            add_log(f"Task error: {e}")
        finally:
            task_status["running"] = False

    run_async(_login())
    return jsonify({"success": True, "message": "Login batch started"})


# ─────────────────────────────────────────────
# Routes - Fanpage
# ─────────────────────────────────────────────

@app.route("/api/pages", methods=["GET"])
def list_pages():
    try:
        from fb_page import get_all_pages
        return jsonify(get_all_pages())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pages/add", methods=["POST"])
def add_page():
    data = request.json or {}
    try:
        from fb_page import add_page_record
        record = add_page_record(
            owner_uid=data.get("owner_uid", ""),
            page_name=data.get("page_name", ""),
            page_url=data.get("page_url", ""),
            page_id=data.get("page_id", ""),
            category=data.get("category", "public_figure"),
            description=data.get("description", ""),
        )
        return jsonify({"success": True, "record": record})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pages/delete/<page_id>", methods=["DELETE"])
def delete_page(page_id):
    try:
        from fb_page import delete_page_record
        ok = delete_page_record(page_id)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pages/create", methods=["POST"])
def create_page_task():
    """Tự động tạo fanpage qua IX Browser"""
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}

    async def _run():
        task_status["running"] = True
        task_status["task"] = "create_page"
        task_status["logs"] = []
        task_status["progress"] = 0
        try:
            from ix_browser import connect_playwright, disconnect_playwright
            from fb_page import create_fanpage
            from account_manager import get_account

            tasks = data.get("tasks", [])
            if not tasks:
                # Build single task
                tasks = [{
                    "profile_id": data.get("profile_id"),
                    "owner_uid": data.get("owner_uid", ""),
                    "page_name": data.get("page_name", ""),
                    "category": data.get("category", "public_figure"),
                    "description": data.get("description", ""),
                    "avatar_path": data.get("avatar_path", ""),
                    "cover_path": data.get("cover_path", ""),
                }]

            add_log(f"Tạo {len(tasks)} fanpage...")
            for i, task in enumerate(tasks):
                task_status["progress"] = int((i / len(tasks)) * 100)
                add_log(f"[{i+1}/{len(tasks)}] Tạo page: {task.get('page_name')}")
                profile_id = task.get("profile_id")
                if not profile_id:
                    add_log(f"  ✗ Thiếu profile_id"); continue
                pw, browser, ctx, playwright_page = await connect_playwright(profile_id, "https://www.facebook.com")
                if not playwright_page:
                    add_log(f"  ✗ Browser lỗi"); continue
                try:
                    r = await create_fanpage(playwright_page, **{k: v for k, v in task.items() if k != "profile_id"})
                    if r["success"]:
                        add_log(f"  ✓ Page tạo OK: {r.get('page_url','')}")
                    else:
                        add_log(f"  ✗ {r.get('error','')}")
                finally:
                    await disconnect_playwright(pw, browser, profile_id)
                import asyncio as _a; await _a.sleep(30)

            task_status["progress"] = 100
            add_log("✅ Hoàn tất tạo page!")
        except Exception as e:
            add_log(f"Fatal: {e}")
        finally:
            task_status["running"] = False

    run_async(_run())
    return jsonify({"success": True, "message": "Đang tạo fanpage..."})


@app.route("/api/pages/add-editor", methods=["POST"])
def add_editor_task():
    """Add Editor/Admin vào page qua IX Browser"""
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}

    async def _run():
        task_status["running"] = True
        task_status["task"] = "add_editor"
        task_status["logs"] = []
        task_status["progress"] = 0
        try:
            from ix_browser import connect_playwright, disconnect_playwright
            from fb_page_editor import add_page_editor

            tasks = data.get("tasks", [])
            if not tasks:
                tasks = [{
                    "profile_id": data.get("profile_id"),
                    "page_url": data.get("page_url", ""),
                    "editor_email": data.get("editor_email", ""),
                    "role": data.get("role", "editor"),
                }]

            add_log(f"Add editor cho {len(tasks)} page...")
            for i, task in enumerate(tasks):
                task_status["progress"] = int((i / len(tasks)) * 100)
                add_log(f"[{i+1}/{len(tasks)}] {task.get('page_url')} ← {task.get('editor_email')} ({task.get('role')})")
                pw, browser, ctx, playwright_page = await connect_playwright(
                    task["profile_id"], task.get("page_url", "https://www.facebook.com"))
                if not playwright_page:
                    add_log(f"  ✗ Browser lỗi"); continue
                try:
                    r = await add_page_editor(playwright_page, task["page_url"],
                                               task["editor_email"], task.get("role", "editor"))
                    add_log(f"  {'✓' if r['success'] else '✗'} {r.get('error','OK')}")
                finally:
                    await disconnect_playwright(pw, browser, task["profile_id"])
                import asyncio as _a; await _a.sleep(15)

            task_status["progress"] = 100
            add_log("✅ Hoàn tất add editor!")
        except Exception as e:
            add_log(f"Fatal: {e}")
        finally:
            task_status["running"] = False

    run_async(_run())
    return jsonify({"success": True, "message": "Đang add editor..."})


@app.route("/api/pages/post", methods=["POST"])
def page_post_task():
    """Đăng bài/Reel lên page"""
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}
    post_type = data.get("post_type", "post")  # post | reel

    async def _run():
        task_status["running"] = True
        task_status["task"] = f"page_{post_type}"
        task_status["logs"] = []
        task_status["progress"] = 0
        try:
            from ix_browser import connect_playwright, disconnect_playwright
            from fb_page_post import post_to_page, post_reel_to_page
            from fb_page import get_all_pages

            tasks = data.get("tasks", [])
            if not tasks:
                # Build from selected pages or all active pages
                selected_pages = data.get("selected_pages", [])
                pages = get_all_pages()
                if selected_pages:
                    pages = [p for p in pages if p["page_id"] in selected_pages]
                else:
                    pages = [p for p in pages if p.get("status") == "active"]
                from account_manager import get_account
                for p in pages:
                    acc = get_account(p["owner_uid"])
                    if acc and acc.get("profile_id"):
                        tasks.append({
                            "profile_id": acc["profile_id"],
                            "page_url": p["page_url"],
                            "content": data.get("content", ""),
                            "video_path": data.get("video_path", ""),
                            "caption": data.get("caption", ""),
                            "images": data.get("images", []),
                        })

            add_log(f"Đăng {post_type} lên {len(tasks)} page...")
            ok = 0
            for i, task in enumerate(tasks):
                task_status["progress"] = int((i / max(len(tasks), 1)) * 100)
                add_log(f"[{i+1}/{len(tasks)}] {task.get('page_url')}")
                pw, browser, ctx, playwright_page = await connect_playwright(
                    task["profile_id"], task.get("page_url", "https://www.facebook.com"))
                if not playwright_page:
                    add_log(f"  ✗ Browser lỗi"); continue
                try:
                    if post_type == "reel":
                        r = await post_reel_to_page(playwright_page, task["page_url"],
                                                     task.get("video_path", ""), task.get("caption", ""))
                    else:
                        r = await post_to_page(playwright_page, task["page_url"],
                                                task.get("content", ""), task.get("images", []))
                    if r["success"]:
                        ok += 1; add_log(f"  ✓ OK")
                    else:
                        add_log(f"  ✗ {r.get('error','')}")
                finally:
                    await disconnect_playwright(pw, browser, task["profile_id"])
                import asyncio as _a; await _a.sleep(20)

            task_status["progress"] = 100
            add_log(f"✅ Hoàn tất: {ok}/{len(tasks)} page đã đăng!")
        except Exception as e:
            add_log(f"Fatal: {e}")
        finally:
            task_status["running"] = False

    run_async(_run())
    return jsonify({"success": True, "message": f"Đang đăng {post_type}..."})


# ─────────────────────────────────────────────
# Routes - Publish Queue
# ─────────────────────────────────────────────

@app.route("/api/queue", methods=["GET"])
def get_queue():
    """Lấy danh sách hàng đợi đăng bài"""
    try:
        from publish_queue import get_pending_items, get_all_items
        all_items = get_all_items()
        return jsonify(all_items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/queue/add", methods=["POST"])
def add_to_queue():
    """Thêm item vào hàng đợi"""
    data = request.json or {}
    try:
        from publish_queue import add_item
        item = add_item(
            page_url=data.get("page_url", ""),
            video_path=data.get("video_path", ""),
            caption=data.get("caption", ""),
            post_type=data.get("post_type", "reel"),
            profile_id=data.get("profile_id"),
            scheduled_at=data.get("scheduled_at", ""),
            owner_uid=data.get("owner_uid", ""),
        )
        return jsonify({"success": True, "item": item})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/queue/delete/<item_id>", methods=["DELETE"])
def delete_queue_item(item_id):
    """Xóa item khỏi hàng đợi"""
    try:
        from publish_queue import delete_item
        ok = delete_item(item_id)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/queue/run", methods=["POST"])
def run_queue():
    """Chạy hàng đợi đăng bài ngay"""
    if task_status["running"]:
        return jsonify({"success": False, "error": "A task is already running"})
    data = request.json or {}
    limit = int(data.get("limit", 10))

    async def _run():
        task_status["running"] = True
        task_status["task"] = "publish_queue"
        task_status["logs"] = []
        task_status["progress"] = 0
        _cancel_flag["requested"] = False
        try:
            from publish_queue import get_pending_items, mark_done, mark_failed
            from ix_browser import connect_playwright, disconnect_playwright
            from fb_page_post import post_to_page, post_reel_to_page
            import asyncio as _a

            items = get_pending_items(limit=limit)
            add_log(f"📋 Publish queue: {len(items)} item(s) pending")

            for i, item in enumerate(items):
                if _cancel_flag["requested"]:
                    add_log("⛔ Queue cancelled by user")
                    break

                task_status["progress"] = int((i / max(len(items), 1)) * 100)
                page_url = item.get("page_url", "")
                post_type = item.get("post_type", "reel")
                profile_id = item.get("profile_id")
                item_id = item.get("id", "")

                add_log(f"[{i+1}/{len(items)}] {post_type} → {page_url}")

                if not profile_id:
                    add_log(f"  ✗ Thiếu profile_id")
                    mark_failed(item_id, "missing profile_id")
                    continue

                pw, browser, ctx, playwright_page = await connect_playwright(
                    profile_id, page_url or "https://www.facebook.com")
                if not playwright_page:
                    add_log(f"  ✗ Browser lỗi")
                    mark_failed(item_id, "browser_failed")
                    continue

                try:
                    if post_type == "reel":
                        r = await post_reel_to_page(
                            playwright_page, page_url,
                            item.get("video_path", ""),
                            item.get("caption", ""))
                    else:
                        r = await post_to_page(
                            playwright_page, page_url,
                            item.get("caption", item.get("content", "")),
                            item.get("images", []))

                    if r.get("success"):
                        mark_done(item_id)
                        add_log(f"  ✓ Đăng thành công")
                    elif r.get("skipped"):
                        mark_done(item_id, note="skipped_dedup")
                        add_log(f"  ⚠ Bỏ qua (dedup)")
                    else:
                        mark_failed(item_id, r.get("error", "unknown"))
                        add_log(f"  ✗ {r.get('error','')}")
                except Exception as e:
                    mark_failed(item_id, str(e))
                    add_log(f"  ✗ Exception: {e}")
                finally:
                    await disconnect_playwright(pw, browser, profile_id)

                await _a.sleep(20)

            task_status["progress"] = 100
            add_log("✅ Publish queue done!")
        except Exception as e:
            add_log(f"Fatal: {e}")
        finally:
            task_status["running"] = False

    run_async(_run())
    return jsonify({"success": True, "message": "Publish queue started"})


# ─────────────────────────────────────────────
# Logs
# ─────────────────────────────────────────────

@app.route("/api/logs", methods=["GET"])
def get_logs():
    log_file = Path(__file__).parent / "scheduler.log"
    lines = []
    if log_file.exists():
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()[-100:]
    return jsonify({"logs": [l.strip() for l in lines]})


if __name__ == "__main__":
    print("=" * 50)
    print("  Facebook Automation Tool")
    print("  URL: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
