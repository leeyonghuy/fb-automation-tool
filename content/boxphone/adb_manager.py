"""
adb_manager.py
Quản lý kết nối ADB với nhiều BoxPhone qua USB.
- Detect thiết bị
- Kiểm tra trạng thái
- Push/pull file
"""

import subprocess
import os
import time
from pathlib import Path
from typing import List, Dict, Optional


# Tìm ADB: ưu tiên C:\platform-tools, fallback về PATH
import shutil as _shutil
_ADB_PATH = r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else (_shutil.which("adb") or "adb")


def run_adb(args: list, device_serial: str = None, timeout: int = 30) -> tuple:
    """
    Chạy lệnh ADB, trả về (stdout, stderr, returncode)
    """
    cmd = [_ADB_PATH]
    if device_serial:
        cmd += ["-s", device_serial]
    cmd += args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", -1
    except FileNotFoundError:
        return "", "ADB not found. Please install Android SDK Platform Tools.", -1


def get_devices() -> List[Dict]:
    """
    Lấy danh sách thiết bị đang kết nối.
    Trả về list: [{"serial": "...", "status": "device|offline|unauthorized"}]
    """
    stdout, stderr, code = run_adb(["devices"])
    devices = []
    if code != 0:
        return devices
    lines = stdout.split("\n")[1:]  # Bỏ dòng "List of devices attached"
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            serial = parts[0].strip()
            status = parts[1].strip()
            devices.append({"serial": serial, "status": status})
    return devices


def get_online_devices() -> List[str]:
    """Trả về list serial của thiết bị đang online (status=device)"""
    return [d["serial"] for d in get_devices() if d["status"] == "device"]


def get_device_info(serial: str) -> Dict:
    """Lấy thông tin thiết bị: model, Android version, battery"""
    info = {"serial": serial}

    # Model
    stdout, _, _ = run_adb(["shell", "getprop", "ro.product.model"], serial)
    info["model"] = stdout or "Unknown"

    # Android version
    stdout, _, _ = run_adb(["shell", "getprop", "ro.build.version.release"], serial)
    info["android_version"] = stdout or "Unknown"

    # Battery
    stdout, _, _ = run_adb(["shell", "dumpsys", "battery"], serial)
    battery = "Unknown"
    for line in stdout.split("\n"):
        if "level:" in line:
            battery = line.split(":")[1].strip() + "%"
            break
    info["battery"] = battery

    # Screen size
    stdout, _, _ = run_adb(["shell", "wm", "size"], serial)
    info["screen_size"] = stdout.replace("Physical size: ", "") or "Unknown"

    return info


def get_all_devices_info() -> List[Dict]:
    """Lấy thông tin tất cả thiết bị đang online"""
    serials = get_online_devices()
    return [get_device_info(s) for s in serials]


def push_file(serial: str, local_path: str, remote_path: str) -> bool:
    """Push file từ máy tính lên điện thoại"""
    _, _, code = run_adb(["push", local_path, remote_path], serial, timeout=120)
    return code == 0


def pull_file(serial: str, remote_path: str, local_path: str) -> bool:
    """Pull file từ điện thoại về máy tính"""
    _, _, code = run_adb(["pull", remote_path, local_path], serial, timeout=120)
    return code == 0


def install_apk(serial: str, apk_path: str) -> bool:
    """Cài APK lên thiết bị"""
    _, _, code = run_adb(["install", "-r", apk_path], serial, timeout=120)
    return code == 0


def reboot_device(serial: str) -> bool:
    """Khởi động lại thiết bị"""
    _, _, code = run_adb(["reboot"], serial)
    return code == 0


def start_scrcpy(serial: str, window_title: str = None, max_size: int = 800):
    """
    Mở scrcpy để mirror màn hình thiết bị.
    Cần cài scrcpy: https://github.com/Genymobile/scrcpy
    """
    cmd = ["scrcpy", "-s", serial, f"--max-size={max_size}", "--no-audio"]
    if window_title:
        cmd += [f"--window-title={window_title}"]
    try:
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
        return True
    except FileNotFoundError:
        print("scrcpy not found. Download from: https://github.com/Genymobile/scrcpy/releases")
        return False


def start_scrcpy_all(max_size: int = 600):
    """Mở scrcpy cho tất cả thiết bị đang online"""
    serials = get_online_devices()
    results = []
    for i, serial in enumerate(serials):
        info = get_device_info(serial)
        title = f"[{i+1}] {info.get('model', serial)} - {serial}"
        ok = start_scrcpy(serial, window_title=title, max_size=max_size)
        results.append({"serial": serial, "success": ok})
        time.sleep(0.5)  # Tránh mở quá nhanh
    return results


def check_adb_installed() -> bool:
    """Kiểm tra ADB đã cài chưa"""
    stdout, _, code = run_adb(["version"])
    return code == 0


if __name__ == "__main__":
    print("=== ADB Manager ===")
    if not check_adb_installed():
        print("❌ ADB chưa được cài. Tải tại: https://developer.android.com/tools/releases/platform-tools")
    else:
        devices = get_devices()
        print(f"Thiết bị kết nối: {len(devices)}")
        for d in devices:
            print(f"  {d['serial']} - {d['status']}")
            if d["status"] == "device":
                info = get_device_info(d["serial"])
                print(f"    Model: {info['model']}, Android: {info['android_version']}, Battery: {info['battery']}")
