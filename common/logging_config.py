"""
common/logging_config.py — cấu hình logging chung cho mọi module.

Thay vì mỗi file Python gọi `logging.basicConfig(...)` (chỉ cái đầu thắng
khi import lẫn nhau), dùng `setup_logging("module_name")` để:
  - Mỗi module có file log riêng trong LOG_DIR.
  - StreamHandler stdout chỉ thêm 1 lần ở root logger.
  - Idempotent: gọi nhiều lần không nhân bản handler.

Usage:
    from common.logging_config import setup_logging
    logger = setup_logging("orchestrator")  # → logs/orchestrator.log
    logger.info(...)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Lazy import config để tránh vòng tròn khi config import logging
_LOG_DIR_OVERRIDE: str | None = None


def _resolve_log_dir() -> str:
    if _LOG_DIR_OVERRIDE:
        return _LOG_DIR_OVERRIDE
    try:
        # Tìm config.py ở project root (2 cấp lên từ file này)
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root))
        from config import LOG_DIR  # type: ignore
        return LOG_DIR
    except Exception:
        return str(Path(__file__).resolve().parent.parent / "logs")


def setup_logging(
    module_name: str,
    level: int = logging.INFO,
    log_filename: str | None = None,
) -> logging.Logger:
    """
    Cấu hình logger cho 1 module:
      - File handler: <LOG_DIR>/<log_filename or module_name>.log
      - Stream handler: stdout (gắn vào root, chỉ 1 lần)

    Idempotent: gọi lại với cùng module_name không tạo handler trùng.
    """
    log_dir = _resolve_log_dir()
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, (log_filename or f"{module_name}.log"))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Root: chỉ stream handler (idempotent)
    root = logging.getLogger()
    root.setLevel(level)
    has_stream = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    )
    if not has_stream:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    # Module logger: thêm file handler riêng (idempotent)
    logger = logging.getLogger(module_name)
    logger.setLevel(level)

    has_file = any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "_module_log", "") == module_name
        for h in logger.handlers
    )
    if not has_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        fh._module_log = module_name  # type: ignore[attr-defined]
        logger.addHandler(fh)

    # Tránh propagate gây duplicate (file đã có ở logger riêng, stream ở root)
    logger.propagate = True
    return logger
