"""
dashboard/app.py - ContenFactory Dashboard
Web UI giám sát tất cả hoạt động: Crawler, Video Editor, Facebook, BoxPhone
Chạy: python app.py → mở http://localhost:5555
"""

import sys
import os
import json
import time
import threading
import glob
from concurrent.futures import ThreadPoolExecutor
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, url_for

sys.path.insert(0, r"D:\Contenfactory")
sys.path.insert(0, r"D:\Contenfactory\crawler")
sys.path.insert(0, r"D:\Contenfactory\content\boxphone")
sys.path.insert(0, r"D:\Contenfactory\content\nuoiaccfb")

try:
    from config import BASE_VIDEO_DIR, EDITED_VIDEO_DIR, SPREADSHEET_ID, LOG_DIR
except Exception:
    BASE_VIDEO_DIR = r"D:\Videos"
    EDITED_VIDEO_DIR = r"D:\Videos\Edited"
    SPREADSHEET_ID = ""
    LOG_DIR = r"D:\Contenfactory\logs"

import status_tracker as st

app = Flask(__name__)
app.secret_key = "contenfactory_2026"
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# Task queue: tối đa 2 task chạy song song, task thứ 3+ xếp hàng đợi
task_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline")
# Tracking futures để có thể cancel
_task_futures = {}  # task_id -> Future

# ─────────────────────────────────────────────
# Background service checker
# ─────────────────────────────────────────────

def service_check_loop():
    """Chạy background, check services mỗi 30 giây."""
    while True:
        try:
            st.check_all_services()
        except Exception:
            pass
        time.sleep(30)

