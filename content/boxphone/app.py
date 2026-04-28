"""
app.py
Web UI quản lý BoxPhone TikTok - chạy tại http://localhost:5001
"""

import os
import sys
import threading
import json
import time
import io
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response

# Thêm thư mục hiện tại vào path
sys.path.insert(0, os.path.dirname(__file__))

from adb_manager import get_devices, get_device_info, start_scrcpy, start_scrcpy_all, check_adb_installed
from device_manager import (
    sync_devices, get_all_devices, get_all_accounts, get_paired_list,
    add_account, update_account, remove_account, assign_account_to_device,
    update_device, remove_device, import_accounts_csv
)
from tiktok_login import login_with_email, is_logged_in
from tiktok_post import upload_video_full, batch_upload
from proxy_manager import (
    add_proxy, get_all_proxies, get_proxy, update_proxy, remove_proxy,
    assign_proxy_to_device, get_proxy_for_device, import_proxies_from_text,
    check_proxy, set_proxy_on_device, remove_proxy_from_device, get_device_current_ip
)
from tiktok_warmup import (
    start_warmup_async, stop_warmup, get_warmup_status, batch_warmup
)
from scheduler import (
    add_schedule, get_all_schedules, get_schedule, update_schedule,
    remove_schedule, cancel_schedule, get_scheduler_status,
    start_scheduler
)
from content_manager import (
    add_content, get_all_content, get_content, update_content, remove_content,
    import_content_from_folder, get_content_stats,
    create_campaign, get_all_campaigns, get_campaign, update_campaign,
    remove_campaign, run_campaign_post
)
from app_manager import (
    get_installed_apps, install_apk, batch_install_apk,
    uninstall_app, batch_uninstall_app,
    force_stop_app, clear_app_data, batch_force_stop, batch_clear_data,
    open_app as app_open, batch_open_app,
    reboot_device, batch_reboot, wake_screen, lock_screen,
    batch_wake, batch_lock,
    get_battery_info, get_all_battery_info,
    set_volume, set_brightness, set_screen_timeout, batch_set_screen_timeout,
    get_device_storage, push_file_to_all,
    run_shell_command, batch_shell_command, batch_input_text
)

app = Flask(__name__)

# Khởi động scheduler khi app start
start_scheduler()

# ─── TASK TRACKING ────────────────────────────────────────────────────────────
running_tasks = {}  # {task_id: {"status": ..., "results": [...], "thread": ...}}
task_counter = 0


def new_task_id():
    global task_counter
    task_counter += 1
    return f"task_{task_counter:04d}"


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("boxphone_index.html")


