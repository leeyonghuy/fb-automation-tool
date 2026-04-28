"""
device_controller.py
Điều khiển thiết bị Android qua uiautomator2 + ADB.
- Tap, swipe, input text
- Screenshot
- Tìm element theo text/resourceId
- Mở app, back, home
"""

import time
import random
import uiautomator2 as u2
from typing import Optional, Tuple
from adb_manager import run_adb


# Cache kết nối u2 để tránh kết nối lại nhiều lần
_connections = {}


def connect(serial: str):
    """Kết nối uiautomator2 tới thiết bị"""
    if serial not in _connections:
        try:
            d = u2.connect(serial)
            d.healthcheck()
            _connections[serial] = d
        except Exception as e:
            print(f"[{serial}] Lỗi kết nối u2: {e}")
            return None
    return _connections[serial]


def disconnect(serial: str):
    """Ngắt kết nối"""
    if serial in _connections:
        del _connections[serial]


def tap(serial: str, x: int, y: int, delay: float = None):
    """Tap vào tọa độ (x, y)"""
    d = connect(serial)
    if not d:
        return False
    try:
        d.click(x, y)
        if delay is None:
            delay = random.uniform(0.5, 1.5)
        time.sleep(delay)
        return True
    except Exception as e:
        print(f"[{serial}] Tap error: {e}")
        return False


def tap_element(serial: str, text: str = None, resource_id: str = None,
                description: str = None, timeout: int = 10) -> bool:
    """Tap vào element theo text hoặc resource_id"""
    d = connect(serial)
    if not d:
        return False
    try:
        if text:
            el = d(text=text)
        elif resource_id:
            el = d(resourceId=resource_id)
        elif description:
            el = d(description=description)
        else:
            return False

        if el.wait(timeout=timeout):
            el.click()
            time.sleep(random.uniform(0.5, 1.2))
            return True
        return False
    except Exception as e:
        print(f"[{serial}] Tap element error: {e}")
        return False


def swipe(serial: str, sx: int, sy: int, ex: int, ey: int, duration: float = 0.3):
    """Swipe từ (sx,sy) đến (ex,ey)"""
    d = connect(serial)
    if not d:
        return False
    try:
        d.swipe(sx, sy, ex, ey, duration=duration)
        time.sleep(random.uniform(0.3, 0.8))
        return True
    except Exception as e:
        print(f"[{serial}] Swipe error: {e}")
        return False


def swipe_up(serial: str, distance: int = 500):
    """Scroll lên (swipe up)"""
    info = get_screen_size(serial)
    if not info:
        return False
    w, h = info
    cx = w // 2
    return swipe(serial, cx, h * 2 // 3, cx, h // 3, duration=0.4)


def swipe_down(serial: str, distance: int = 500):
    """Scroll xuống (swipe down)"""
    info = get_screen_size(serial)
    if not info:
        return False
    w, h = info
    cx = w // 2
    return swipe(serial, cx, h // 3, cx, h * 2 // 3, duration=0.4)


def input_text(serial: str, text: str, clear_first: bool = True):
    """Nhập text vào ô đang focus"""
    d = connect(serial)
    if not d:
        return False
    try:
        if clear_first:
            d.clear_text()
        d.send_keys(text)
        time.sleep(random.uniform(0.3, 0.8))
        return True
    except Exception as e:
        # Fallback: dùng ADB input
        text_escaped = text.replace(" ", "%s").replace("'", "\\'")
        _, _, code = run_adb(["shell", "input", "text", text_escaped], serial)
        return code == 0


def press_back(serial: str):
    """Nhấn nút Back"""
    d = connect(serial)
    if d:
        d.press("back")
        time.sleep(0.5)
        return True
    return False


def press_home(serial: str):
    """Nhấn nút Home"""
    d = connect(serial)
    if d:
        d.press("home")
        time.sleep(0.5)
        return True
    return False


def press_enter(serial: str):
    """Nhấn Enter"""
    run_adb(["shell", "input", "keyevent", "66"], serial)
    time.sleep(0.3)


def open_app(serial: str, package_name: str) -> bool:
    """Mở app theo package name"""
    d = connect(serial)
    if not d:
        return False
    try:
        d.app_start(package_name)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"[{serial}] Open app error: {e}")
        return False


def close_app(serial: str, package_name: str) -> bool:
    """Đóng app"""
    d = connect(serial)
    if not d:
        return False
    try:
        d.app_stop(package_name)
        return True
    except Exception:
        return False


def get_current_app(serial: str) -> str:
    """Lấy package name của app đang mở"""
    d = connect(serial)
    if not d:
        return ""
    try:
        info = d.app_current()
        return info.get("package", "")
    except Exception:
        return ""


def screenshot(serial: str, save_path: str = None):
    """Chụp màn hình, trả về PIL Image hoặc lưu file"""
    d = connect(serial)
    if not d:
        return None
    try:
        img = d.screenshot()
        if save_path:
            img.save(save_path)
        return img
    except Exception as e:
        print(f"[{serial}] Screenshot error: {e}")
        return None


def get_screen_size(serial: str) -> Optional[Tuple[int, int]]:
    """Lấy kích thước màn hình (width, height)"""
    d = connect(serial)
    if not d:
        return None
    try:
        info = d.window_size()
        return info[0], info[1]
    except Exception:
        stdout, _, _ = run_adb(["shell", "wm", "size"], serial)
        if "x" in stdout:
            parts = stdout.replace("Physical size: ", "").split("x")
            return int(parts[0]), int(parts[1])
        return None


def wait_for_element(serial: str, text: str = None, resource_id: str = None,
                     timeout: int = 15) -> bool:
    """Đợi element xuất hiện trên màn hình"""
    d = connect(serial)
    if not d:
        return False
    try:
        if text:
            return d(text=text).wait(timeout=timeout)
        elif resource_id:
            return d(resourceId=resource_id).wait(timeout=timeout)
        return False
    except Exception:
        return False


def element_exists(serial: str, text: str = None, resource_id: str = None) -> bool:
    """Kiểm tra element có tồn tại không"""
    d = connect(serial)
    if not d:
        return False
    try:
        if text:
            return d(text=text).exists(timeout=3)
        elif resource_id:
            return d(resourceId=resource_id).exists(timeout=3)
        return False
    except Exception:
        return False


def get_element_text(serial: str, resource_id: str) -> str:
    """Lấy text của element"""
    d = connect(serial)
    if not d:
        return ""
    try:
        el = d(resourceId=resource_id)
        if el.exists(timeout=5):
            return el.get_text() or ""
        return ""
    except Exception:
        return ""


def unlock_screen(serial: str):
    """Mở khóa màn hình (nếu đang tắt)"""
    run_adb(["shell", "input", "keyevent", "224"], serial)  # Wake up
    time.sleep(1)
    run_adb(["shell", "input", "keyevent", "82"], serial)   # Unlock
    time.sleep(0.5)


def random_delay(min_s: float = 1.0, max_s: float = 3.0):
    """Delay ngẫu nhiên để giả lập hành vi người dùng"""
    time.sleep(random.uniform(min_s, max_s))
