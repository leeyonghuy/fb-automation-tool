#!/usr/bin/env python3
"""
Video Downloader - Content Factory v2
Supports: YouTube, TikTok, Douyin, Xiaohongshu, Instagram, 1800+ sites
Uses yt-dlp Python API (faster than subprocess) + cookies + retry
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path

# Cho phép import config.py ở project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, BASE_VIDEO_DIR as _BASE_VIDEO_DIR, COOKIES_DIR as _COOKIES_DIR  # noqa: E402

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    import subprocess

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
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
BASE_VIDEO_DIR = _BASE_VIDEO_DIR
COOKIES_DIR = _COOKIES_DIR
MAX_RETRIES = 5

# Browser-like User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# yt-dlp base options (dùng Python API)
BASE_YTDLP_OPTS = {
    "quiet": True,
    "no_warnings": False,
    "noplaylist": True,
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "merge_output_format": "mp4",
    "retries": MAX_RETRIES,
    "fragment_retries": MAX_RETRIES,
    "socket_timeout": 30,
    "http_headers": {"User-Agent": USER_AGENT},
    "writeinfojson": True,
    "no_overwrites": True,
    "ignoreerrors": False,
    "extractor_retries": 3,
}


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
    elif "bilibili.com" in url_lower or "bilibili.tv" in url_lower or "b23.tv" in url_lower:
        return "bilibili"
    elif "instagram.com" in url_lower or "instagr.am" in url_lower:
        return "instagram"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower or "fb.com" in url_lower:
        return "facebook"
    elif "twitter.com" in url_lower or "x.com" in url_lower or "t.co" in url_lower:
        return "twitter"
    elif "threads.net" in url_lower:
        return "threads"
    elif "weibo.com" in url_lower or "weibo.cn" in url_lower:
        return "weibo"
    else:
        return "unknown"


# Mapping chất lượng video
QUALITY_MAP = {
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
}


def build_output_path(topic: str, video_id: str) -> str:
    """Build output directory path: D:/Videos/{Topic}/{Date}/"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_clean = sanitize_filename(topic) if topic else "Uncategorized"
    out_dir = os.path.join(BASE_VIDEO_DIR, topic_clean, date_str)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{sanitize_filename(video_id)}.%(ext)s")


# ---------------------------------------------------------------------------
# yt-dlp Python API (nhanh hơn subprocess, không cần spawn process)
# ---------------------------------------------------------------------------