threading.Thread(target=service_check_loop, daemon=True).start()


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    """API trả về toàn bộ trạng thái cho dashboard."""
    try:
        stats = st.get_stats()
        services = st.get_all_service_status()
        active_tasks = st.get_active_tasks()
        recent_tasks = st.get_recent_tasks(20)
        recent_logs = st.get_recent_logs(30)

        # Format tasks
        def fmt_task(t):
            t = dict(t)
            if t.get("created_at"):
                t["created_str"] = datetime.fromtimestamp(t["created_at"]).strftime("%H:%M:%S")
            if t.get("updated_at"):
                t["updated_str"] = datetime.fromtimestamp(t["updated_at"]).strftime("%H:%M:%S")
            if t.get("finished_at"):
                t["finished_str"] = datetime.fromtimestamp(t["finished_at"]).strftime("%H:%M:%S")
            # Parse output_data
            try:
                t["output_data"] = json.loads(t.get("output_data") or "{}")
            except Exception:
                t["output_data"] = {}
            return t

        return jsonify({
            "ok": True,
            "stats": stats,
            "services": services,
            "active_tasks": [fmt_task(t) for t in active_tasks],
            "recent_tasks": [fmt_task(t) for t in recent_tasks],
            "recent_logs": recent_logs,
            "server_time": datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/tasks")
def api_tasks():
    """Lấy tasks theo filter."""
    status = request.args.get("status")
    task_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    tasks = st.get_tasks(status=status, task_type=task_type, limit=limit)
    return jsonify({"ok": True, "tasks": tasks, "count": len(tasks)})


@app.route("/api/logs")
def api_logs():
    """Lấy activity logs."""
    limit = int(request.args.get("limit", 50))
    task_id = request.args.get("task_id")
    logs = st.get_recent_logs(limit=limit, task_id=task_id)
    return jsonify({"ok": True, "logs": logs})


@app.route("/api/check_services")
def api_check_services():
    """Trigger check services ngay lập tức."""
    threading.Thread(target=st.check_all_services, daemon=True).start()
    return jsonify({"ok": True, "message": "Đang kiểm tra..."})


@app.route("/api/pipeline/download", methods=["POST"])
def api_pipeline_download():
    """Tải video từ URL (hỗ trợ nhiều URL, mỗi dòng 1 link)."""
    data = request.json or {}
    raw_url = data.get("url", "").strip()
    topic = data.get("topic", "Uncategorized")
    quality = data.get("quality", "best")

    if not raw_url:
        return jsonify({"ok": False, "error": "Thiếu URL"})

    # Hỗ trợ nhiều URL (mỗi dòng 1 link)
    urls = [u.strip() for u in raw_url.replace(",", "\n").split("\n") if u.strip()]
    if not urls:
        return jsonify({"ok": False, "error": "Không có URL hợp lệ"})

    task_ids = []
    for url in urls:
        task_id = st.make_task_id("download")
        st.create_task(task_id, "download", f"Tải: {url[:50]}", {"url": url, "topic": topic, "quality": quality})

        def run(u=url, tid=task_id, q=quality):
            try:
                st.update_task(tid, status="running", progress=10, message=f"Đang tải [{q}]...")
                from video_downloader import download_video

                def on_progress(pct, msg):
                    st.update_task(tid, progress=pct, message=msg)

                result = download_video(u, topic, quality=q, progress_callback=on_progress)
                if result.get("success"):
                    fp = result.get("file_path") or result.get("filename") or ""
                    st.finish_task(tid, True, f"✅ Tải xong: {os.path.basename(fp)}", result)
                else:
                    st.finish_task(tid, False, f"❌ Lỗi: {result.get('error', 'Unknown')}")
            except Exception as e:
                st.finish_task(tid, False, f"❌ Exception: {str(e)}")

        _task_futures[task_id] = task_executor.submit(run)
        task_ids.append(task_id)

    msg = f"Đang tải {len(urls)} video [{quality}]..." if len(urls) > 1 else "Đang tải..."
    return jsonify({"ok": True, "task_id": task_ids[0], "task_ids": task_ids,
                    "count": len(urls), "message": msg})


@app.route("/api/pipeline/process", methods=["POST"])
def api_pipeline_process():
    """Xử lý video (anti-CP + dịch + TTS)."""
    data = request.json or {}
    input_path = data.get("input_path", "").strip()
    mode = data.get("mode", "full")
    topic = data.get("topic", "Uncategorized")

    if not input_path:
        return jsonify({"ok": False, "error": "Thiếu đường dẫn video"})

    task_id = st.make_task_id("process")
    name = os.path.basename(input_path)
    st.create_task(task_id, "video", f"Xử lý: {name}", {"input": input_path, "mode": mode})

    def run():
        try:
            st.update_task(task_id, status="running", progress=5, message="Bắt đầu xử lý...")
            from video_editor import process_video
            result = process_video(input_path, topic=topic, mode=mode)
            if result.get("success"):
                st.finish_task(task_id, True,
                               f"✅ Xong: {os.path.basename(result.get('edited_path', ''))}",
                               result)
            else:
                st.finish_task(task_id, False, f"❌ Lỗi: {result.get('error', 'Unknown')}")
        except Exception as e:
            st.finish_task(task_id, False, f"❌ Exception: {str(e)}")

    _task_futures[task_id] = task_executor.submit(run)
    return jsonify({"ok": True, "task_id": task_id, "message": "Đang xử lý..."})


@app.route("/api/pipeline/auto", methods=["POST"])
def api_pipeline_auto():
    """Auto pipeline: Tải + Xử lý + Metadata."""
    data = request.json or {}
    url = data.get("url", "").strip()
    topic = data.get("topic", "Uncategorized")

    if not url:
        return jsonify({"ok": False, "error": "Thiếu URL"})

    task_id = st.make_task_id("auto")
    st.create_task(task_id, "auto", f"Auto: {url[:50]}", {"url": url, "topic": topic})

    def run():
        try:
            # Bước 1: Tải
            st.update_task(task_id, status="running", progress=10, message="[1/3] Đang tải video...")
            from video_downloader import download_video
            dl = download_video(url, topic)
            if not dl.get("success"):
                st.finish_task(task_id, False, f"❌ Tải thất bại: {dl.get('error')}")
                return

            video_path = dl.get("file_path") or dl.get("output_path", "")
            st.update_task(task_id, progress=35, message=f"[2/3] Đang xử lý video...")

            # Bước 2: Xử lý
            from video_editor import process_video
            proc = process_video(video_path, topic=topic, mode="full")
            if not proc.get("success"):
                st.finish_task(task_id, False, f"❌ Xử lý thất bại: {proc.get('error')}")
                return

            st.update_task(task_id, progress=90, message="[3/3] Tạo metadata AI...")

            # Bước 3: Metadata đã được tạo trong process_video
            metadata = proc.get("metadata", {})
            st.finish_task(task_id, True,
                           f"✅ Hoàn thành! Title: {metadata.get('title', '')[:40]}",
                           {"video": proc.get("edited_path"), "metadata": metadata})

        except Exception as e:
            st.finish_task(task_id, False, f"❌ Exception: {str(e)}")

    _task_futures[task_id] = task_executor.submit(run)
    return jsonify({"ok": True, "task_id": task_id, "message": "Auto pipeline đang chạy..."})


@app.route("/api/task/<task_id>")
def api_task_detail(task_id):
    """Chi tiết 1 task."""
    task = st.get_task(task_id)
    logs = st.get_recent_logs(20, task_id=task_id)
    return jsonify({"ok": True, "task": task, "logs": logs})


@app.route("/api/task/<task_id>/cancel", methods=["POST"])
def api_task_cancel(task_id):
    """Hủy task đang chạy hoặc đang chờ."""
    future = _task_futures.get(task_id)
    if future and not future.done():
        cancelled = future.cancel()  # Chỉ cancel được task đang queued
        if cancelled:
            st.finish_task(task_id, False, "⏹️ Đã hủy (chưa chạy)")
            return jsonify({"ok": True, "message": "Task đã hủy"})
        else:
            # Task đang chạy - đánh dấu cancel, thread sẽ tự dừng
            st.finish_task(task_id, False, "⏹️ Đã dừng bởi người dùng")
            return jsonify({"ok": True, "message": "Task đã đánh dấu dừng"})
    else:
        # Task đã xong hoặc không tìm thấy
        st.finish_task(task_id, False, "⏹️ Đã dừng")
        return jsonify({"ok": True, "message": "Task đã dừng"})


# ---------------------------------------------------------------------------
# New Layer 2 endpoints
# ---------------------------------------------------------------------------

def _scan_videos(base_dir, max_files=200):
    """Scan directory for video files recursively."""
    videos = []
    if not os.path.isdir(base_dir):
        return videos
    for root, dirs, files in os.walk(base_dir):
        for f in sorted(files):
            if f.lower().endswith(('.mp4', '.mkv', '.webm', '.avi')):
                full = os.path.join(root, f)
                try:
                    stat = os.stat(full)
                    videos.append({
                        "name": f,
                        "path": full,
                        "size_mb": round(stat.st_size / 1024 / 1024, 1),
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m %H:%M"),
                        "modified_ts": stat.st_mtime,
                        "rel_path": os.path.relpath(full, base_dir),
                    })
                except OSError:
                    pass
            if len(videos) >= max_files:
                break
        if len(videos) >= max_files:
            break
    return sorted(videos, key=lambda x: x.get("modified_ts", 0), reverse=True)


@app.route("/api/videos/list")
def api_videos_list():
    """List downloaded and processed videos."""
    try:
        downloaded = _scan_videos(BASE_VIDEO_DIR)
        processed = _scan_videos(EDITED_VIDEO_DIR)
        return jsonify({
            "ok": True,
            "downloaded": downloaded,
            "processed": processed,
            "download_dir": BASE_VIDEO_DIR,
            "edited_dir": EDITED_VIDEO_DIR,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/pipeline/translate", methods=["POST"])
def api_pipeline_translate():
    """Whisper-based translation pipeline (DICH_V2 engine)."""
    data = request.json or {}
    input_path = data.get("input_path", "").strip()
    model = data.get("model", "base")
    tts = data.get("tts", "edge")
    lang_src = data.get("lang_src", "zh")
    keep_original = data.get("keep_original_audio", False)
    edge_voice = data.get("edge_voice", "vi-VN-NamMinhNeural")

    if not input_path or not os.path.isfile(input_path):
        return jsonify({"ok": False, "error": f"File không tồn tại: {input_path}"})

    task_id = st.make_task_id("translate")
    name = os.path.basename(input_path)
    st.create_task(task_id, "translate",
                   f"Dịch: {name[:40]}",
                   {"input": input_path, "model": model, "tts": tts})

    def run():
        try:
            st.update_task(task_id, status="running", progress=5,
                           message=f"Whisper ({model}) + {tts} TTS...")
            # Import DICH_V2 functions
            sys.path.insert(0, r"D:\Contenfactory")
            from DICH_V2 import (
                process_video as dich_process,
                setup_logging, find_ffmpeg,
                import_or_install,
            )
            log_dir = Path(LOG_DIR)
            log = setup_logging(log_dir)
            ffmpeg = find_ffmpeg(log)

            # Eager-import core deps
            import_or_install("torch")
            import_or_install("whisper", "openai-whisper")
            import_or_install("pydub")
            import_or_install("deep_translator", "deep-translator")
            if tts == "edge":
                import_or_install("edge_tts", "edge-tts")

            output_dir = EDITED_VIDEO_DIR
            os.makedirs(output_dir, exist_ok=True)

            args = Namespace(
                model=model, lang_src=lang_src, tts=tts,
                edge_voice=edge_voice,
                vieneu_voice="Xuân Vĩnh",
                keep_original_audio=keep_original,
                orig_volume_db=-20.0,
                no_burn_sub=False,
                no_resume=False,
            )

            out = dich_process(input_path, output_dir, ffmpeg, args, log, task_id)
            if out:
                st.finish_task(task_id, True,
                               f"✅ Dịch xong: {os.path.basename(out)}",
                               {"output": out})
            else:
                st.finish_task(task_id, False, "❌ Dịch thất bại")
        except Exception as e:
            st.finish_task(task_id, False, f"❌ Exception: {str(e)}")

    _task_futures[task_id] = task_executor.submit(run)
    return jsonify({"ok": True, "task_id": task_id, "message": "Đang dịch..."})


@app.route("/api/pipeline/channel-scan", methods=["POST"])
def api_channel_scan():
    """Trigger orchestrator channel scan."""
    sid = SPREADSHEET_ID
    if not sid:
        return jsonify({"ok": False, "error": "Chưa cấu hình SPREADSHEET_ID trong .env"})

    task_id = st.make_task_id("scan")
    st.create_task(task_id, "channel_scan", "Quét kênh tự động", {"spreadsheet_id": sid})

    def run():
        try:
            st.update_task(task_id, status="running", progress=10,
                           message="Đang quét kênh từ Google Sheet...")
            from orchestrator import run_channel_scan
            result = run_channel_scan(sid)
            dl = result.get("downloaded", 0)
            fail = result.get("failed", 0)
            st.finish_task(task_id, True,
                           f"✅ Quét xong: {dl} tải, {fail} lỗi",
                           result)
        except Exception as e:
            st.finish_task(task_id, False, f"❌ Exception: {str(e)}")

    _task_futures[task_id] = task_executor.submit(run)
    return jsonify({"ok": True, "task_id": task_id, "message": "Đang quét kênh..."})


@app.route("/api/queue-status")
def api_queue_status():
    """Trạng thái hàng đợi task."""
    pending = task_executor._work_queue.qsize()
    active = len([t for t in task_executor._threads if t.is_alive()]) if task_executor._threads else 0
    # Ước lượng: active threads - idle = đang chạy thực tế
    return jsonify({
        "ok": True,
        "max_workers": 2,
        "queued": pending,
        "message": f"Hàng đợi: {pending} task đang chờ" if pending else "Sẵn sàng"
    })


@app.route("/api/config")
def api_config():
    """Show current configuration status."""
    try:
        from config import (
            SPREADSHEET_ID as SID, GEMINI_API_KEY, FFMPEG_CMD, FFPROBE_CMD,
            BASE_VIDEO_DIR as BVD, EDITED_VIDEO_DIR as EVD,
            GOOGLE_CREDENTIALS_FILE, ROUTER_BASE,
        )
        return jsonify({"ok": True, "config": {
            "spreadsheet_id": bool(SID),
            "gemini_api_key": bool(GEMINI_API_KEY),
            "ffmpeg": FFMPEG_CMD,
            "ffprobe": FFPROBE_CMD,
            "base_video_dir": BVD,
            "edited_video_dir": EVD,
            "google_credentials": os.path.exists(GOOGLE_CREDENTIALS_FILE),
            "router_base": ROUTER_BASE,
        }})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/task-stats")
def api_task_stats():
    """Thống kê task theo ngày (7 ngày gần nhất)."""
    try:
        from collections import Counter
        all_tasks = st.get_tasks(limit=500)
        day_done = Counter()
        day_err = Counter()
        for t in all_tasks:
            ts = t.get("updated") or t.get("created", "")
            if not ts:
                continue
            day = ts[:10]  # YYYY-MM-DD
            if t.get("status") == "done":
                day_done[day] += 1
            elif t.get("status") == "error":
                day_err[day] += 1
        # Last 7 days
        from datetime import timedelta
        days = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            days.append({"date": d, "done": day_done.get(d, 0), "error": day_err.get(d, 0)})
        return jsonify({"ok": True, "days": days})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/system-info")
def api_system_info():
    """Thông tin hệ thống: GPU, Whisper models, disk usage."""
    info = {"gpu": None, "whisper_models": [], "disk": {}}

    # GPU detection
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu"] = {
                "name": torch.cuda.get_device_name(0),
                "vram_gb": round(torch.cuda.get_device_properties(0).total_mem / 1024**3, 1),
                "device": "cuda",
            }
        else:
            info["gpu"] = {"name": "CPU only", "vram_gb": 0, "device": "cpu"}
    except ImportError:
        info["gpu"] = {"name": "PyTorch chưa cài", "vram_gb": 0, "device": "cpu"}

    # Whisper model status
    whisper_models = {
        "tiny": {"size_mb": 75, "speed": "nhanh nhất", "quality": "thấp"},
        "base": {"size_mb": 142, "speed": "nhanh", "quality": "trung bình"},
        "small": {"size_mb": 466, "speed": "vừa", "quality": "khá"},
        "medium": {"size_mb": 1500, "speed": "chậm", "quality": "tốt"},
        "large": {"size_mb": 2880, "speed": "rất chậm (cần GPU)", "quality": "tốt nhất"},
    }
    whisper_cache = os.path.expanduser("~/.cache/whisper")
    for name, meta in whisper_models.items():
        downloaded = os.path.exists(os.path.join(whisper_cache, f"{name}.pt"))
        info["whisper_models"].append({
            "name": name, "downloaded": downloaded,
            "size_mb": meta["size_mb"], "speed": meta["speed"], "quality": meta["quality"],
        })

    # Disk usage
    try:
        import shutil
        for label, path in [("Videos", BASE_VIDEO_DIR), ("Edited", EDITED_VIDEO_DIR)]:
            if os.path.exists(path):
                usage = shutil.disk_usage(path)
                info["disk"][label] = {
                    "total_gb": round(usage.total / 1024**3, 1),
                    "used_gb": round(usage.used / 1024**3, 1),
                    "free_gb": round(usage.free / 1024**3, 1),
                    "percent": round(usage.used / usage.total * 100, 1),
                }
    except Exception:
        pass

    return jsonify({"ok": True, **info})


@app.route("/api/whisper/download-model", methods=["POST"])
def api_whisper_download_model():
    """Tải trước Whisper model (tránh tải lúc chạy pipeline)."""
    data = request.json or {}
    model_name = data.get("model", "base")
    if model_name not in ("tiny", "base", "small", "medium", "large"):
        return jsonify({"ok": False, "error": f"Model không hợp lệ: {model_name}"})

    task_id = st.make_task_id("download")
    st.create_task(task_id, "download", f"Tải Whisper model: {model_name}", {"model": model_name})

    def run():
        try:
            st.update_task(task_id, status="running", progress=10,
                           message=f"Đang tải Whisper model '{model_name}'...")
            import whisper
            whisper.load_model(model_name)
            st.finish_task(task_id, True, f"✅ Whisper model '{model_name}' đã sẵn sàng")
        except Exception as e:
            st.finish_task(task_id, False, f"❌ Lỗi tải model: {str(e)}")

    _task_futures[task_id] = task_executor.submit(run)
    return jsonify({"ok": True, "task_id": task_id, "message": f"Đang tải model {model_name}..."})


@app.route("/api/video/serve")
def api_video_serve():
    """Serve video file để preview trên dashboard."""
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        return "File not found", 404
    # Chỉ cho phép serve video từ thư mục cho phép
    allowed = [BASE_VIDEO_DIR, EDITED_VIDEO_DIR]
    if not any(os.path.abspath(path).startswith(os.path.abspath(d)) for d in allowed):
        return "Forbidden", 403
    from flask import send_file
    return send_file(path, mimetype="video/mp4")


if __name__ == "__main__":
    print("=" * 50)
    print("  ContenFactory Dashboard")
    print("  http://localhost:5555")
    print("=" * 50)
    # Initial service check
    threading.Thread(target=st.check_all_services, daemon=True).start()
    app.run(host="0.0.0.0", port=5555, debug=False)
