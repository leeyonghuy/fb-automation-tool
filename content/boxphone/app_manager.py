"""
app_manager.py
Quản lý ứng dụng trên thiết bị Android qua ADB.
Tham khảo tính năng App Manager của XiaoWei:
- Cài APK hàng loạt
- Gỡ app
- Force stop / Clear data
- Lấy danh sách app đã cài
- Reboot / Wake / Lock thiết bị
- Chụp ảnh màn hình hàng loạt
- Thay đổi DNS
"""

import os
import time
import threading
from typing import List, Dict, Optional
from adb_manager import run_adb, get_online_devices


# ─── APP OPERATIONS ───────────────────────────────────────────────────────────

def get_installed_apps(serial: str, include_system: bool = False) -> List[Dict]:
    """Lấy danh sách app đã cài trên thiết bị"""
    args = ["shell", "pm", "list", "packages", "-3"]  # -3 = third-party only
    if include_system:
        args = ["shell", "pm", "list", "packages"]
    stdout, _, code = run_adb(args, serial)
    if code != 0:
        return []
    apps = []
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("package:"):
            pkg = line.replace("package:", "").strip()
            apps.append({"package": pkg, "serial": serial})
    return apps


def install_apk(serial: str, apk_path: str) -> Dict:
    """Cài APK lên thiết bị"""
    if not os.path.exists(apk_path):
        return {"success": False, "error": f"File not found: {apk_path}"}
    _, stderr, code = run_adb(["install", "-r", "-d", apk_path], serial, timeout=120)
    if code == 0:
        return {"success": True, "serial": serial, "apk": os.path.basename(apk_path)}
    return {"success": False, "serial": serial, "error": stderr or "Install failed"}


def batch_install_apk(serials: List[str], apk_path: str) -> List[Dict]:
    """Cài APK hàng loạt lên nhiều thiết bị"""
    results = []
    lock = threading.Lock()

    def run(serial):
        r = install_apk(serial, apk_path)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=run, args=(s,), daemon=True) for s in serials]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=150)
    return results


def uninstall_app(serial: str, package_name: str) -> Dict:
    """Gỡ cài đặt app"""
    _, stderr, code = run_adb(["uninstall", package_name], serial, timeout=60)
    if code == 0:
        return {"success": True, "serial": serial, "package": package_name}
    return {"success": False, "serial": serial, "error": stderr or "Uninstall failed"}


def batch_uninstall_app(serials: List[str], package_name: str) -> List[Dict]:
    """Gỡ app hàng loạt"""
    results = []
    for serial in serials:
        results.append(uninstall_app(serial, package_name))
    return results


def force_stop_app(serial: str, package_name: str) -> bool:
    """Force stop app"""
    _, _, code = run_adb(["shell", "am", "force-stop", package_name], serial)
    return code == 0


def clear_app_data(serial: str, package_name: str) -> bool:
    """Xóa data của app (như factory reset app)"""
    _, _, code = run_adb(["shell", "pm", "clear", package_name], serial)
    return code == 0


def batch_force_stop(serials: List[str], package_name: str) -> List[Dict]:
    """Force stop app hàng loạt"""
    results = []
    for serial in serials:
        ok = force_stop_app(serial, package_name)
        results.append({"serial": serial, "success": ok})
    return results


def batch_clear_data(serials: List[str], package_name: str) -> List[Dict]:
    """Clear data hàng loạt"""
    results = []
    for serial in serials:
        ok = clear_app_data(serial, package_name)
        results.append({"serial": serial, "success": ok})
    return results


def open_app(serial: str, package_name: str) -> bool:
    """Mở app"""
    _, _, code = run_adb(["shell", "monkey", "-p", package_name,
                          "-c", "android.intent.category.LAUNCHER", "1"], serial)
    return code == 0


def batch_open_app(serials: List[str], package_name: str) -> List[Dict]:
    """Mở app hàng loạt"""
    results = []
    for serial in serials:
        ok = open_app(serial, package_name)
        results.append({"serial": serial, "success": ok})
        time.sleep(0.3)
    return results


# ─── DEVICE CONTROL ───────────────────────────────────────────────────────────

def reboot_device(serial: str) -> bool:
    """Khởi động lại thiết bị"""
    _, _, code = run_adb(["reboot"], serial)
    return code == 0


def batch_reboot(serials: List[str]) -> List[Dict]:
    """Reboot hàng loạt"""
    results = []
    for serial in serials:
        ok = reboot_device(serial)
        results.append({"serial": serial, "success": ok})
    return results


def wake_screen(serial: str) -> bool:
    """Bật màn hình (wake up)"""
    run_adb(["shell", "input", "keyevent", "224"], serial)  # KEYCODE_WAKEUP
    time.sleep(0.5)
    run_adb(["shell", "input", "keyevent", "82"], serial)   # KEYCODE_MENU (unlock)
    return True


def lock_screen(serial: str) -> bool:
    """Tắt màn hình (lock)"""
    _, _, code = run_adb(["shell", "input", "keyevent", "26"], serial)  # KEYCODE_POWER
    return code == 0


def batch_wake(serials: List[str]) -> List[Dict]:
    """Wake hàng loạt"""
    results = []
    for serial in serials:
        ok = wake_screen(serial)
        results.append({"serial": serial, "success": ok})
        time.sleep(0.2)
    return results


