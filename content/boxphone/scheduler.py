"""
scheduler.py
Lên lịch đăng bài TikTok tự động.
- Tạo schedule: thiết bị + video + giờ đăng
- Background thread kiểm tra và chạy đúng giờ
- Hỗ trợ lặp lại hàng ngày
"""

import json
import os
import time
import threading
import datetime
from typing import List, Dict, Optional

DATA_FILE = os.path.join(os.path.dirname(__file__), "devices.json")
_scheduler_thread = None
_scheduler_running = False
_scheduler_lock = threading.Lock()


def _load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devices": [], "accounts": [], "proxies": [], "schedules": [], "content_library": []}


def _save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _ensure_key(data: dict, key: str, default):
    if key not in data:
        data[key] = default


# ─── SCHEDULE CRUD ────────────────────────────────────────────────────────────

def add_schedule(serial: str, video_path: str, caption: str = "",
                 hashtags: list = None, product_name: str = None,
                 product_link: str = None, schedule_time: str = None,
                 repeat_daily: bool = False, note: str = "") -> Dict:
    """
    Thêm lịch đăng bài.
    schedule_time: "HH:MM" hoặc "YYYY-MM-DD HH:MM"
    """
    data = _load_data()
    _ensure_key(data, "schedules", [])

    sched_id = f"sched_{int(time.time())}_{len(data['schedules'])}"
    schedule = {
        "id": sched_id,
        "serial": serial,
        "video_path": video_path,
        "caption": caption,
        "hashtags": hashtags or [],
        "product_name": product_name,
        "product_link": product_link,
        "schedule_time": schedule_time,  # "HH:MM" hoặc "YYYY-MM-DD HH:MM"
        "repeat_daily": repeat_daily,
        "note": note,
        "status": "pending",  # pending / running / done / failed / cancelled
        "created_at": datetime.datetime.now().isoformat(),
        "last_run": None,
        "next_run": _calc_next_run(schedule_time, repeat_daily),
        "run_count": 0,
        "error": ""
    }
    data["schedules"].append(schedule)
    _save_data(data)
    return schedule


def _calc_next_run(schedule_time: str, repeat_daily: bool) -> Optional[str]:
    """Tính thời điểm chạy tiếp theo"""
    if not schedule_time:
        return None
    now = datetime.datetime.now()
    try:
        if len(schedule_time) == 5:  # "HH:MM"
            t = datetime.datetime.strptime(schedule_time, "%H:%M")
            next_run = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += datetime.timedelta(days=1)
        else:  # "YYYY-MM-DD HH:MM"
            next_run = datetime.datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
        return next_run.isoformat()
    except Exception:
        return None


def get_all_schedules() -> List[Dict]:
    data = _load_data()
    _ensure_key(data, "schedules", [])
    return data.get("schedules", [])


def get_schedule(sched_id: str) -> Optional[Dict]:
    for s in get_all_schedules():
        if s["id"] == sched_id:
            return s
    return None


def update_schedule(sched_id: str, **kwargs) -> bool:
    data = _load_data()
    _ensure_key(data, "schedules", [])
    for s in data["schedules"]:
        if s["id"] == sched_id:
            s.update(kwargs)
            _save_data(data)
            return True
    return False


def remove_schedule(sched_id: str) -> bool:
    data = _load_data()
    _ensure_key(data, "schedules", [])
    before = len(data["schedules"])
    data["schedules"] = [s for s in data["schedules"] if s["id"] != sched_id]
    if len(data["schedules"]) < before:
        _save_data(data)
        return True
    return False


def cancel_schedule(sched_id: str) -> bool:
    return update_schedule(sched_id, status="cancelled")


# ─── SCHEDULER ENGINE ─────────────────────────────────────────────────────────

def _run_schedule(schedule: Dict):
    """Thực thi 1 schedule"""
    from tiktok_post import upload_video_full
    sched_id = schedule["id"]
    serial = schedule["serial"]

    print(f"[SCHEDULER] Chạy schedule {sched_id}: {serial} → {schedule['video_path']}")
    update_schedule(sched_id, status="running", last_run=datetime.datetime.now().isoformat())

    try:
        result = upload_video_full(
            serial=serial,
            local_video_path=schedule["video_path"],
            caption=schedule.get("caption", ""),
            hashtags=schedule.get("hashtags", []),
            product_name=schedule.get("product_name"),
            product_link=schedule.get("product_link")
        )

        run_count = schedule.get("run_count", 0) + 1

        if result.get("success"):
            if schedule.get("repeat_daily"):
                # Tính next_run cho ngày mai
                next_run = _calc_next_run(schedule["schedule_time"], True)
                update_schedule(sched_id, status="pending", run_count=run_count,
                                next_run=next_run, error="")
                print(f"[SCHEDULER] ✓ Done, next run: {next_run}")
            else:
                update_schedule(sched_id, status="done", run_count=run_count, error="")
                print(f"[SCHEDULER] ✓ Done")
        else:
            update_schedule(sched_id, status="failed", run_count=run_count,
                            error=result.get("error", "Unknown error"))
            print(f"[SCHEDULER] ✗ Failed: {result.get('error')}")

    except Exception as e:
        update_schedule(sched_id, status="failed", error=str(e))
        print(f"[SCHEDULER] ✗ Exception: {e}")


def _scheduler_loop():
    """Background loop kiểm tra và chạy schedules"""
    global _scheduler_running
    print("[SCHEDULER] Started")
    while _scheduler_running:
        try:
            now = datetime.datetime.now()
            schedules = get_all_schedules()
            for sched in schedules:
                if sched["status"] not in ("pending",):
                    continue
                next_run = sched.get("next_run")
                if not next_run:
                    continue
                try:
                    next_dt = datetime.datetime.fromisoformat(next_run)
                    if now >= next_dt:
                        # Chạy trong thread riêng
                        t = threading.Thread(target=_run_schedule, args=(sched,), daemon=True)
                        t.start()
                except Exception:
                    continue
        except Exception as e:
            print(f"[SCHEDULER] Loop error: {e}")
        time.sleep(30)  # Kiểm tra mỗi 30 giây
    print("[SCHEDULER] Stopped")


def start_scheduler():
    """Khởi động scheduler background"""
    global _scheduler_thread, _scheduler_running
    with _scheduler_lock:
        if _scheduler_running:
            return
        _scheduler_running = True
        _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
        _scheduler_thread.start()


def stop_scheduler():
    """Dừng scheduler"""
    global _scheduler_running
    _scheduler_running = False


def get_scheduler_status() -> Dict:
    return {
        "running": _scheduler_running,
        "pending_count": len([s for s in get_all_schedules() if s["status"] == "pending"]),
        "done_count": len([s for s in get_all_schedules() if s["status"] == "done"]),
        "failed_count": len([s for s in get_all_schedules() if s["status"] == "failed"]),
    }
