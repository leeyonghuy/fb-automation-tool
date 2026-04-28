#!/usr/bin/env python3
"""
run_pipeline.py — [DEPRECATED]

Pipeline cũ: download TikTok → anti-CP → "dịch" bằng 9router.

File này có 2 vấn đề nghiêm trọng đã được thay thế:
  1. Subtitle được "bịa" bởi Gemini (không phiên âm audio thật)
  2. ROUTER_KEY hardcoded (secret leak)

Double-check tại `crawler/video_editor.py::process_video()` — implementation
đúng dùng Gemini SDK + audio upload thật.

File này giữ lại như 1 thin wrapper gọi vào video_editor với URL/topic
truền qua CLI — để bảo mức tương thích ngược.
"""

import os, sys, json, logging
from pathlib import Path

# Cho phép import config.py ở project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (  # noqa: E402
    ROUTER_BASE, ROUTER_KEY, ROUTER_MODEL,
    BASE_VIDEO_DIR, EDITED_VIDEO_DIR, LOG_DIR,
)

# Backward-compat aliases
MODEL = ROUTER_MODEL
DOWNLOAD_DIR = os.path.join(BASE_VIDEO_DIR, "TikTok")
EDITED_DIR = EDITED_VIDEO_DIR

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EDITED_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ─── MAIN (deprecated path) ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="[DEPRECATED] Dùng video_editor.process_video trực tiếp."
    )
    parser.add_argument("--url", help="URL TikTok/Douyin")
    parser.add_argument("--topic", default="Uncategorized")
    args = parser.parse_args()

    if not args.url:
        log.error(
            "File này đã bị deprecated. Dùng:\n"
            "  python -m crawler.orchestrator --mode videos\n"
            "hoặc:\n"
            "  python crawler/video_editor.py <input.mp4> --mode full\n"
        )
        sys.exit(2)

    log.warning("run_pipeline.py đã deprecated, chuyển hướng sang video_editor.process_video.")
    from video_downloader import download_video
    from video_editor import process_video

    dl = download_video(args.url, topic=args.topic)
    if not dl.get("success"):
        log.error(f"Tải video thất bại: {dl.get('error')}")
        sys.exit(1)

    proc = process_video(dl["file_path"], topic=args.topic, mode="full")
    print(json.dumps(proc, ensure_ascii=False, indent=2))
