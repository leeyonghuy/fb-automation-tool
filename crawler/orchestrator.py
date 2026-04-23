#!/usr/bin/env python3
"""
Orchestrator - Content Factory
Luồng 1: Quét kênh định kỳ, tải video mới
Luồng 2: Xử lý video thủ công từ tab Videos
"""

import os
import sys
import json
import logging
from datetime import datetime

from sheets_manager import SheetsManager
from video_downloader import download_video, get_channel_latest_videos, detect_platform
from video_editor import process_video

# ---------------------------------------------------------------------------
# Config - CẬP NHẬT SPREADSHEET_ID sau khi chạy setup_ggsheet.py
# ---------------------------------------------------------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "19gdA_7ZsOAvzBTlnXQCuIyUClZm9OQsrDm4TcB90mBA")

LOG_DIR = r"D:\Contenfactory\logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "orchestrator.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Luồng 1: Tự động quét kênh
# ---------------------------------------------------------------------------

def run_channel_scan(spreadsheet_id: str):
    """Scan all active channels for new videos and download them."""
    logger.info("=" * 60)
    logger.info("LUONG 1: Bat dau quet kenh tu dong")
    logger.info("=" * 60)

    mgr = SheetsManager(spreadsheet_id)
    channels = mgr.get_active_channels()
    logger.info(f"Tim thay {len(channels)} kenh active")

    total_downloaded = 0
    total_failed = 0

    for ch in channels:
        ch_link = ch["link"].strip()
        ch_topic = ch["topic"].strip() or "Uncategorized"
        ch_name = ch["name"]
        last_video_url = ch["last_video_url"].strip()

        if not ch_link:
            continue

        logger.info(f"\nQuet kenh: {ch_name} ({ch_link})")

        try:
            videos = get_channel_latest_videos(ch_link, max_count=10)
        except Exception as e:
            logger.error(f"  Loi khi quet kenh: {e}")
            mgr.update_channel_last_video(ch["row_index"], last_video_url, "Error")
            continue

        if not videos:
            logger.info("  Khong co video nao.")
            continue

        # Filter new videos (not seen before)
        new_videos = []
        for v in videos:
            if v["url"] and v["url"] != last_video_url:
                new_videos.append(v)
            else:
                break  # Assume list is newest-first; stop at known video

        logger.info(f"  Tim thay {len(new_videos)} video moi")

        for v in new_videos:
            url = v["url"]
            if not url:
                continue

            result = download_video(url, topic=ch_topic, video_id=v.get("id"))

            if result["success"]:
                total_downloaded += 1
                # Add to Videos sheet
                # Xử lý video (anti-copyright + dịch + AI metadata)
                edit_result = process_video(
                    result["file_path"],
                    topic=ch_topic,
                    platform="tiktok",
                    mode="full"
                )
                edited_path = edit_result.get("edited_path") or result["file_path"]
                metadata = edit_result.get("metadata", {})

                mgr.add_video_row(
                    link=url,
                    platform=detect_platform(url),
                    topic=ch_topic,
                    status="Success",
                    file_path=edited_path,
                )
            else:
                total_failed += 1
                mgr.add_video_row(
                    link=url,
                    platform=detect_platform(url),
                    topic=ch_topic,
                    status="Failed",
                    file_path="",
                )

        # Update Last Video URL with the newest video
        if new_videos:
            newest_url = new_videos[0]["url"]
            mgr.update_channel_last_video(ch["row_index"], newest_url, "Active")

    logger.info(f"\nKet qua: {total_downloaded} thanh cong, {total_failed} that bai")
    return {"downloaded": total_downloaded, "failed": total_failed}


# ---------------------------------------------------------------------------
# Luồng 2: Xử lý video thủ công
# ---------------------------------------------------------------------------

def run_manual_download(spreadsheet_id: str):
    """Process all Pending videos in the Videos tab."""
    logger.info("=" * 60)
    logger.info("LUONG 2: Xu ly video thu cong")
    logger.info("=" * 60)

    mgr = SheetsManager(spreadsheet_id)
    pending = mgr.get_pending_videos()
    logger.info(f"Tim thay {len(pending)} video dang cho xu ly")

    total_downloaded = 0
    total_failed = 0

    for vid in pending:
        url = vid["link"].strip()
        topic = vid["topic"].strip() or "Uncategorized"
        row_index = vid["row_index"]

        if not url:
            mgr.update_video_status(row_index, "Failed", "")
            continue

        logger.info(f"\nTai video: {url}")

        # Mark as Processing
        mgr.update_video_status(row_index, "Processing", "")

        result = download_video(url, topic=topic)

        if result["success"]:
            # Xử lý video sau khi tải
            edit_result = process_video(
                result["file_path"],
                topic=topic,
                platform="tiktok",
                mode="full"
            )
            edited_path = edit_result.get("edited_path") or result["file_path"]
            mgr.update_video_status(row_index, "Success", edited_path)
            total_downloaded += 1
        else:
            mgr.update_video_status(row_index, "Failed", result.get("error", ""))
            total_failed += 1

    logger.info(f"\nKet qua: {total_downloaded} thanh cong, {total_failed} that bai")
    return {"downloaded": total_downloaded, "failed": total_failed}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Content Factory Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["channels", "videos", "all"],
        default="all",
        help="channels=Luong 1, videos=Luong 2, all=ca hai",
    )
    parser.add_argument("--spreadsheet-id", default=SPREADSHEET_ID,
                        help="Google Spreadsheet ID")
    args = parser.parse_args()

    sid = args.spreadsheet_id
    if sid == "YOUR_SPREADSHEET_ID_HERE":
        logger.error("Chua cau hinh SPREADSHEET_ID. Sua trong orchestrator.py hoac truyen --spreadsheet-id")
        sys.exit(1)

    results = {}
    if args.mode in ("channels", "all"):
        results["channels"] = run_channel_scan(sid)
    if args.mode in ("videos", "all"):
        results["videos"] = run_manual_download(sid)

    print(json.dumps(results, ensure_ascii=False, indent=2))
