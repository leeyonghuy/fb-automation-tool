"""
video_dedup.py
Kiểm tra và ghi nhận video đã đăng để tránh đăng trùng.
- Hash file video (MD5)
- Lưu lịch sử vào post_history.json
- Check trước khi đăng
"""

import hashlib
import json
import sys
import time
from pathlib import Path

HISTORY_FILE = Path(__file__).parent / "post_history.json"

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


# ─────────────────────────────────────────────
# Hash
# ─────────────────────────────────────────────

def compute_video_hash(file_path: str, chunk_size: int = 8192) -> str:
    """
    Tính MD5 hash của file video.
    Trả về hex string hoặc "" nếu file không tồn tại.
    """
    path = Path(file_path)
    if not path.exists():
        print(f"[video_dedup] File không tồn tại: {file_path}")
        return ""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"[video_dedup] Hash error: {e}")
        return ""


# ─────────────────────────────────────────────
# History
# ─────────────────────────────────────────────

def has_been_posted(video_hash: str, page_url: str) -> bool:
    """
    Kiểm tra video (theo hash) đã được đăng lên page_url chưa.
    Trả về True nếu đã đăng.
    """
    if not video_hash:
        return False
    data = load_json(HISTORY_FILE, default={}) or {}
    page_key = _normalize_url(page_url)
    posted_hashes = data.get(page_key, [])
    return video_hash in posted_hashes


def record_post(video_hash: str, page_url: str, fb_uid: str = "",
                video_path: str = "") -> bool:
    """
    Ghi nhận video đã đăng thành công.
    Trả về True nếu ghi thành công.
    """
    if not video_hash:
        return False
    page_key = _normalize_url(page_url)
    try:
        with locked_update(HISTORY_FILE, default={}) as data:
            if page_key not in data:
                data[page_key] = []
            if video_hash not in data[page_key]:
                data[page_key].append(video_hash)
            # Giữ tối đa 500 hash per page
            if len(data[page_key]) > 500:
                data[page_key] = data[page_key][-500:]
        print(f"[video_dedup] Recorded: {video_hash[:8]}... → {page_key}")
        return True
    except Exception as e:
        print(f"[video_dedup] Record error: {e}")
        return False


def check_and_record(video_path: str, page_url: str, fb_uid: str = "") -> dict:
    """
    Convenience: tính hash + check + (nếu chưa đăng) trả về hash để dùng sau.
    Trả về:
        {"hash": str, "already_posted": bool, "skip": bool}
    skip=True nghĩa là nên bỏ qua (đã đăng rồi hoặc không hash được)
    """
    video_hash = compute_video_hash(video_path)
    if not video_hash:
        return {"hash": "", "already_posted": False, "skip": False}

    already = has_been_posted(video_hash, page_url)
    if already:
        print(f"[video_dedup] ⚠ Đã đăng video này lên {_normalize_url(page_url)} — bỏ qua")
    return {"hash": video_hash, "already_posted": already, "skip": already}


def _normalize_url(url: str) -> str:
    """Chuẩn hóa URL để làm key (bỏ trailing slash, lowercase)."""
    return url.strip().rstrip("/").lower()


# ─────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────

def get_stats() -> dict:
    """Thống kê số video đã đăng per page."""
    data = load_json(HISTORY_FILE, default={}) or {}
    return {page: len(hashes) for page, hashes in data.items()}