@app.route("/api/devices", methods=["GET"])
def api_devices():
    """Lấy danh sách thiết bị + trạng thái ADB"""
    try:
        devices = sync_devices()
        # Merge với thông tin ADB live
        adb_devices = {d["serial"]: d["status"] for d in get_devices()}
        for d in devices:
            d["adb_status"] = adb_devices.get(d["serial"], "offline")
        return jsonify({"success": True, "devices": devices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/devices/sync", methods=["POST"])
def api_sync_devices():
    """Đồng bộ thiết bị từ ADB"""
    try:
        devices = sync_devices()
        return jsonify({"success": True, "devices": devices, "count": len(devices)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/devices/<serial>/info", methods=["GET"])
def api_device_info(serial):
    """Lấy thông tin chi tiết thiết bị"""
    try:
        info = get_device_info(serial)
        return jsonify({"success": True, "info": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/devices/<serial>/mirror", methods=["POST"])
def api_mirror(serial):
    """Mở scrcpy mirror cho thiết bị"""
    try:
        ok = start_scrcpy(serial, window_title=f"BoxPhone - {serial}")
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/devices/mirror_all", methods=["POST"])
def api_mirror_all():
    """Mở scrcpy cho tất cả thiết bị"""
    try:
        results = start_scrcpy_all()
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/devices/<serial>/assign", methods=["POST"])
def api_assign_account(serial):
    """Gán tài khoản cho thiết bị"""
    data = request.json
    account_id = data.get("account_id")
    if not account_id:
        return jsonify({"success": False, "error": "Missing account_id"})
    ok = assign_account_to_device(serial, account_id)
    return jsonify({"success": ok})


@app.route("/api/devices/<serial>", methods=["DELETE"])
def api_remove_device(serial):
    ok = remove_device(serial)
    return jsonify({"success": ok})


# ─── ACCOUNTS ─────────────────────────────────────────────────────────────────

@app.route("/api/accounts", methods=["GET"])
def api_accounts():
    accounts = get_all_accounts()
    # Ẩn password trong response
    safe = [{**a, "password": "***"} for a in accounts]
    return jsonify({"success": True, "accounts": safe})


@app.route("/api/accounts", methods=["POST"])
def api_add_account():
    data = request.json
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    serial = data.get("serial", "").strip() or None
    note = data.get("note", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email và password không được trống"})

    acc = add_account(email, password, serial, note)
    return jsonify({"success": True, "account": {**acc, "password": "***"}})


@app.route("/api/accounts/<account_id>", methods=["PUT"])
def api_update_account(account_id):
    data = request.json
    ok = update_account(account_id, **data)
    return jsonify({"success": ok})


@app.route("/api/accounts/<account_id>", methods=["DELETE"])
def api_remove_account(account_id):
    ok = remove_account(account_id)
    return jsonify({"success": ok})


@app.route("/api/accounts/import", methods=["POST"])
def api_import_accounts():
    """Import tài khoản từ CSV upload"""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file"})
    f = request.files["file"]
    tmp_path = os.path.join(os.path.dirname(__file__), "tmp_import.csv")
    f.save(tmp_path)
    try:
        count = import_accounts_csv(tmp_path)
        os.remove(tmp_path)
        return jsonify({"success": True, "imported": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── PAIRED LIST ──────────────────────────────────────────────────────────────

@app.route("/api/paired", methods=["GET"])
def api_paired():
    """Lấy danh sách thiết bị + tài khoản đã ghép cặp"""
    pairs = get_paired_list()
    return jsonify({"success": True, "pairs": pairs})


# ─── LOGIN TASKS ──────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    """Đăng nhập TikTok cho một thiết bị"""
    data = request.json
    serial = data.get("serial")
    email = data.get("email")
    password = data.get("password")

    if not all([serial, email, password]):
        return jsonify({"success": False, "error": "Thiếu thông tin"})

    task_id = new_task_id()
    running_tasks[task_id] = {"status": "running", "results": []}

    def run():
        result = login_with_email(serial, email, password)
        running_tasks[task_id]["results"] = [result]
        running_tasks[task_id]["status"] = "done"

    t = threading.Thread(target=run, daemon=True)
    running_tasks[task_id]["thread"] = t
    t.start()

    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/login/batch", methods=["POST"])
def api_login_batch():
    """Đăng nhập hàng loạt"""
    data = request.json
    accounts = data.get("accounts", [])  # [{"serial": ..., "email": ..., "password": ...}]

    if not accounts:
        return jsonify({"success": False, "error": "Danh sách tài khoản trống"})

    task_id = new_task_id()
    running_tasks[task_id] = {"status": "running", "results": [], "total": len(accounts)}

    def run():
        import asyncio
        from tiktok_login import batch_login
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(batch_login(accounts))
        loop.close()
        running_tasks[task_id]["results"] = results
        running_tasks[task_id]["status"] = "done"

    t = threading.Thread(target=run, daemon=True)
    running_tasks[task_id]["thread"] = t
    t.start()

    return jsonify({"success": True, "task_id": task_id})


# ─── UPLOAD TASKS ─────────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload video cho một thiết bị"""
    data = request.json
    serial = data.get("serial")
    video_path = data.get("video_path")
    caption = data.get("caption", "")
    hashtags = data.get("hashtags", [])
    product_name = data.get("product_name")
    product_link = data.get("product_link")

    if not serial or not video_path:
        return jsonify({"success": False, "error": "Thiếu serial hoặc video_path"})

    task_id = new_task_id()
    running_tasks[task_id] = {"status": "running", "results": []}

    def run():
        result = upload_video_full(serial, video_path, caption, hashtags,
                                   product_name, product_link)
        running_tasks[task_id]["results"] = [result]
        running_tasks[task_id]["status"] = "done"

    t = threading.Thread(target=run, daemon=True)
    running_tasks[task_id]["thread"] = t
    t.start()

    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/upload/batch", methods=["POST"])
def api_upload_batch():
    """Upload hàng loạt"""
    data = request.json
    tasks = data.get("tasks", [])

    if not tasks:
        return jsonify({"success": False, "error": "Danh sách task trống"})

    task_id = new_task_id()
    running_tasks[task_id] = {"status": "running", "results": [], "total": len(tasks)}

    def run():
        results = batch_upload(tasks)
        running_tasks[task_id]["results"] = results
        running_tasks[task_id]["status"] = "done"

    t = threading.Thread(target=run, daemon=True)
    running_tasks[task_id]["thread"] = t
    t.start()

    return jsonify({"success": True, "task_id": task_id})


# ─── TASK STATUS ──────────────────────────────────────────────────────────────

@app.route("/api/tasks/<task_id>", methods=["GET"])
def api_task_status(task_id):
    """Kiểm tra trạng thái task"""
    task = running_tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"})
    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task["status"],
        "results": task.get("results", []),
        "total": task.get("total", 1)
    })


@app.route("/api/tasks", methods=["GET"])
def api_all_tasks():
    """Lấy tất cả tasks"""
    result = []
    for tid, task in running_tasks.items():
        result.append({
            "task_id": tid,
            "status": task["status"],
            "result_count": len(task.get("results", [])),
            "total": task.get("total", 1)
        })
    return jsonify({"success": True, "tasks": result})


# ─── SCREENSHOT & STREAM ──────────────────────────────────────────────────────

@app.route("/api/devices/<serial>/screenshot")
def api_screenshot(serial):
    """Chụp màn hình thiết bị, trả về JPEG"""
    try:
        from adb_manager import run_adb
        import base64
        # Dùng ADB screencap
        stdout, stderr, code = run_adb(["exec-out", "screencap", "-p"], serial, timeout=10)
        if code != 0 or not stdout:
            # Fallback: screencap ra file rồi pull
            run_adb(["shell", "screencap", "-p", "/sdcard/screen_tmp.png"], serial, timeout=10)
            import subprocess, tempfile
            tmp = tempfile.mktemp(suffix=".png")
            adb_path = r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else "adb"
            r2 = subprocess.run([adb_path, "-s", serial, "pull", "/sdcard/screen_tmp.png", tmp],
                                capture_output=True, timeout=15)
            if r2.returncode == 0 and os.path.exists(tmp):
                with open(tmp, "rb") as f:
                    img_bytes = f.read()
                os.remove(tmp)
                return Response(img_bytes, mimetype="image/png",
                                headers={"Cache-Control": "no-cache"})
            return jsonify({"success": False, "error": "Screenshot failed"}), 500

        # stdout là binary PNG từ exec-out
        img_bytes = stdout.encode("latin-1") if isinstance(stdout, str) else stdout
        return Response(img_bytes, mimetype="image/png",
                        headers={"Cache-Control": "no-cache"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/devices/<serial>/screenshot_b64")
def api_screenshot_b64(serial):
    """Chụp màn hình, trả về base64 JSON (dùng cho polling JS)"""
    try:
        import subprocess, tempfile, base64
        adb_path = r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else "adb"
        tmp = tempfile.mktemp(suffix=".png")
        # screencap trực tiếp ra file local qua exec-out
        with open(tmp, "wb") as f:
            r = subprocess.run([adb_path, "-s", serial, "exec-out", "screencap", "-p"],
                               stdout=f, stderr=subprocess.PIPE, timeout=10)
        if r.returncode == 0 and os.path.getsize(tmp) > 1000:
            with open(tmp, "rb") as f:
                img_bytes = f.read()
            os.remove(tmp)
            b64 = base64.b64encode(img_bytes).decode()
            return jsonify({"success": True, "image": b64, "mime": "image/png"})
        # Fallback: pull từ sdcard
        subprocess.run([adb_path, "-s", serial, "shell", "screencap", "-p", "/sdcard/_sc.png"],
                       capture_output=True, timeout=10)
        r2 = subprocess.run([adb_path, "-s", serial, "pull", "/sdcard/_sc.png", tmp],
                            capture_output=True, timeout=15)
        if r2.returncode == 0 and os.path.exists(tmp):
            with open(tmp, "rb") as f:
                img_bytes = f.read()
            os.remove(tmp)
            b64 = base64.b64encode(img_bytes).decode()
            return jsonify({"success": True, "image": b64, "mime": "image/png"})
        return jsonify({"success": False, "error": "Screenshot failed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/devices/<serial>/stream")
def api_stream(serial):
    """MJPEG stream màn hình thiết bị"""
    def generate():
        import subprocess, tempfile
        adb_path = r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else "adb"
        while True:
            try:
                tmp = tempfile.mktemp(suffix=".png")
                with open(tmp, "wb") as f:
                    r = subprocess.run([adb_path, "-s", serial, "exec-out", "screencap", "-p"],
                                       stdout=f, stderr=subprocess.PIPE, timeout=8)
                if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
                    with open(tmp, "rb") as f:
                        frame = f.read()
                    os.remove(tmp)
                    yield (b"--frame\r\n"
                           b"Content-Type: image/png\r\n\r\n" + frame + b"\r\n")
                else:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                time.sleep(0.5)
            except Exception:
                time.sleep(1)
                break

    return Response(generate(),
                    mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-cache"})


# ─── ADB CONTROL ──────────────────────────────────────────────────────────────

@app.route("/api/devices/<serial>/tap", methods=["POST"])
def api_tap(serial):
    """Tap vào tọa độ x,y trên thiết bị"""
    data = request.json
    x = data.get("x", 0)
    y = data.get("y", 0)
    from adb_manager import run_adb
    run_adb(["shell", "input", "tap", str(x), str(y)], serial)
    return jsonify({"success": True})


@app.route("/api/devices/<serial>/swipe", methods=["POST"])
def api_swipe(serial):
    """Swipe trên thiết bị"""
    data = request.json
    x1, y1 = data.get("x1", 0), data.get("y1", 0)
    x2, y2 = data.get("x2", 0), data.get("y2", 0)
    duration = data.get("duration", 300)
    from adb_manager import run_adb
    run_adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)], serial)
    return jsonify({"success": True})


@app.route("/api/devices/<serial>/keyevent", methods=["POST"])
def api_keyevent(serial):
    """Gửi keyevent (back=4, home=3, menu=82)"""
    data = request.json
    keycode = data.get("keycode", 4)
    from adb_manager import run_adb
    run_adb(["shell", "input", "keyevent", str(keycode)], serial)
    return jsonify({"success": True})


# ─── PROXY MANAGEMENT ────────────────────────────────────────────────────────

@app.route("/api/proxies", methods=["GET"])
def api_get_proxies():
    """Lấy danh sách proxy"""
    proxies = get_all_proxies()
    return jsonify({"success": True, "proxies": proxies})


@app.route("/api/proxies", methods=["POST"])
def api_add_proxy():
    """Thêm proxy mới"""
    data = request.json
    host = data.get("host", "").strip()
    port = data.get("port", 0)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    proxy_type = data.get("type", "http")
    note = data.get("note", "")
    if not host or not port:
        return jsonify({"success": False, "error": "Thiếu host hoặc port"})
    proxy = add_proxy(host, int(port), username, password, proxy_type, note)
    return jsonify({"success": True, "proxy": proxy})


@app.route("/api/proxies/import", methods=["POST"])
def api_import_proxies():
    """Import proxy từ text (mỗi dòng 1 proxy)"""
    data = request.json
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"success": False, "error": "Nội dung trống"})
    count = import_proxies_from_text(text)
    return jsonify({"success": True, "imported": count})


@app.route("/api/proxies/<proxy_id>", methods=["DELETE"])
def api_remove_proxy(proxy_id):
    """Xóa proxy"""
    ok = remove_proxy(proxy_id)
    return jsonify({"success": ok})


@app.route("/api/proxies/<proxy_id>/check", methods=["POST"])
def api_check_proxy(proxy_id):
    """Kiểm tra proxy"""
    result = check_proxy(proxy_id)
    return jsonify(result)


@app.route("/api/proxies/<proxy_id>/assign", methods=["POST"])
def api_assign_proxy(proxy_id):
    """Gán proxy cho thiết bị"""
    data = request.json
    serial = data.get("serial")
    if not serial:
        return jsonify({"success": False, "error": "Thiếu serial"})
    ok = assign_proxy_to_device(serial, proxy_id)
    if ok:
        # Cài proxy lên thiết bị
        set_proxy_on_device(serial, proxy_id)
    return jsonify({"success": ok})


@app.route("/api/devices/<serial>/proxy", methods=["GET"])
def api_device_proxy(serial):
    """Lấy proxy của thiết bị"""
    proxy = get_proxy_for_device(serial)
    return jsonify({"success": True, "proxy": proxy})


@app.route("/api/devices/<serial>/proxy", methods=["DELETE"])
def api_remove_device_proxy(serial):
    """Gỡ proxy khỏi thiết bị"""
    ok = assign_proxy_to_device(serial, None)
    remove_proxy_from_device(serial)
    return jsonify({"success": ok})


@app.route("/api/devices/<serial>/ip", methods=["GET"])
def api_device_ip(serial):
    """Lấy IP hiện tại của thiết bị"""
    ip = get_device_current_ip(serial)
    return jsonify({"success": True, "ip": ip})


# ─── WARMUP / NUÔI ACC ────────────────────────────────────────────────────────

@app.route("/api/warmup/start", methods=["POST"])
def api_warmup_start():
    """Bắt đầu nuôi acc cho 1 hoặc nhiều thiết bị"""
    data = request.json
    serials = data.get("serials", [])
    serial = data.get("serial")
    if serial and serial not in serials:
        serials.append(serial)
    config = data.get("config", {})
    if not serials:
        return jsonify({"success": False, "error": "Thiếu serial"})
    if len(serials) == 1:
        start_warmup_async(serials[0], config)
        return jsonify({"success": True, "serial": serials[0]})
    result = batch_warmup(serials, config, stagger_seconds=data.get("stagger", 15))
    return jsonify({"success": True, **result})


@app.route("/api/warmup/stop", methods=["POST"])
def api_warmup_stop():
    """Dừng nuôi acc"""
    data = request.json
    serial = data.get("serial")
    if not serial:
        return jsonify({"success": False, "error": "Thiếu serial"})
    stop_warmup(serial)
    return jsonify({"success": True})


@app.route("/api/warmup/status/<serial>", methods=["GET"])
def api_warmup_status(serial):
    """Lấy trạng thái nuôi acc"""
    status = get_warmup_status(serial)
    return jsonify({"success": True, "status": status})


# ─── GROUP CONTROL ────────────────────────────────────────────────────────────

@app.route("/api/group/tap", methods=["POST"])
def api_group_tap():
    """Tap đồng loạt nhiều thiết bị"""
    data = request.json
    serials = data.get("serials", [])
    x = data.get("x", 0)
    y = data.get("y", 0)
    from adb_manager import run_adb
    results = []
    for serial in serials:
        _, _, code = run_adb(["shell", "input", "tap", str(x), str(y)], serial)
        results.append({"serial": serial, "success": code == 0})
    return jsonify({"success": True, "results": results})


@app.route("/api/group/swipe", methods=["POST"])
def api_group_swipe():
    """Swipe đồng loạt nhiều thiết bị"""
    data = request.json
    serials = data.get("serials", [])
    x1, y1 = data.get("x1", 540), data.get("y1", 1600)
    x2, y2 = data.get("x2", 540), data.get("y2", 400)
    duration = data.get("duration", 300)
    from adb_manager import run_adb
    results = []
    for serial in serials:
        _, _, code = run_adb(["shell", "input", "swipe",
                              str(x1), str(y1), str(x2), str(y2), str(duration)], serial)
        results.append({"serial": serial, "success": code == 0})
    return jsonify({"success": True, "results": results})


@app.route("/api/group/keyevent", methods=["POST"])
def api_group_keyevent():
    """Gửi keyevent đồng loạt"""
    data = request.json
    serials = data.get("serials", [])
    keycode = data.get("keycode", 4)
    from adb_manager import run_adb
    results = []
    for serial in serials:
        _, _, code = run_adb(["shell", "input", "keyevent", str(keycode)], serial)
        results.append({"serial": serial, "success": code == 0})
    return jsonify({"success": True, "results": results})


@app.route("/api/group/text", methods=["POST"])
def api_group_text():
    """Nhập text đồng loạt"""
    data = request.json
    serials = data.get("serials", [])
    text = data.get("text", "")
    from adb_manager import run_adb
    results = []
    for serial in serials:
        text_escaped = text.replace(" ", "%s")
        _, _, code = run_adb(["shell", "input", "text", text_escaped], serial)
        results.append({"serial": serial, "success": code == 0})
    return jsonify({"success": True, "results": results})


# ─── CONTENT MANAGER API ─────────────────────────────────────────────────────

@app.route("/api/content", methods=["GET"])
def api_get_content():
    return jsonify({"success": True, "content": get_all_content(), "stats": get_content_stats()})

@app.route("/api/content", methods=["POST"])
def api_add_content():
    data = request.json
    c = add_content(
        title=data.get("title", ""),
        video_path=data.get("video_path", ""),
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", []),
        product_name=data.get("product_name"),
        product_link=data.get("product_link"),
        tags=data.get("tags", [])
    )
    return jsonify({"success": True, "content": c})

@app.route("/api/content/<content_id>", methods=["PUT"])
def api_update_content(content_id):
    data = request.json
    ok = update_content(content_id, **data)
    return jsonify({"success": ok})

@app.route("/api/content/<content_id>", methods=["DELETE"])
def api_remove_content(content_id):
    ok = remove_content(content_id)
    return jsonify({"success": ok})

@app.route("/api/content/import_folder", methods=["POST"])
def api_import_content_folder():
    data = request.json
    folder = data.get("folder_path", "")
    if not folder:
        return jsonify({"success": False, "error": "Thiếu folder_path"})
    count = import_content_from_folder(folder)
    return jsonify({"success": True, "imported": count})

@app.route("/api/campaigns", methods=["GET"])
def api_get_campaigns():
    return jsonify({"success": True, "campaigns": get_all_campaigns()})

@app.route("/api/campaigns", methods=["POST"])
def api_create_campaign():
    data = request.json
    c = create_campaign(
        name=data.get("name", ""),
        serials=data.get("serials", []),
        content_ids=data.get("content_ids", []),
        schedule_type=data.get("schedule_type", "manual"),
        schedule_config=data.get("schedule_config", {}),
        note=data.get("note", "")
    )
    return jsonify({"success": True, "campaign": c})

@app.route("/api/campaigns/<campaign_id>", methods=["PUT"])
def api_update_campaign(campaign_id):
    data = request.json
    ok = update_campaign(campaign_id, **data)
    return jsonify({"success": ok})

@app.route("/api/campaigns/<campaign_id>", methods=["DELETE"])
def api_remove_campaign(campaign_id):
    ok = remove_campaign(campaign_id)
    return jsonify({"success": ok})

@app.route("/api/campaigns/<campaign_id>/run", methods=["POST"])
def api_run_campaign(campaign_id):
    task_id = new_task_id()
    running_tasks[task_id] = {"status": "running", "results": []}
    def run():
        results = run_campaign_post(campaign_id)
        running_tasks[task_id]["results"] = results
        running_tasks[task_id]["status"] = "done"
    t = threading.Thread(target=run, daemon=True)
    running_tasks[task_id]["thread"] = t
    t.start()
    return jsonify({"success": True, "task_id": task_id})


# ─── APP MANAGER API ─────────────────────────────────────────────────────────

@app.route("/api/apps/<serial>", methods=["GET"])
def api_get_apps(serial):
    include_system = request.args.get("system", "false").lower() == "true"
    apps = get_installed_apps(serial, include_system)
    return jsonify({"success": True, "apps": apps})

@app.route("/api/apps/install", methods=["POST"])
def api_install_apk():
    data = request.json
    serials = data.get("serials", [])
    apk_path = data.get("apk_path", "")
    if not apk_path:
        return jsonify({"success": False, "error": "Thiếu apk_path"})
    if len(serials) == 1:
        result = install_apk(serials[0], apk_path)
        return jsonify({"success": True, "results": [result]})
    results = batch_install_apk(serials, apk_path)
    return jsonify({"success": True, "results": results})

@app.route("/api/apps/uninstall", methods=["POST"])
def api_uninstall_app():
    data = request.json
    serials = data.get("serials", [])
    package = data.get("package", "")
    if not package:
        return jsonify({"success": False, "error": "Thiếu package"})
    results = batch_uninstall_app(serials, package)
    return jsonify({"success": True, "results": results})

@app.route("/api/apps/force_stop", methods=["POST"])
def api_force_stop():
    data = request.json
    serials = data.get("serials", [])
    package = data.get("package", "")
    results = batch_force_stop(serials, package)
    return jsonify({"success": True, "results": results})

@app.route("/api/apps/clear_data", methods=["POST"])
def api_clear_data():
    data = request.json
    serials = data.get("serials", [])
    package = data.get("package", "")
    results = batch_clear_data(serials, package)
    return jsonify({"success": True, "results": results})

@app.route("/api/apps/open", methods=["POST"])
def api_open_app():
    data = request.json
    serials = data.get("serials", [])
    package = data.get("package", "")
    results = batch_open_app(serials, package)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/reboot", methods=["POST"])
def api_batch_reboot():
    data = request.json
    serials = data.get("serials", [])
    results = batch_reboot(serials)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/wake", methods=["POST"])
def api_batch_wake():
    data = request.json
    serials = data.get("serials", [])
    results = batch_wake(serials)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/lock", methods=["POST"])
def api_batch_lock():
    data = request.json
    serials = data.get("serials", [])
    results = batch_lock(serials)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/battery", methods=["GET"])
def api_battery_all():
    serials = request.args.getlist("serial") or None
    results = get_all_battery_info(serials)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/<serial>/battery", methods=["GET"])
def api_battery(serial):
    info = get_battery_info(serial)
    return jsonify({"success": True, "info": info})

@app.route("/api/devices/<serial>/storage", methods=["GET"])
def api_storage(serial):
    info = get_device_storage(serial)
    return jsonify({"success": True, "info": info})

@app.route("/api/devices/screen_timeout", methods=["POST"])
def api_screen_timeout():
    data = request.json
    serials = data.get("serials", [])
    ms = data.get("ms", 600000)
    results = batch_set_screen_timeout(serials, ms)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/shell", methods=["POST"])
def api_shell():
    data = request.json
    serials = data.get("serials", [])
    command = data.get("command", "")
    if not command:
        return jsonify({"success": False, "error": "Thiếu command"})
    if len(serials) == 1:
        result = run_shell_command(serials[0], command)
        return jsonify({"success": True, "results": [result]})
    results = batch_shell_command(serials, command)
    return jsonify({"success": True, "results": results})

@app.route("/api/devices/push_file", methods=["POST"])
def api_push_file():
    data = request.json
    serials = data.get("serials", [])
    local_path = data.get("local_path", "")
    remote_path = data.get("remote_path", "/sdcard/")
    if not local_path:
        return jsonify({"success": False, "error": "Thiếu local_path"})
    results = push_file_to_all(serials, local_path, remote_path)
    return jsonify({"success": True, "results": results})


# ─── SCHEDULER API ────────────────────────────────────────────────────────────

@app.route("/api/scheduler", methods=["GET"])
def api_get_schedules():
    schedules = get_all_schedules()
    return jsonify({"success": True, "schedules": schedules})

@app.route("/api/scheduler", methods=["POST"])
def api_add_schedule():
    data = request.json
    serial = data.get("serial", "")
    action = data.get("action", "upload")
    scheduled_time = data.get("scheduled_time", "")
    repeat_type = data.get("repeat_type")
    note = data.get("note", "")
    video_path = data.get("video_path", "")
    caption = data.get("caption", "")
    if not serial or not scheduled_time:
        return jsonify({"success": False, "error": "Thiếu serial hoặc scheduled_time"})
    sid = add_schedule(serial=serial, action=action, scheduled_time=scheduled_time,
                       repeat_type=repeat_type, note=note,
                       video_path=video_path, caption=caption)
    return jsonify({"success": True, "id": sid})

@app.route("/api/scheduler/<int:sid>", methods=["DELETE"])
def api_delete_schedule(sid):
    remove_schedule(sid)
    return jsonify({"success": True})


# ─── APP MANAGER API ──────────────────────────────────────────────────────────

@app.route("/api/app_manager/<serial>/list_apps", methods=["GET"])
def api_am_list_apps(serial):
    packages = get_installed_apps(serial)
    return jsonify({"success": True, "packages": packages})

@app.route("/api/app_manager/<serial>/open", methods=["POST"])
def api_am_open(serial):
    data = request.json
    pkg = data.get("package", "")
    if not pkg:
        return jsonify({"success": False, "error": "Thiếu package"})
    result = app_open(serial, pkg)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/force_stop", methods=["POST"])
def api_am_force_stop(serial):
    data = request.json
    pkg = data.get("package", "")
    result = force_stop_app(serial, pkg)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/clear_data", methods=["POST"])
def api_am_clear_data(serial):
    data = request.json
    pkg = data.get("package", "")
    result = clear_app_data(serial, pkg)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/uninstall", methods=["POST"])
def api_am_uninstall(serial):
    data = request.json
    pkg = data.get("package", "")
    result = uninstall_app(serial, pkg)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/install", methods=["POST"])
def api_am_install(serial):
    data = request.json
    apk_path = data.get("apk_path", "")
    if not apk_path:
        return jsonify({"success": False, "error": "Thiếu apk_path"})
    result = install_apk(serial, apk_path)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/reboot", methods=["POST"])
def api_am_reboot(serial):
    result = reboot_device(serial)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/battery", methods=["GET"])
def api_am_battery(serial):
    info = get_battery_info(serial)
    return jsonify({"success": True, "battery": str(info)})

@app.route("/api/app_manager/<serial>/storage", methods=["GET"])
def api_am_storage(serial):
    info = get_device_storage(serial)
    return jsonify({"success": True, "storage": str(info)})

@app.route("/api/app_manager/<serial>/screen_timeout", methods=["POST"])
def api_am_screen_timeout(serial):
    data = request.json
    ms = data.get("timeout_ms", 600000)
    result = set_screen_timeout(serial, ms)
    return jsonify(result)

@app.route("/api/app_manager/<serial>/shell", methods=["POST"])
def api_am_shell(serial):
    data = request.json
    command = data.get("command", "")
    if not command:
        return jsonify({"success": False, "error": "Thiếu command"})
    result = run_shell_command(serial, command)
    return jsonify({"success": True, "output": str(result)})


# ─── SYSTEM ───────────────────────────────────────────────────────────────────

@app.route("/api/system/check", methods=["GET"])
def api_system_check():
    """Kiểm tra hệ thống"""
    adb_ok = check_adb_installed()
    return jsonify({
        "success": True,
        "adb": adb_ok,
        "scrcpy": _check_scrcpy()
    })


def _check_scrcpy() -> bool:
    import subprocess
    try:
        r = subprocess.run(["scrcpy", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("  BoxPhone TikTok Manager")
    print("  http://localhost:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False)