def batch_lock(serials: List[str]) -> List[Dict]:
    """Lock hàng loạt"""
    results = []
    for serial in serials:
        ok = lock_screen(serial)
        results.append({"serial": serial, "success": ok})
    return results


def get_battery_info(serial: str) -> Dict:
    """Lấy thông tin pin chi tiết"""
    stdout, _, _ = run_adb(["shell", "dumpsys", "battery"], serial)
    info = {"serial": serial, "level": 0, "status": "unknown",
            "charging": False, "temperature": 0}
    for line in stdout.split("\n"):
        line = line.strip()
        if "level:" in line:
            try:
                info["level"] = int(line.split(":")[1].strip())
            except Exception:
                pass
        elif "status:" in line:
            status_map = {"1": "unknown", "2": "charging", "3": "discharging",
                          "4": "not charging", "5": "full"}
            try:
                code = line.split(":")[1].strip()
                info["status"] = status_map.get(code, code)
                info["charging"] = code in ("2", "5")
            except Exception:
                pass
        elif "temperature:" in line:
            try:
                info["temperature"] = int(line.split(":")[1].strip()) / 10
            except Exception:
                pass
    return info


def get_all_battery_info(serials: List[str] = None) -> List[Dict]:
    """Lấy pin của nhiều thiết bị"""
    if serials is None:
        serials = get_online_devices()
    return [get_battery_info(s) for s in serials]


def set_volume(serial: str, stream: str = "music", level: int = 5) -> bool:
    """
    Đặt âm lượng thiết bị.
    stream: music / ring / notification / alarm
    level: 0-15
    """
    stream_map = {"music": 3, "ring": 2, "notification": 5, "alarm": 4}
    stream_id = stream_map.get(stream, 3)
    _, _, code = run_adb(["shell", "media", "volume", "--stream",
                          str(stream_id), "--set", str(level)], serial)
    return code == 0


def set_brightness(serial: str, level: int = 128) -> bool:
    """Đặt độ sáng màn hình (0-255)"""
    # Tắt auto brightness
    run_adb(["shell", "settings", "put", "system",
             "screen_brightness_mode", "0"], serial)
    _, _, code = run_adb(["shell", "settings", "put", "system",
                          "screen_brightness", str(level)], serial)
    return code == 0


def set_screen_timeout(serial: str, ms: int = 300000) -> bool:
    """Đặt thời gian tắt màn hình (ms). Default: 5 phút"""
    _, _, code = run_adb(["shell", "settings", "put", "system",
                          "screen_off_timeout", str(ms)], serial)
    return code == 0


def batch_set_screen_timeout(serials: List[str], ms: int = 600000) -> List[Dict]:
    """Đặt screen timeout hàng loạt"""
    results = []
    for serial in serials:
        ok = set_screen_timeout(serial, ms)
        results.append({"serial": serial, "success": ok})
    return results


def get_device_storage(serial: str) -> Dict:
    """Lấy thông tin bộ nhớ thiết bị"""
    stdout, _, _ = run_adb(["shell", "df", "/sdcard"], serial)
    info = {"serial": serial, "total": "", "used": "", "free": "", "percent": ""}
    lines = stdout.strip().split("\n")
    if len(lines) >= 2:
        parts = lines[-1].split()
        if len(parts) >= 5:
            try:
                info["total"] = parts[1]
                info["used"] = parts[2]
                info["free"] = parts[3]
                info["percent"] = parts[4]
            except Exception:
                pass
    return info


def push_file_to_all(serials: List[str], local_path: str, remote_path: str) -> List[Dict]:
    """Push file lên nhiều thiết bị cùng lúc"""
    from adb_manager import push_file
    results = []
    lock = threading.Lock()

    def run(serial):
        ok = push_file(serial, local_path, remote_path)
        with lock:
            results.append({"serial": serial, "success": ok})

    threads = [threading.Thread(target=run, args=(s,), daemon=True) for s in serials]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    return results


def run_shell_command(serial: str, command: str) -> Dict:
    """Chạy lệnh shell tùy ý trên thiết bị"""
    stdout, stderr, code = run_adb(["shell"] + command.split(), serial, timeout=30)
    return {
        "serial": serial,
        "success": code == 0,
        "stdout": stdout,
        "stderr": stderr,
        "code": code
    }


def batch_shell_command(serials: List[str], command: str) -> List[Dict]:
    """Chạy lệnh shell hàng loạt"""
    results = []
    for serial in serials:
        results.append(run_shell_command(serial, command))
    return results


# ─── CLIPBOARD ────────────────────────────────────────────────────────────────

def set_clipboard(serial: str, text: str) -> bool:
    """Copy text vào clipboard của thiết bị"""
    # Dùng ADB input để set clipboard
    escaped = text.replace("'", "\\'").replace(" ", "%s")
    _, _, code = run_adb(["shell", "am", "broadcast", "-a",
                          "clipper.set", "-e", "text", escaped], serial)
    return code == 0


def batch_input_text(serials: List[str], text: str) -> List[Dict]:
    """Nhập text hàng loạt vào ô đang focus"""
    results = []
    for serial in serials:
        escaped = text.replace(" ", "%s")
        _, _, code = run_adb(["shell", "input", "text", escaped], serial)
        results.append({"serial": serial, "success": code == 0})
    return results
