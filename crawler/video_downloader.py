#!/usr/bin/env python3
"""
Video Downloader - Content Factory
Supports: YouTube, Douyin, Xiaohongshu
"""

import os
import sys
import json
import logging
import subprocess
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = r"D:\Contenfactory\logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "downloader.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_VIDEO_DIR = r"D:\Videos"
MAX_RETRIES = 3
YTDLP_CMD = "yt-dlp"  # must be in PATH or installed via pip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in Windows filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "douyin.com" in url_lower or "tiktok.com" in url_lower:
        return "douyin"
    elif "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower or "xhs" in url_lower:
        return "xiaohongshu"
    else:
        return "unknown"


def build_output_path(topic: str, video_id: str) -> str:
    """Build output directory path: D:/Videos/{Topic}/{Date}/"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_clean = sanitize_filename(topic) if topic else "Uncategorized"
    out_dir = os.path.join(BASE_VIDEO_DIR, topic_clean, date_str)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{sanitize_filename(video_id)}.%(ext)s")


# ---------------------------------------------------------------------------
# yt-dlp based downloader
# ---------------------------------------------------------------------------

def get_video_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    cmd = [YTDLP_CMD, "--dump-json", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.warning(f"Could not fetch info for {url}: {e}")
    return {}


def download_video(url: str, topic: str = "Uncategorized", video_id: str = None) -> dict:
    """
    Download a single video using yt-dlp.
    Returns dict with keys: success, file_path, error
    """
    platform = detect_platform(url)
    logger.info(f"Downloading [{platform}]: {url}")

    # Get metadata first to determine video_id
    if not video_id:
        info = get_video_info(url)
        video_id = info.get("id", sanitize_filename(url[-20:]))

    output_template = build_output_path(topic, video_id)

    # Build yt-dlp command
    cmd = [
        YTDLP_CMD,
        "--no-playlist",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", output_template,
        "--retries", str(MAX_RETRIES),
        "--fragment-retries", str(MAX_RETRIES),
        "--socket-timeout", "30",
        "--write-info-json",
        "--no-overwrites",
    ]

    # Platform-specific options
    if platform == "douyin":
        cmd += ["--extractor-args", "douyin:api_hostname=www.iesdouyin.com"]
    elif platform == "xiaohongshu":
        # yt-dlp has limited xhs support; use cookies if available
        cookies_file = r"D:\Contenfactory\crawler\cookies\xhs_cookies.txt"
        if os.path.exists(cookies_file):
            cmd += ["--cookies", cookies_file]

    cmd.append(url)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"  Attempt {attempt}/{MAX_RETRIES} ...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            stdout = result.stdout + result.stderr

            if result.returncode == 0:
                # Find downloaded file
                date_str = datetime.now().strftime("%Y-%m-%d")
                topic_clean = sanitize_filename(topic)
                out_dir = os.path.join(BASE_VIDEO_DIR, topic_clean, date_str)
                file_path = find_downloaded_file(out_dir, video_id)
                logger.info(f"  ✓ Downloaded to: {file_path}")
                return {"success": True, "file_path": file_path, "error": None, "video_id": video_id}
            else:
                logger.warning(f"  yt-dlp error (attempt {attempt}): {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"  Timeout on attempt {attempt}")
        except Exception as e:
            logger.error(f"  Exception on attempt {attempt}: {e}")

    error_msg = f"Failed after {MAX_RETRIES} attempts"
    logger.error(f"  ✗ {error_msg}: {url}")
    return {"success": False, "file_path": None, "error": error_msg, "video_id": video_id}


def find_downloaded_file(directory: str, video_id: str) -> str:
    """Find the downloaded file in the directory."""
    try:
        for f in os.listdir(directory):
            if sanitize_filename(video_id) in f and f.endswith(".mp4"):
                return os.path.join(directory, f)
        # Return any mp4 if video_id match not found
        for f in os.listdir(directory):
            if f.endswith(".mp4"):
                return os.path.join(directory, f)
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Channel scanning (YouTube)
# ---------------------------------------------------------------------------

def get_channel_latest_videos(channel_url: str, max_count: int = 10) -> list:
    """
    Get latest video URLs from a YouTube channel.
    Returns list of dicts: {url, title, id, upload_date}
    """
    logger.info(f"Scanning channel: {channel_url}")
    cmd = [
        YTDLP_CMD,
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(max_count),
        channel_url
    ]
    videos = []
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        item = json.loads(line)
                        videos.append({
                            "url": item.get("url") or item.get("webpage_url", ""),
                            "title": item.get("title", ""),
                            "id": item.get("id", ""),
                            "upload_date": item.get("upload_date", "")
                        })
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.error(f"Error scanning channel {channel_url}: {e}")
    logger.info(f"  Found {len(videos)} videos")
    return videos


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Content Factory - Video Downloader")
    parser.add_argument("url", help="Video or channel URL")
    parser.add_argument("--topic", default="Uncategorized", help="Topic/category")
    parser.add_argument("--mode", choices=["video", "channel"], default="video",
                        help="Download single video or scan channel")
    parser.add_argument("--max-videos", type=int, default=10,
                        help="Max videos to fetch from channel")
    args = parser.parse_args()

    if args.mode == "video":
        result = download_video(args.url, topic=args.topic)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        videos = get_channel_latest_videos(args.url, max_count=args.max_videos)
        print(json.dumps(videos, ensure_ascii=False, indent=2))
