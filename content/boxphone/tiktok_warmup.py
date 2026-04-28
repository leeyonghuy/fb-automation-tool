"""
tiktok_warmup.py
Auto nuôi acc TikTok: lướt FYP, like, follow, comment ngẫu nhiên.
Mục đích: warm-up acc mới, tránh bị ban khi đăng bài.
"""

import time
import random
import threading
from typing import Dict, List, Optional
from device_controller import (
    connect, tap, tap_element, swipe_up, swipe_down,
    open_app, element_exists, wait_for_element,
    unlock_screen, random_delay, press_back, press_home
)
from tiktok_login import get_tiktok_package, is_logged_in

# ─── COMMENT TEMPLATES ────────────────────────────────────────────────────────
DEFAULT_COMMENTS = [
    "❤️", "🔥🔥", "😍", "Hay quá!", "Tuyệt vời!",
    "Thích cái này 👍", "Ủng hộ bạn!", "Nội dung hay!",
    "Xem mãi không chán", "Cảm ơn bạn đã chia sẻ",
    "Hay lắm bạn ơi", "🙌🙌🙌", "Đỉnh quá!", "Chill thật",
    "Xem đi xem lại vẫn thích", "Nội dung chất lượng 💯"
]

# ─── WARMUP STATE ─────────────────────────────────────────────────────────────
_warmup_sessions = {}  # {serial: {"running": bool, "stats": {...}}}
_warmup_lock = threading.Lock()


def get_warmup_status(serial: str) -> Dict:
    """Lấy trạng thái warmup của thiết bị"""
    with _warmup_lock:
        return _warmup_sessions.get(serial, {
            "running": False,
            "stats": {"videos_watched": 0, "likes": 0, "follows": 0, "comments": 0},
            "log": []
        })


def stop_warmup(serial: str):
    """Dừng warmup"""
    with _warmup_lock:
        if serial in _warmup_sessions:
            _warmup_sessions[serial]["running"] = False


def _log(serial: str, msg: str):
    """Ghi log warmup"""
    with _warmup_lock:
        if serial in _warmup_sessions:
            logs = _warmup_sessions[serial].setdefault("log", [])
            logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if len(logs) > 100:
                logs.pop(0)
    print(f"[WARMUP][{serial}] {msg}")


def _update_stat(serial: str, key: str, delta: int = 1):
    """Cập nhật thống kê"""
    with _warmup_lock:
        if serial in _warmup_sessions:
            stats = _warmup_sessions[serial].setdefault("stats", {})
            stats[key] = stats.get(key, 0) + delta


# ─── WARMUP ACTIONS ───────────────────────────────────────────────────────────

def _watch_video(serial: str, watch_seconds: float = None) -> bool:
    """Xem video trong FYP"""
    if watch_seconds is None:
        watch_seconds = random.uniform(5, 35)
    time.sleep(watch_seconds)
    _update_stat(serial, "videos_watched")
    return True