def _get_ytdlp_opts(platform: str, output_template: str = None, quality: str = "best") -> dict:
    """Build yt-dlp options theo platform."""
    opts = dict(BASE_YTDLP_OPTS)
    if output_template:
        opts["outtmpl"] = output_template

    # Chất lượng video
    if quality in QUALITY_MAP:
        opts["format"] = QUALITY_MAP[quality]

    # Cookies
    cookies_map = {
        "douyin": "tiktok_cookies.txt",
        "tiktok": "tiktok_cookies.txt",
        "xiaohongshu": "xhs_cookies.txt",
        "youtube": "youtube_cookies.txt",
        "instagram": "instagram_cookies.txt",
        "bilibili": "bilibili_cookies.txt",  # bilibili.tv (quốc tế)
    }
    cookie_file = os.path.join(COOKIES_DIR, cookies_map.get(platform, ""))
    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file
        logger.info(f"  Using cookies: {cookie_file}")

    # Thêm cookies cho platforms mới
    cookies_map_extra = {
        "facebook": "facebook_cookies.txt",
        "twitter": "twitter_cookies.txt",
        "threads": "threads_cookies.txt",
    }
    if platform in cookies_map_extra:
        extra_cookie = os.path.join(COOKIES_DIR, cookies_map_extra[platform])
        if os.path.exists(extra_cookie):
            opts["cookiefile"] = extra_cookie
            logger.info(f"  Using cookies: {extra_cookie}")

    # Platform-specific extractor args
    if platform in ("douyin", "tiktok"):
        opts["extractor_args"] = {"tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}}
    elif platform == "bilibili":
        opts["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    elif platform == "facebook":
        opts["format"] = "bestvideo+bestaudio/best"

    return opts


def get_video_info(url: str) -> dict:
    """Fetch video metadata without downloading (dùng Python API)."""
    platform = detect_platform(url)
    opts = _get_ytdlp_opts(platform)
    opts["skip_download"] = True

    if not YTDLP_AVAILABLE:
        # Fallback subprocess
        try:
            import subprocess
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-playlist", url],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"Could not fetch info for {url}: {e}")
        return {}

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info or {}
    except Exception as e:
        logger.warning(f"Could not fetch info for {url}: {e}")
        return {}


def download_video(url: str, topic: str = "Uncategorized", video_id: str = None,
                   quality: str = "best", progress_callback=None) -> dict:
    """
    Download a single video dùng yt-dlp Python API.
    Với Xiaohongshu: thử yt-dlp trước, fail thì fallback sang module riêng
    quality: 'best' | '1080p' | '720p' | '480p'
    progress_callback: function(percent, message) - cập nhật tiến trình

    Returns dict: {success, file_path, error, video_id, title, platform}
    """
    platform = detect_platform(url)
    logger.info(f"Downloading [{platform}]: {url}")

    # Special path: Xiaohongshu cần fallback đặc thù
    if platform == "xiaohongshu":
        return _download_xhs_with_fallback(url, topic, video_id)

    # Lấy video_id trước
    if not video_id:
        info = get_video_info(url)
        video_id = info.get("id") or sanitize_filename(url[-20:])
        title = info.get("title", "")
    else:
        title = ""

    output_template = build_output_path(topic, video_id)
    opts = _get_ytdlp_opts(platform, output_template, quality=quality)

    if not YTDLP_AVAILABLE:
        # Fallback subprocess
        import subprocess
        cmd = ["yt-dlp", "--no-playlist", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
               "--merge-output-format", "mp4", "-o", output_template,
               "--retries", str(MAX_RETRIES), "--socket-timeout", "30",
               "--add-header", f"User-Agent:{USER_AGENT}", url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                out_dir = os.path.dirname(output_template)
                file_path = find_downloaded_file(out_dir, video_id)
                return {"success": True, "file_path": file_path, "error": None, "video_id": video_id, "title": title}
        except Exception as e:
            return {"success": False, "file_path": None, "error": str(e), "video_id": video_id, "title": title}

    # Dùng Python API
    downloaded_file = {"path": ""}

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0 and progress_callback:
                pct = int(downloaded / total * 80) + 10  # 10-90%
                speed = d.get("speed", 0)
                speed_str = f"{speed/1024/1024:.1f}MB/s" if speed else ""
                progress_callback(pct, f"Đang tải {pct}% {speed_str}")
        elif d["status"] == "finished":
            downloaded_file["path"] = d.get("filename", "")
            logger.info(f"  \u2713 Downloaded: {d.get('filename', '')}")
            if progress_callback:
                progress_callback(90, "Hoàn tất, đang merge...")
        elif d["status"] == "error":
            logger.warning(f"  \u2717 Error: {d.get('error', '')}")
            if progress_callback:
                progress_callback(0, f"Lỗi: {d.get('error', '')[:80]}")

    opts["progress_hooks"] = [progress_hook]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"  Attempt {attempt}/{MAX_RETRIES} ...")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            # Tìm file đã download
            out_dir = os.path.dirname(output_template)
            file_path = downloaded_file["path"] or find_downloaded_file(out_dir, video_id)
            if file_path and os.path.exists(file_path):
                logger.info(f"  ✓ Success: {file_path}")
                return {"success": True, "file_path": file_path, "error": None,
                        "video_id": video_id, "title": title, "platform": platform}
            else:
                logger.warning(f"  File not found after download attempt {attempt}")
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"  DownloadError attempt {attempt}: {str(e)[:200]}")
        except Exception as e:
            logger.error(f"  Exception attempt {attempt}: {e}")

    error_msg = f"Failed after {MAX_RETRIES} attempts"
    logger.error(f"  ✗ {error_msg}: {url}")
    return {"success": False, "file_path": None, "error": error_msg,
            "video_id": video_id, "title": title, "platform": platform}


def _download_xhs_with_fallback(url: str, topic: str, video_id: str = None) -> dict:
    """
    Tải XHS theo 3 tier:
      Tier 0: yt-dlp (nhanh, hỗ trợ partial)
      Tier 1+2: module `xiaohongshu.py` (HTTP parse → Playwright)
    """
    # Tier 0: yt-dlp
    if YTDLP_AVAILABLE:
        try:
            info = get_video_info(url)
            vid = video_id or info.get("id") or sanitize_filename(url[-20:])
            title = info.get("title", "")
            output_template = build_output_path(topic, vid)
            opts = _get_ytdlp_opts("xiaohongshu", output_template)

            captured = {"path": ""}

            def _hook(d):
                if d.get("status") == "finished":
                    captured["path"] = d.get("filename", "")

            opts["progress_hooks"] = [_hook]
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            out_dir = os.path.dirname(output_template)
            file_path = captured["path"] or find_downloaded_file(out_dir, vid)
            if file_path and os.path.exists(file_path):
                logger.info(f"  ✓ Tier 0 (yt-dlp) success: {file_path}")
                return {"success": True, "file_path": file_path, "error": None,
                        "video_id": vid, "title": title, "platform": "xiaohongshu"}
            logger.warning("  Tier 0 (yt-dlp) downloaded nhưng không thấy file → fallback")
        except Exception as e:
            logger.warning(f"  Tier 0 (yt-dlp) fail: {str(e)[:200]} → fallback")

    # Tier 1 + 2: module xiaohongshu
    try:
        from xiaohongshu import download_xhs  # type: ignore
    except ImportError as e:
        return {"success": False, "file_path": None, "error": f"Cannot import xiaohongshu module: {e}",
                "video_id": video_id, "title": "", "platform": "xiaohongshu"}

    out_dir = os.path.dirname(build_output_path(topic, video_id or "x"))
    res = download_xhs(url, out_dir, video_id=video_id or "")
    return res


def find_downloaded_file(directory: str, video_id: str) -> str:
    """
    Tìm file đã download trong thư mục dựa trên video_id.
    Bỏ qua file tạm của yt-dlp (.f1.mp4, .f12.mp4, .part, .ytdl).
    KHÔNG fallback chung chung sang "any mp4" vì thư mục date có thể chứa
    nhiều video khác đã download trước đó.
    """
    if not directory or not os.path.isdir(directory):
        return ""
    safe_id = sanitize_filename(video_id) if video_id else ""
    try:
        if safe_id:
            # Ưu tiên file merged (không có .fXX trước extension)
            candidates = []
            for f in os.listdir(directory):
                if safe_id not in f:
                    continue
                fl = f.lower()
                # Bỏ qua file tạm: .f1.mp4, .f12.mp4, .part, .ytdl
                if re.search(r'\.f\d+\.', fl) or fl.endswith('.part') or fl.endswith('.ytdl'):
                    continue
                if fl.endswith(('.mp4', '.mkv', '.webm')):
                    candidates.append(os.path.join(directory, f))
            if candidates:
                # Trả về file mới nhất
                return max(candidates, key=os.path.getmtime)
    except OSError:
        pass
    return ""


# ---------------------------------------------------------------------------
# Channel scanning (YouTube, TikTok, Douyin)
# ---------------------------------------------------------------------------

def get_channel_latest_videos(channel_url: str, max_count: int = 10) -> list:
    """
    Get latest video URLs from YouTube/TikTok/Douyin channel.
    Returns list of dicts: {url, title, id, upload_date, platform}
    """
    logger.info(f"Scanning channel: {channel_url}")
    platform = detect_platform(channel_url)

    if YTDLP_AVAILABLE:
        opts = _get_ytdlp_opts(platform)
        opts.update({
            "extract_flat": True,
            "playlistend": max_count,
            "quiet": True,
        })
        videos = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                if info and "entries" in info:
                    for entry in (info["entries"] or [])[:max_count]:
                        if not entry:
                            continue
                        vid_url = entry.get("url") or entry.get("webpage_url", "")
                        if vid_url and not vid_url.startswith("http"):
                            vid_url = f"https://www.tiktok.com/@{info.get('uploader_id','')}/video/{entry.get('id','')}"
                        videos.append({
                            "url": vid_url,
                            "title": entry.get("title", ""),
                            "id": entry.get("id", ""),
                            "upload_date": entry.get("upload_date", ""),
                            "platform": platform,
                            "duration": entry.get("duration", 0),
                            "view_count": entry.get("view_count", 0),
                        })
        except Exception as e:
            logger.error(f"Error scanning channel {channel_url}: {e}")
        logger.info(f"  Found {len(videos)} videos")
        return videos

    # Fallback subprocess
    import subprocess
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json",
           "--playlist-end", str(max_count), channel_url]
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
                            "upload_date": item.get("upload_date", ""),
                            "platform": platform,
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
