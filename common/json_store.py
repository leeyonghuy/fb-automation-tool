"""
common/json_store.py — đọc/ghi JSON state an toàn với file lock + atomic write.

Vấn đề: nhiều module (`account_manager`, `fb_interact`, `fb_page`) đang dùng
pattern read-modify-write trên JSON files. Khi UI bấm 2 nút song song hoặc
scheduler chạy đồng thời → race condition → mất dữ liệu.

Giải pháp:
  - `filelock.FileLock` quanh toàn bộ read-modify-write.
  - Atomic write: ghi sang `.tmp` rồi `os.replace` để tránh file rỗng nếu
    process bị kill giữa chừng.

Usage:
    from common.json_store import load_json, save_json, locked_update

    accounts = load_json(PATH, default=[])

    # Hoặc transactional:
    with locked_update(PATH, default=[]) as data:
        data.append({"foo": "bar"})
        # tự động save khi exit context

API:
  - load_json(path, default) -> Any
  - save_json(path, data) -> None
  - locked_update(path, default) -> contextmanager yields data
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lock timeout — nếu hold quá lâu coi như deadlock và bỏ
_LOCK_TIMEOUT = 30  # seconds

try:
    from filelock import FileLock, Timeout  # type: ignore
    _FILELOCK_AVAILABLE = True
except ImportError:
    _FILELOCK_AVAILABLE = False
    logger.warning(
        "filelock chưa cài → JSON store hoạt động KHÔNG có lock (race condition risk). "
        "Chạy: pip install filelock"
    )

    class Timeout(Exception):  # type: ignore[no-redef]
        pass


def _lock_path(path: str | os.PathLike) -> str:
    return str(path) + ".lock"


@contextmanager
def _maybe_lock(path: str | os.PathLike, timeout: float = _LOCK_TIMEOUT):
    """Context manager bọc filelock; no-op nếu không cài filelock."""
    if not _FILELOCK_AVAILABLE:
        yield
        return
    lock = FileLock(_lock_path(path), timeout=timeout)
    try:
        with lock:
            yield
    except Timeout:
        logger.error(f"Timeout {timeout}s khi acquire lock cho {path} — bỏ qua lock")
        yield


def load_json(path: str | os.PathLike, default: Any = None) -> Any:
    """Đọc JSON với lock. Nếu không tồn tại / lỗi → trả default."""
    p = Path(path)
    if not p.exists():
        return default
    with _maybe_lock(path):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"load_json({path}) lỗi: {e}")
            return default


def save_json(path: str | os.PathLike, data: Any) -> None:
    """
    Ghi JSON atomic với lock.
    Pattern: write tmp file cùng folder → os.replace (atomic on POSIX & NTFS).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _maybe_lock(path):
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=p.name + ".",
            suffix=".tmp",
            dir=str(p.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, p)
        except Exception:
            # Cleanup tmp nếu fail
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise


@contextmanager
def locked_update(path: str | os.PathLike, default: Any = None):
    """
    Read-modify-write transactional với cùng 1 lock cho cả đọc lẫn ghi.

    Usage:
        with locked_update(PATH, default=[]) as data:
            data.append(item)  # data là list / dict
            # tự lưu khi exit context (kể cả modify in-place)

    Nếu code bên trong raise exception → KHÔNG ghi (giữ file cũ).
    """
    with _maybe_lock(path):
        # Đọc
        if Path(path).exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"locked_update read fail: {e} → dùng default")
                data = default
        else:
            data = default

        try:
            yield data
        except Exception:
            raise  # không lưu khi có lỗi

        # Ghi atomic
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=p.name + ".",
            suffix=".tmp",
            dir=str(p.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, p)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