def _like_video(serial: str) -> bool:
    """Like video hiện tại"""
    d = connect(serial)
    if not d:
        return False
    try:
        # Tìm nút like (heart icon)
        like_btn = d(description="Like")
        if not like_btn.exists(timeout=3):
            like_btn = d(resourceId="com.zhiliaoapp.musically:id/iv_like")
        if not like_btn.exists(timeout=3):
            # Double tap vào giữa màn hình để like
            size = d.window_size()
            d.double_click(size[0] // 2, size[1] // 2)
            time.sleep(0.5)
            _update_stat(serial, "likes")
            return True

        # Kiểm tra đã like chưa
        liked = like_btn.info.get("selected", False)
        if not liked:
            like_btn.click()
            time.sleep(random.uniform(0.3, 0.8))
            _update_stat(serial, "likes")
            return True
        return False
    except Exception as e:
        print(f"[{serial}] Like error: {e}")
        return False


def _follow_creator(serial: str) -> bool:
    """Follow creator của video đang xem"""
    d = connect(serial)
    if not d:
        return False
    try:
        # Tìm nút Follow
        follow_btn = d(text="Follow")
        if not follow_btn.exists(timeout=3):
            follow_btn = d(description="Follow")
        if follow_btn.exists(timeout=3):
            follow_btn.click()
            time.sleep(random.uniform(0.5, 1.5))
            _update_stat(serial, "follows")
            return True
        return False
    except Exception as e:
        print(f"[{serial}] Follow error: {e}")
        return False


def _comment_video(serial: str, comment_text: str = None) -> bool:
    """Comment vào video"""
    d = connect(serial)
    if not d:
        return False
    try:
        if comment_text is None:
            comment_text = random.choice(DEFAULT_COMMENTS)

        # Tìm nút comment
        comment_btn = d(description="Comment")
        if not comment_btn.exists(timeout=3):
            comment_btn = d(resourceId="com.zhiliaoapp.musically:id/iv_comment")
        if not comment_btn.exists(timeout=3):
            return False

        comment_btn.click()
        time.sleep(1.5)

        # Tìm ô nhập comment
        input_field = d(hint="Add comment...")
        if not input_field.exists(timeout=3):
            input_field = d(className="android.widget.EditText")
        if input_field.exists(timeout=5):
            input_field.click()
            time.sleep(0.5)
            d.send_keys(comment_text)
            time.sleep(0.5)
            # Nhấn Send
            send_btn = d(text="Post")
            if not send_btn.exists(timeout=2):
                send_btn = d(description="Send")
            if send_btn.exists(timeout=3):
                send_btn.click()
                time.sleep(1)
                _update_stat(serial, "comments")
                # Đóng comment section
                press_back(serial)
                time.sleep(0.5)
                return True

        press_back(serial)
        return False
    except Exception as e:
        print(f"[{serial}] Comment error: {e}")
        press_back(serial)
        return False


def _open_fyp(serial: str) -> bool:
    """Mở TikTok và vào tab For You"""
    pkg = get_tiktok_package(serial)
    unlock_screen(serial)
    open_app(serial, pkg)
    time.sleep(4)

    if not is_logged_in(serial):
        return False

    # Tap vào tab "For You" nếu chưa ở đó
    d = connect(serial)
    if d:
        fyp = d(text="For You")
        if fyp.exists(timeout=3):
            fyp.click()
            time.sleep(1)
    return True


# ─── MAIN WARMUP LOOP ─────────────────────────────────────────────────────────

def run_warmup_session(serial: str, config: Dict = None) -> Dict:
    """
    Chạy 1 phiên warmup.
    config = {
        "duration_minutes": 20,       # Thời gian nuôi (phút)
        "like_probability": 0.3,      # Xác suất like mỗi video (0-1)
        "follow_probability": 0.05,   # Xác suất follow creator
        "comment_probability": 0.02,  # Xác suất comment
        "watch_min": 5,               # Xem tối thiểu (giây)
        "watch_max": 35,              # Xem tối đa (giây)
        "comments": []                # Danh sách comment template
    }
    """
    if config is None:
        config = {}

    duration_minutes = config.get("duration_minutes", 20)
    like_prob = config.get("like_probability", 0.3)
    follow_prob = config.get("follow_probability", 0.05)
    comment_prob = config.get("comment_probability", 0.02)
    watch_min = config.get("watch_min", 5)
    watch_max = config.get("watch_max", 35)
    custom_comments = config.get("comments", [])

    if custom_comments:
        global DEFAULT_COMMENTS
        comments_pool = custom_comments + DEFAULT_COMMENTS
    else:
        comments_pool = DEFAULT_COMMENTS

    # Khởi tạo session
    with _warmup_lock:
        _warmup_sessions[serial] = {
            "running": True,
            "stats": {"videos_watched": 0, "likes": 0, "follows": 0, "comments": 0},
            "log": [],
            "config": config,
            "start_time": time.time()
        }

    _log(serial, f"Bắt đầu nuôi acc - {duration_minutes} phút")

    # Mở TikTok FYP
    if not _open_fyp(serial):
        _log(serial, "❌ Không thể mở TikTok hoặc chưa đăng nhập")
        with _warmup_lock:
            _warmup_sessions[serial]["running"] = False
        return get_warmup_status(serial)

    end_time = time.time() + duration_minutes * 60
    video_count = 0

    while time.time() < end_time:
        # Kiểm tra có bị dừng không
        with _warmup_lock:
            if not _warmup_sessions.get(serial, {}).get("running", False):
                break

        video_count += 1
        watch_time = random.uniform(watch_min, watch_max)
        _log(serial, f"Video #{video_count}: xem {watch_time:.0f}s")

        # Xem video
        _watch_video(serial, watch_time)

        # Like ngẫu nhiên
        if random.random() < like_prob:
            if _like_video(serial):
                _log(serial, "👍 Like video")

        # Follow ngẫu nhiên
        if random.random() < follow_prob:
            if _follow_creator(serial):
                _log(serial, "➕ Follow creator")

        # Comment ngẫu nhiên
        if random.random() < comment_prob:
            comment = random.choice(comments_pool)
            if _comment_video(serial, comment):
                _log(serial, f"💬 Comment: {comment}")

        # Swipe lên xem video tiếp
        swipe_up(serial)
        time.sleep(random.uniform(0.5, 1.5))

        # Thỉnh thoảng pause lâu hơn (giả lập người thật)
        if random.random() < 0.1:
            pause = random.uniform(10, 30)
            _log(serial, f"⏸ Nghỉ {pause:.0f}s")
            time.sleep(pause)

    # Kết thúc session
    with _warmup_lock:
        if serial in _warmup_sessions:
            _warmup_sessions[serial]["running"] = False
            stats = _warmup_sessions[serial]["stats"]

    _log(serial, f"✅ Hoàn thành nuôi acc: {stats}")

    # Về home
    press_home(serial)
    return get_warmup_status(serial)


def start_warmup_async(serial: str, config: Dict = None) -> threading.Thread:
    """Chạy warmup trong background thread"""
    t = threading.Thread(target=run_warmup_session, args=(serial, config), daemon=True)
    t.start()
    return t


def batch_warmup(serials: List[str], config: Dict = None, stagger_seconds: float = 30) -> Dict:
    """
    Chạy warmup cho nhiều thiết bị cùng lúc.
    stagger_seconds: delay giữa mỗi thiết bị để tránh pattern
    """
    threads = {}
    for i, serial in enumerate(serials):
        if i > 0:
            time.sleep(stagger_seconds)
        t = start_warmup_async(serial, config)
        threads[serial] = t
        print(f"[WARMUP] Bắt đầu nuôi: {serial}")

    return {"started": list(threads.keys()), "count": len(threads)}
