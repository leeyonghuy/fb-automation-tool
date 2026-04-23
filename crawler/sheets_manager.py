#!/usr/bin/env python3
"""
Google Sheets Manager - Content Factory
Handles read/write operations for Channels and Videos tabs.
"""

import os
import sys
import json
import logging
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = r"D:\Contenfactory\API\nha-may-content-208dc5165e29.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column indices (0-based) for Channels sheet
# Platform | Channel Link | Channel Name | Topic | Last Video URL | Status
COL_CH_PLATFORM = 0
COL_CH_LINK = 1
COL_CH_NAME = 2
COL_CH_TOPIC = 3
COL_CH_LAST_VIDEO = 4
COL_CH_STATUS = 5

# Column indices (0-based) for Videos sheet
# Video Link | Platform | Topic | Download Status | File Path | Created At
COL_VID_LINK = 0
COL_VID_PLATFORM = 1
COL_VID_TOPIC = 2
COL_VID_STATUS = 3
COL_VID_PATH = 4
COL_VID_CREATED = 5


class SheetsManager:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        self.service = build("sheets", "v4", credentials=creds)
        self.sheets = self.service.spreadsheets()

    # -----------------------------------------------------------------------
    # Generic helpers
    # -----------------------------------------------------------------------

    def read_range(self, range_name: str) -> list:
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id, range=range_name
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            logger.error(f"Error reading {range_name}: {e}")
            return []

    def write_range(self, range_name: str, values: list) -> bool:
        try:
            self.sheets.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": values},
            ).execute()
            return True
        except HttpError as e:
            logger.error(f"Error writing {range_name}: {e}")
            return False

    def append_row(self, sheet_name: str, values: list) -> bool:
        try:
            self.sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            ).execute()
            return True
        except HttpError as e:
            logger.error(f"Error appending to {sheet_name}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Channels tab
    # -----------------------------------------------------------------------

    def get_active_channels(self) -> list:
        """Return list of active channels (Status != 'Disabled')."""
        rows = self.read_range("Channels!A2:F")
        channels = []
        for i, row in enumerate(rows):
            # Pad row to 6 cols
            row = row + [""] * (6 - len(row))
            status = row[COL_CH_STATUS].strip().lower()
            if status != "disabled":
                channels.append({
                    "row_index": i + 2,  # 1-based, skipping header
                    "platform": row[COL_CH_PLATFORM],
                    "link": row[COL_CH_LINK],
                    "name": row[COL_CH_NAME],
                    "topic": row[COL_CH_TOPIC],
                    "last_video_url": row[COL_CH_LAST_VIDEO],
                    "status": row[COL_CH_STATUS],
                })
        return channels

    def update_channel_last_video(self, row_index: int, last_video_url: str, status: str = "Active") -> bool:
        """Update Last Video URL and Status for a channel row."""
        range_name = f"Channels!E{row_index}:F{row_index}"
        return self.write_range(range_name, [[last_video_url, status]])

    # -----------------------------------------------------------------------
    # Videos tab
    # -----------------------------------------------------------------------

    def get_pending_videos(self) -> list:
        """Return list of videos with Download Status == 'Pending'."""
        rows = self.read_range("Videos!A2:F")
        videos = []
        for i, row in enumerate(rows):
            row = row + [""] * (6 - len(row))
            status = row[COL_VID_STATUS].strip().lower()
            if status == "pending":
                videos.append({
                    "row_index": i + 2,
                    "link": row[COL_VID_LINK],
                    "platform": row[COL_VID_PLATFORM],
                    "topic": row[COL_VID_TOPIC],
                    "status": row[COL_VID_STATUS],
                    "file_path": row[COL_VID_PATH],
                    "created_at": row[COL_VID_CREATED],
                })
        return videos

    def update_video_status(self, row_index: int, status: str, file_path: str = "") -> bool:
        """Update Download Status and File Path for a video row."""
        range_name = f"Videos!D{row_index}:E{row_index}"
        return self.write_range(range_name, [[status, file_path]])

    def add_video_row(self, link: str, platform: str, topic: str,
                      status: str = "Pending", file_path: str = "") -> bool:
        """Append a new video row to the Videos sheet."""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.append_row("Videos", [link, platform, topic, status, file_path, created_at])


# ---------------------------------------------------------------------------
# CLI - for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sheets Manager CLI")
    parser.add_argument("spreadsheet_id", help="Google Spreadsheet ID")
    parser.add_argument("--action", choices=["list-channels", "list-pending"], required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    mgr = SheetsManager(args.spreadsheet_id)

    if args.action == "list-channels":
        channels = mgr.get_active_channels()
        print(json.dumps(channels, ensure_ascii=False, indent=2))
    elif args.action == "list-pending":
        videos = mgr.get_pending_videos()
        print(json.dumps(videos, ensure_ascii=False, indent=2))
