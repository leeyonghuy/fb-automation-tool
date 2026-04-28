"""
common/secret_store.py — mã hoá / giải mã giá trị nhạy cảm.

Dùng `cryptography.fernet.Fernet` (AES-128 trong CBC + HMAC-SHA256).
Key đọc từ env `ACCOUNT_ENCRYPTION_KEY` (xem `.env.example`).

API:
    encrypt(plain) -> str  # token bắt đầu bằng "enc:"
    decrypt(token_or_plain) -> str  # nếu là plain → trả nguyên
    is_encrypted(s) -> bool

Thiết kế:
  - Token có prefix "enc:" để phân biệt với plaintext cũ.
  - `decrypt` chấp nhận plaintext cũ (không có prefix) → trả luôn,
    cho phép migrate dần (đọc OK kể cả khi accounts.json chưa mã hoá).
  - Nếu không có ACCOUNT_ENCRYPTION_KEY → encrypt là no-op (để dev không
    bị block); production nên set key.

Sinh key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Migration script gợi ý (chạy 1 lần):
    from common.secret_store import encrypt
    import json
    with open("accounts.json", encoding="utf-8") as f:
        accs = json.load(f)
    for a in accs:
        for k in ("password", "two_fa_secret", "cookie"):
            if a.get(k):
                a[k] = encrypt(a[k])
    with open("accounts.json", "w", encoding="utf-8") as f:
        json.dump(accs, f, ensure_ascii=False, indent=2)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_PREFIX = "enc:"
_fernet = None
_key_warned = False


def _get_fernet():
    global _fernet, _key_warned
    if _fernet is not None:
        return _fernet
    try:
        # Lazy load config + cryptography
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from config import ACCOUNT_ENCRYPTION_KEY  # type: ignore
        if not ACCOUNT_ENCRYPTION_KEY:
            if not _key_warned:
                logger.warning(
                    "ACCOUNT_ENCRYPTION_KEY chưa được set — secret_store hoạt động ở "
                    "chế độ no-op (giá trị lưu plaintext). Sinh key:\n"
                    "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
                _key_warned = True
            return None
        from cryptography.fernet import Fernet  # type: ignore
        _fernet = Fernet(ACCOUNT_ENCRYPTION_KEY.encode())
        return _fernet
    except ImportError:
        if not _key_warned:
            logger.warning(
                "cryptography chưa được cài. Chạy: pip install cryptography"
            )
            _key_warned = True
        return None
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Fernet: {e}")
        return None


def is_encrypted(s: str) -> bool:
    return isinstance(s, str) and s.startswith(_PREFIX)


def encrypt(plain: str) -> str:
    """Mã hoá plain → 'enc:<token>'. Nếu key chưa set → trả nguyên."""
    if not plain or is_encrypted(plain):
        return plain
    f = _get_fernet()
    if f is None:
        return plain
    token = f.encrypt(plain.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt(value: str) -> str:
    """Giải mã. Nếu không có prefix → coi như plaintext cũ và trả nguyên."""
    if not value or not is_encrypted(value):
        return value
    f = _get_fernet()
    if f is None:
        # Không có key mà gặp token mã hoá → không thể decrypt
        logger.error("Gặp giá trị đã mã hoá nhưng ACCOUNT_ENCRYPTION_KEY chưa set!")
        return ""
    try:
        return f.decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except Exception as e:
        logger.error(f"Decrypt thất bại: {e}")
        return ""
