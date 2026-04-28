"""
status_tracker.py - ContenFactory Status Tracking System
Ghi/đọc trạng thái tất cả tasks vào SQLite DB
Dùng chung cho: crawler, video_editor, fb_warmup, tiktok_post, boxphone
"""

import sqlite3
import json
import time
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = r"D:\Contenfactory\status.db"

# ─────────────────────────────────────────────
# DB Setup
# ─────────────────────────────────────────────

def init_db():
    """Khởi tạo database và các bảng."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     TEXT UNIQUE NOT NULL,
            task_type   TEXT NOT NULL,
            name        TEXT,
            status      TEXT DEFAULT 'pending',
            progress    INTEGER DEFAULT 0,
            message     TEXT,
            input_data  TEXT,
            output_data TEXT,
            created_at  REAL,
            updated_at  REAL,
            finished_at REAL
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     TEXT,
            level       TEXT DEFAULT 'info',
            message     TEXT,
            timestamp   REAL
        );

        CREATE TABLE IF NOT EXISTS system_status (
            service     TEXT PRIMARY KEY,
            status      TEXT DEFAULT 'unknown',
            detail      TEXT,
            checked_at  REAL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
        CREATE INDEX IF NOT EXISTS idx_log_task ON activity_log(task_id);
        CREATE INDEX IF NOT EXISTS idx_log_time ON activity_log(timestamp);
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─────────────────────────────────────────────
# Task Management
# ─────────────────────────────────────────────

def create_task(task_id: str, task_type: str, name: str = "", input_data: dict = None) -> str:
    """Tạo task mới. Trả về task_id."""
    now = time.time()
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO tasks
            (task_id, task_type, name, status, progress, message, input_data, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', 0, 'Đang chờ...', ?, ?, ?)
        """, (task_id, task_type, name,
              json.dumps(input_data or {}, ensure_ascii=False),
              now, now))
    log(task_id, f"Task tạo: [{task_type}] {name}", "info")
    return task_id


def update_task(task_id: str, status: str = None, progress: int = None,
                message: str = None, output_data: dict = None):
    """Cập nhật trạng thái task."""
    now = time.time()
    fields = ["updated_at = ?"]
    values = [now]

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if progress is not None:
        fields.append("progress = ?")
        values.append(min(100, max(0, progress)))
    if message is not None:
        fields.append("message = ?")
        values.append(message)
    if output_data is not None:
        fields.append("output_data = ?")
        values.append(json.dumps(output_data, ensure_ascii=False))
    if status in ("done", "error", "cancelled"):
        fields.append("finished_at = ?")
        values.append(now)

    values.append(task_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?", values)

    if message:
        log(task_id, message, "error" if status == "error" else "info")


def finish_task(task_id: str, success: bool, message: str = "", output_data: dict = None):
    """Hoàn thành task."""
    update_task(
        task_id,
        status="done" if success else "error",
        progress=100 if success else None,
        message=message or ("✅ Hoàn thành" if success else "❌ Thất bại"),
        output_data=output_data
    )


def get_task(task_id: str) -> dict:
    """Lấy thông tin 1 task."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else {}


def get_tasks(status: str = None, task_type: str = None, limit: int = 50) -> list:
    """Lấy danh sách tasks."""
    query = "SELECT * FROM tasks"
    conditions = []
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if task_type:
        conditions.append("task_type = ?")
        params.append(task_type)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_active_tasks() -> list:
    """Lấy tasks đang chạy (pending + running)."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM tasks
            WHERE status IN ('pending', 'running')
            ORDER BY created_at ASC
        """).fetchall()
        return [dict(r) for r in rows]


def get_recent_tasks(limit: int = 20) -> list:
    """Lấy tasks gần đây nhất."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM tasks
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Activity Log
# ─────────────────────────────────────────────

def log(task_id: str, message: str, level: str = "info"):
    """Ghi log activity."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO activity_log (task_id, level, message, timestamp)
            VALUES (?, ?, ?, ?)
        """, (task_id, level, message, time.time()))


def get_recent_logs(limit: int = 50, task_id: str = None) -> list:
    """Lấy logs gần đây."""
    if task_id:
        query = "SELECT * FROM activity_log WHERE task_id = ? ORDER BY timestamp DESC LIMIT ?"
        params = (task_id, limit)
    else:
        query = "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?"
        params = (limit,)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["time_str"] = datetime.fromtimestamp(d["timestamp"]).strftime("%H:%M:%S")
            result.append(d)
        return result


# ─────────────────────────────────────────────
# System Status
# ─────────────────────────────────────────────

def update_service_status(service: str, status: str, detail: str = ""):
    """Cập nhật trạng thái service (ixbrowser, adb, ffmpeg, gemini...)."""
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO system_status (service, status, detail, checked_at)
            VALUES (?, ?, ?, ?)
        """, (service, status, detail, time.time()))


def get_all_service_status() -> dict:
    """Lấy trạng thái tất cả services."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM system_status").fetchall()
        return {r["service"]: dict(r) for r in rows}


def check_all_services():
    """Kiểm tra và cập nhật trạng thái tất cả services."""
    import subprocess

    # Check FFmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            ver = result.stdout.decode()[:50].split('\n')[0]
            update_service_status("ffmpeg", "ok", ver)
        else:
            update_service_status("ffmpeg", "error", "ffmpeg lỗi")
    except Exception:
        update_service_status("ffmpeg", "offline", "ffmpeg chưa cài")

    # Check VieNeu TTS
    try:
        import sys
        sys.path.insert(0, r"D:\Contenfactory\crawler")
        from tts_engine import is_available
        if is_available():
            update_service_status("tts", "ok", "VieNeu-TTS sẵn sàng")
        else:
            update_service_status("tts", "error", "TTS chưa load model")
    except Exception:
        update_service_status("tts", "offline", "tts_engine chưa cài")

    # Check Gemini API
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        update_service_status("gemini", "ok", "API key đã cấu hình")
    else:
        update_service_status("gemini", "warning", "Chưa set GEMINI_API_KEY")


# ─────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────

def get_stats() -> dict:
    """Thống kê tổng quan."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
        error = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='error'").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending','running')").fetchone()[0]

        # Today stats
        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        today_done = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='done' AND finished_at > ?",
            (today_start,)
        ).fetchone()[0]

        return {
            "total": total,
            "done": done,
            "error": error,
            "running": running,
            "today_done": today_done
        }


# ─────────────────────────────────────────────
# Helper: Task ID generator
# ─────────────────────────────────────────────

def make_task_id(prefix: str = "task") -> str:
    """Tạo task ID unique."""
    import uuid
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}"


# ─────────────────────────────────────────────
# Init on import
# ─────────────────────────────────────────────

init_db()


if __name__ == "__main__":
    print("=== Status Tracker Test ===")
    check_all_services()
    services = get_all_service_status()
    for name, info in services.items():
        icon = "✅" if info["status"] == "ok" else ("⚠️" if info["status"] == "warning" else "❌")
        print(f"  {icon} {name}: {info['detail']}")

    # Test task
    tid = make_task_id("test")
    create_task(tid, "video", "Test video.mp4", {"url": "https://example.com"})
    update_task(tid, status="running", progress=50, message="Đang xử lý...")
    finish_task(tid, True, "Xong!", {"output": "test_edited.mp4"})

    stats = get_stats()
    print(f"\nStats: {stats}")
    print("\nRecent logs:")
    for l in get_recent_logs(5):
        print(f"  [{l['time_str']}] {l['message']}")
