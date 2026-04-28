"""
config.py — Cấu hình tập trung cho toàn dự án ContenFactory.

Đọc giá trị từ biến môi trường (qua .env nếu có cài python-dotenv).
KHÔNG hardcode secret/path trong source nữa — mọi giá trị đều có thể
override qua biến môi trường tương ứng.

Cách dùng:
    from config import (
        SPREADSHEET_ID, GEMINI_API_KEY, ROUTER_BASE, ROUTER_KEY,
        BASE_VIDEO_DIR, EDITED_VIDEO_DIR, COOKIES_DIR, LOG_DIR,
        FFMPEG_CMD, FFPROBE_CMD, IX_API_BASE, GOOGLE_CREDENTIALS_FILE,
    )

Tạo file .env ở project root (xem .env.example) hoặc đặt env var
trước khi chạy.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env nếu có (không bắt buộc — env var thật vẫn ưu tiên)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    # python-dotenv không bắt buộc; nếu không có thì bỏ qua
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_path(key: str, default: str) -> str:
    """Đọc đường dẫn từ env, thay '/' theo OS."""
    val = os.environ.get(key, default)
    return os.path.normpath(val) if val else val


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: str = str(_PROJECT_ROOT)

LOG_DIR: str = _env_path("LOG_DIR", str(_PROJECT_ROOT / "logs"))
BASE_VIDEO_DIR: str = _env_path("BASE_VIDEO_DIR", r"D:\Videos")
EDITED_VIDEO_DIR: str = _env_path("EDITED_VIDEO_DIR", r"D:\Videos\Edited")
COOKIES_DIR: str = _env_path("COOKIES_DIR", str(_PROJECT_ROOT / "cookies"))

# ---------------------------------------------------------------------------
# Google Sheets / Drive
# ---------------------------------------------------------------------------
GOOGLE_CREDENTIALS_FILE: str = _env_path(
    "GOOGLE_CREDENTIALS_FILE",
    str(_PROJECT_ROOT / "API" / "nha-may-content-208dc5165e29.json"),
)
SPREADSHEET_ID: str = _env("SPREADSHEET_ID", "")

# ---------------------------------------------------------------------------
# AI providers
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = _env("GEMINI_API_KEY", "")

# 9router (OpenAI-compatible local AI router)
ROUTER_BASE: str = _env("ROUTER_BASE", "http://localhost:20128/v1")
ROUTER_KEY: str = _env("ROUTER_KEY", "")
ROUTER_MODEL: str = _env("ROUTER_MODEL", "gemini/gemini-2.5-flash-preview")

# ---------------------------------------------------------------------------
# ffmpeg / ffprobe
# ---------------------------------------------------------------------------
FFMPEG_CMD: str = _env("FFMPEG_CMD", "ffmpeg")
FFPROBE_CMD: str = _env("FFPROBE_CMD", "ffprobe")

# ---------------------------------------------------------------------------
# IX Browser (FB automation) + ADB (BoxPhone)
# ---------------------------------------------------------------------------
IX_API_BASE: str = _env("IX_API_BASE", "http://127.0.0.1:53200/api/v2")
ADB_PATH: str = _env_path(
    "ADB_PATH",
    r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else "adb",
)

# ---------------------------------------------------------------------------
# Account encryption key (mã hoá password trong accounts.json)
# Dùng Fernet — sinh key bằng:
#     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# ---------------------------------------------------------------------------
ACCOUNT_ENCRYPTION_KEY: str = _env("ACCOUNT_ENCRYPTION_KEY", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    """Tạo các thư mục bắt buộc nếu chưa có."""
    for p in (LOG_DIR, BASE_VIDEO_DIR, EDITED_VIDEO_DIR, COOKIES_DIR):
        try:
            os.makedirs(p, exist_ok=True)
        except OSError:
            pass


def require(name: str) -> str:
    """Lấy giá trị bắt buộc từ env, raise nếu rỗng."""
    val = _env(name)
    if not val:
        raise RuntimeError(
            f"Thiếu cấu hình '{name}'. Set env var hoặc thêm vào .env "
            f"(xem .env.example ở project root)."
        )
    return val


# Tự động tạo dirs khi import (nhẹ, idempotent)
ensure_dirs()
