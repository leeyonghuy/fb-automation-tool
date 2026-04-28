"""
publish_queue.py
Kết nối Google Sheet [Publish Queue] cho Layer 3 Distribution.

Sheet tab: "Publish Queue"
Columns (A-H):
  A: Video Path
  B: Page URL
  C: Post Type (post | reel)
  D: Caption/Content
  E: Status (queued | publishing | published | failed | skipped)
  F: Account UID
  G: Posted At
  H: Error

Cách dùng:
    from publish_queue import PublishQueueManager
    pq = PublishQueueManager(spreadsheet_id)
    tasks = pq.get_queued_tasks()
    pq.mark_publishing(row_index)
    pq.mark_published(row_index, fb_uid)
    pq.mark_failed(row_index, error_msg)
"""

import os
import sys
import time
from pathlib import Path

# Cho phép import config.py ở project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from config import GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID  # type: ignore
except ImportError:
    GOOGLE_CREDENTIALS_FILE = ""
    SPREADSHEET_ID = ""

SHEET_NAME = "Publish Queue"

# Column indices (0-based)
COL_VIDEO_PATH = 0
COL_PAGE_URL = 1
COL_POST_TYPE = 2
COL_CAPTION = 3
COL_STATUS = 4
COL_ACCOUNT_UID = 5
COL_POSTED_AT = 6
COL_ERROR = 7


class PublishQueueManager:
    def __init__(self, spreadsheet_id: str = ""):
        self.spreadsheet_id = spreadsheet_id or SPREADSHEET_ID
        if not self.spreadsheet_id:
            raise ValueError("[publish_queue] SPREADSHEET_ID chưa được cấu hình. Set env var SPREADSHEET_ID.")

        creds_file = GOOGLE_CREDENTIALS_FILE
        if not creds_file or not Path(creds_file).exists():
            raise FileNotFoundError(f"[publish_queue] Không tìm thấy credentials: {creds_file}")

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_file(
                creds_file,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            service = build("sheets", "v4", credentials=creds)
            self._sheets = service.spreadsheets()
        except ImportError:
            raise ImportError("[publish_queue] Cần cài: pip install google-api-python-client google-auth")

    # ─────────────────────────────────────────────
    # Read
    # ─────────────────────────────────────────────

    def get_queued_tasks(self) -> list:
        """
        Lấy tất cả task có status='queued' từ Sheet.
        Trả về list dict với row_index để update sau.
        """
        try:
            result = self._sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{SHEET_NAME}!A2:H"
            ).execute()
            rows = result.get("values", [])
        except Exception as e:
            print(f"[publish_queue] Lỗi đọc sheet: {e}")
            return []

        tasks = []
        for i, row in enumerate(rows):
            row = row + [""] * (8 - len(row))  # pad to 8 cols
            status = row[COL_STATUS].strip().lower()
            if status == "queued":
                tasks.append({
                    "row_index": i + 2,  # 1-based, skip header
                    "video_path": row[COL_VIDEO_PATH].strip(),
                    "page_url": row[COL_PAGE_URL].strip(),
                    "post_type": row[COL_POST_TYPE].strip() or "reel",
                    "caption": row[COL_CAPTION].strip(),
                    "status": row[COL_STATUS].strip(),
                    "account_uid": row[COL_ACCOUNT_UID].strip(),
                    "posted_at": row[COL_POSTED_AT].strip(),
                    "error": row[COL_ERROR].strip(),
                })
        print(f"[publish_queue] Tìm thấy {len(tasks)} task queued")
        return tasks

    def get_all_tasks(self, status_filter: str = "") -> list:
        """Lấy tất cả task, tùy chọn filter theo status."""
        try:
            result = self._sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{SHEET_NAME}!A2:H"
            ).execute()
            rows = result.get("values", [])
        except Exception as e:
            print(f"[publish_queue] Lỗi đọc sheet: {e}")
            return []

        tasks = []
        for i, row in enumerate(rows):
            row = row + [""] * (8 - len(row))
            status = row[COL_STATUS].strip().lower()
            if status_filter and status != status_filter.lower():
                continue
            tasks.append({
                "row_index": i + 2,
                "video_path": row[COL_VIDEO_PATH].strip(),
                "page_url": row[COL_PAGE_URL].strip(),
                "post_type": row[COL_POST_TYPE].strip() or "reel",
                "caption": row[COL_CAPTION].strip(),
                "status": status,
                "account_uid": row[COL_ACCOUNT_UID].strip(),
                "posted_at": row[COL_POSTED_AT].strip(),
                "error": row[COL_ERROR].strip(),
            })
        return tasks

    # ─────────────────────────────────────────────
    # Write
    # ─────────────────────────────────────────────

    def _update_row(self, row_index: int, values: list) -> bool:
        """Update columns E-H (status, account_uid, posted_at, error) cho 1 row."""
        range_name = f"{SHEET_NAME}!E{row_index}:H{row_index}"
        try:
            self._sheets.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": [values]}
            ).execute()
            return True
        except Exception as e:
            print(f"[publish_queue] Lỗi update row {row_index}: {e}")
            return False

    def mark_publishing(self, row_index: int, fb_uid: str = "") -> bool:
        """Đánh dấu task đang được xử lý."""
        return self._update_row(row_index, ["publishing", fb_uid, "", ""])

    def mark_published(self, row_index: int, fb_uid: str = "") -> bool:
        """Đánh dấu task đã đăng thành công."""
        posted_at = time.strftime("%Y-%m-%d %H:%M:%S")
        return self._update_row(row_index, ["published", fb_uid, posted_at, ""])

    def mark_failed(self, row_index: int, error_msg: str = "", fb_uid: str = "") -> bool:
        """Đánh dấu task thất bại."""
        posted_at = time.strftime("%Y-%m-%d %H:%M:%S")
        return self._update_row(row_index, ["failed", fb_uid, posted_at, error_msg[:200]])

    def mark_skipped(self, row_index: int, reason: str = "") -> bool:
        """Đánh dấu task bị bỏ qua (dedup, v.v.)."""
        return self._update_row(row_index, ["skipped", "", "", reason[:200]])

    def reset_to_queued(self, row_index: int) -> bool:
        """Reset task về queued để thử lại."""
        return self._update_row(row_index, ["queued", "", "", ""])

    def add_task(self, video_path: str, page_url: str,
                 post_type: str = "reel", caption: str = "") -> bool:
        """Thêm task mới vào queue."""
        try:
            self._sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{SHEET_NAME}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [[video_path, page_url, post_type, caption, "queued", "", "", ""]]}
            ).execute()
            print(f"[publish_queue] Đã thêm task: {video_path} → {page_url}")
            return True
        except Exception as e:
            print(f"[publish_queue] Lỗi thêm task: {e}")
            return False

    # ─────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Thống kê số task theo status."""
        tasks = self.get_all_tasks()
        from collections import Counter
        counts = Counter(t["status"] for t in tasks)
        return dict(counts)


# ─────────────────────────────────────────────
# Singleton helper
# ─────────────────────────────────────────────

_instance = None


def get_publish_queue(spreadsheet_id: str = "") -> PublishQueueManager:
    """Lấy singleton instance (lazy init)."""
    global _instance
    if _instance is None:
        _instance = PublishQueueManager(spreadsheet_id)
    return _instance
