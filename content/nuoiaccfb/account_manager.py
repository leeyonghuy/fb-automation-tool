"""
account_manager.py
Manage Facebook accounts / Fanpages.
- Store account status (accounts.json)
- Assign IX Browser profile to each account
- Track status: active, checkpoint, die, warming
- Store credentials: email, password, 2FA
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional
from collections import Counter

ACCOUNTS_FILE = Path(__file__).parent / "accounts.json"

# Cho phép import common/* từ project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from common.json_store import load_json, save_json, locked_update  # type: ignore
    from common.secret_store import encrypt, decrypt, is_encrypted  # type: ignore
    _HARDENED = True
except ImportError:
    # Fallback: giữ hiện thực cũ để không vỡ khi common chưa cài deps
    _HARDENED = False

    def load_json(path, default=None):  # type: ignore[no-redef]
        if not Path(path).exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_json(path, data):  # type: ignore[no-redef]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def locked_update(path, default=None):  # type: ignore[no-redef]
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            data = load_json(path, default)
            yield data
            save_json(path, data)
        return _cm()

    def encrypt(s):  # type: ignore[no-redef]
        return s

    def decrypt(s):  # type: ignore[no-redef]
        return s

    def is_encrypted(s):  # type: ignore[no-redef]
        return False


# Trường nhạy cảm sẽ được mã hoá khi save, giải mã khi load
_SENSITIVE_FIELDS = ("password", "two_fa_secret", "cookie")


def _decrypt_account(acc: dict) -> dict:
    """Trả về bản acc với trường nhạy cảm đã giải mã (nhận cả plaintext cũ)."""
    out = dict(acc)
    for k in _SENSITIVE_FIELDS:
        if out.get(k):
            out[k] = decrypt(out[k])
    return out


def _encrypt_account_in_place(acc: dict) -> None:
    """Mã hoá trường nhạy cảm của 1 acc (idempotent: skip nếu đã mã hoá)."""
    for k in _SENSITIVE_FIELDS:
        v = acc.get(k)
        if v and not is_encrypted(v):
            acc[k] = encrypt(v)


def _load() -> list:
    """Load + decrypt sensitive fields."""
    raw = load_json(ACCOUNTS_FILE, default=[]) or []
    return [_decrypt_account(a) for a in raw]


def _save(accounts: list):
    """Encrypt sensitive fields trước khi ghi."""
    encrypted = []
    for a in accounts:
        a2 = dict(a)
        _encrypt_account_in_place(a2)
        encrypted.append(a2)
    save_json(ACCOUNTS_FILE, encrypted)


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────

def add_account(fb_uid: str, name: str, profile_id=None,
                account_type: str = "personal",
                email: str = "", password: str = "",
                two_fa_secret: str = "",
                cookie: str = "", note: str = "",
                proxy: str = "") -> dict:
    """
    Add new account (atomic với file lock).
    account_type: 'personal' | 'fanpage'
    proxy format: 'host:port:user:pass' or 'host:port'
    """
    new_acc = {
        "fb_uid": fb_uid,
        "name": name,
        "account_type": account_type,
        "profile_id": profile_id,       # IX Browser profile ID
        "group": 1,                     # Group number for batch processing
        "status": "new",                # new | warming | active | checkpoint | die
        # Credentials (encrypted on disk via secret_store)
        "email": email,
        "password": password,
        "two_fa_secret": two_fa_secret,
        "cookie": cookie,
        "proxy": proxy,                 # host:port:user:pass
        # Metadata
        "note": note,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_action_at": "",
        "warm_up_days": 0,
        "post_count": 0,
        "like_count_today": 0,
        "comment_count_today": 0,
        "friend_count_today": 0,
        "last_reset_date": time.strftime("%Y-%m-%d"),
    }

    with locked_update(ACCOUNTS_FILE, default=[]) as accs:
        # Decrypt to compare uid (uid không nhạy cảm, không cần decrypt)
        for acc in accs:
            if acc.get("fb_uid") == fb_uid:
                print(f"[account_manager] UID {fb_uid} already exists.")
                # Trả bản decrypted cho caller
                return _decrypt_account(acc)
        # Chuẩn bị bản encrypted để ghi
        encrypted = dict(new_acc)
        _encrypt_account_in_place(encrypted)
        accs.append(encrypted)

    print(f"[account_manager] Added: {name} ({fb_uid})")
    return new_acc


def import_accounts_from_list(lines: list) -> list:
    """
    Import accounts from text lines.
    Supported formats:
      email|password
      email|password|two_fa_secret
      email|password|two_fa_secret|profile_id
    """
    added = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        email = parts[0].strip()
        password = parts[1].strip() if len(parts) > 1 else ""
        two_fa = parts[2].strip() if len(parts) > 2 else ""
        profile_id = int(parts[3].strip()) if len(parts) > 3 else None
        fb_uid = email.split("@")[0] + f"_{i}"
        acc = add_account(
            fb_uid=fb_uid,
            name=email,
            email=email,
            password=password,
            two_fa_secret=two_fa,
            profile_id=profile_id,
        )
        added.append(acc)
    print(f"[account_manager] Imported {len(added)} accounts")
    return added


def import_from_file(filepath: str) -> list:
    """Import accounts from text file (one per line)"""
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()
    return import_accounts_from_list(lines)


def get_all_accounts() -> list:
    return _load()


def get_account(fb_uid: str) -> Optional[dict]:
    for acc in _load():
        if acc["fb_uid"] == fb_uid:
            return acc
    return None


def get_account_by_profile(profile_id) -> Optional[dict]:
    for acc in _load():
        if str(acc.get("profile_id")) == str(profile_id):
            return acc
    return None


def update_account(fb_uid: str, **kwargs) -> bool:
    """Update field bất kỳ (atomic). Tự mã hoá sensitive fields."""
    found = False
    with locked_update(ACCOUNTS_FILE, default=[]) as accs:
        for acc in accs:
            if acc.get("fb_uid") == fb_uid:
                # Mã hoá ngay những kwarg nhạy cảm
                merged = dict(kwargs)
                for k in _SENSITIVE_FIELDS:
                    if k in merged and merged[k] and not is_encrypted(merged[k]):
                        merged[k] = encrypt(merged[k])
                acc.update(merged)
                found = True
                break
    if not found:
        print(f"[account_manager] UID not found: {fb_uid}")
    return found


def delete_account(fb_uid: str) -> bool:
    deleted = False
    with locked_update(ACCOUNTS_FILE, default=[]) as accs:
        before = len(accs)
        accs[:] = [a for a in accs if a.get("fb_uid") != fb_uid]
        deleted = len(accs) < before
    if deleted:
        print(f"[account_manager] Deleted: {fb_uid}")
    return deleted


def set_status(fb_uid: str, status: str) -> bool:
    valid = {"new", "warming", "active", "checkpoint", "die"}
    if status not in valid:
        print(f"[account_manager] Invalid status: {status}. Choose: {valid}")
        return False
    return update_account(fb_uid, status=status)


def assign_profile(fb_uid: str, profile_id) -> bool:
    """Assign IX Browser profile to account"""
    return update_account(fb_uid, profile_id=profile_id)


def log_action(fb_uid: str, action: str = ""):
    """Record last action time"""
    update_account(fb_uid,
                   last_action_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                   last_action=action)


def increment_post_count(fb_uid: str):
    acc = get_account(fb_uid)
    if acc:
        update_account(fb_uid, post_count=acc.get("post_count", 0) + 1)


def reset_daily_counts_if_needed(fb_uid: str):
    """Reset daily counters if new day"""
    acc = get_account(fb_uid)
    if not acc:
        return
    today = time.strftime("%Y-%m-%d")
    if acc.get("last_reset_date") != today:
        update_account(fb_uid,
                       like_count_today=0,
                       comment_count_today=0,
                       friend_count_today=0,
                       last_reset_date=today)


def auto_assign_profiles():
    """Auto assign IX Browser profiles to accounts without one"""
    from ix_browser import get_all_profiles
    profiles = get_all_profiles()
    accounts = _load()

    used_pids = {str(a.get("profile_id")) for a in accounts if a.get("profile_id")}
    free_profiles = [p for p in profiles if str(p.get("profile_id")) not in used_pids]

    assigned = 0
    for acc in accounts:
        if not acc.get("profile_id") and free_profiles:
            p = free_profiles.pop(0)
            assign_profile(acc["fb_uid"], p["profile_id"])
            assigned += 1
            print(f"[account_manager] Assigned profile {p['profile_id']} to {acc['fb_uid']}")

    print(f"[account_manager] Auto-assigned {assigned} profiles")
    return assigned


# ─────────────────────────────────────────────
# Group Management
# ─────────────────────────────────────────────

def get_groups() -> dict:
    """Return dict {group_number: [accounts]}"""
    accounts = _load()
    groups = {}
    for acc in accounts:
        g = acc.get("group", 1)
        groups.setdefault(g, []).append(acc)
    return dict(sorted(groups.items()))


def get_accounts_by_group(group: int) -> list:
    return [a for a in _load() if a.get("group", 1) == group]


def set_group(fb_uid: str, group: int) -> bool:
    return update_account(fb_uid, group=group)


def auto_assign_groups(group_size: int = 5) -> int:
    """Auto split all accounts into groups of group_size (atomic)."""
    changed = 0
    with locked_update(ACCOUNTS_FILE, default=[]) as accs:
        for i, acc in enumerate(accs):
            new_group = (i // group_size) + 1
            if acc.get("group") != new_group:
                acc["group"] = new_group
                changed += 1
        total = len(accs)
    print(f"[account_manager] Auto-assigned {total} accounts into groups of {group_size}")
    return changed


def get_group_summary() -> list:
    """Return list of group info dicts"""
    accounts = _load()
    groups = {}
    for acc in accounts:
        g = acc.get("group", 1)
        if g not in groups:
            groups[g] = {"group": g, "count": 0, "accounts": []}
        groups[g]["count"] += 1
        groups[g]["accounts"].append({
            "fb_uid": acc["fb_uid"],
            "email": acc.get("email", ""),
            "profile_id": acc.get("profile_id"),
            "status": acc.get("status", "new"),
        })
    return [groups[k] for k in sorted(groups.keys())]


# ─────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────

def get_accounts_by_status(status: str) -> list:
    return [a for a in _load() if a.get("status") == status]


def get_active_accounts() -> list:
    return get_accounts_by_status("active")


def get_warming_accounts() -> list:
    return get_accounts_by_status("warming")


def get_new_accounts() -> list:
    return get_accounts_by_status("new")


def get_fanpages() -> list:
    return [a for a in _load() if a.get("account_type") == "fanpage"]


def get_accounts_ready() -> list:
    """Get accounts ready for posting (active + has profile)"""
    return [
        a for a in _load()
        if a.get("status") == "active"
        and a.get("profile_id")
    ]


# ─────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────

def print_summary():
    accounts = _load()
    status_count = Counter(a.get("status", "unknown") for a in accounts)
    type_count = Counter(a.get("account_type", "unknown") for a in accounts)
    print(f"\n{'='*45}")
    print(f"  Total accounts: {len(accounts)}")
    print(f"  By type:   {dict(type_count)}")
    print(f"  By status: {dict(status_count)}")
    print(f"\n  Details:")
    for a in accounts:
        pid = a.get("profile_id", "-")
        status = a.get("status", "?")
        days = a.get("warm_up_days", 0)
        posts = a.get("post_count", 0)
        print(f"    [{a['fb_uid']}] profile={pid} status={status} days={days} posts={posts}")
    print(f"{'='*45}\n")


def migrate_existing_accounts() -> int:
    """
    Chạy 1 lần: mã hoá tất cả password/2FA/cookie hiện lưu plaintext.
    Idempotent (skip field đã mã hoá).
    Trả về số field đã mã hoá.
    """
    if not _HARDENED:
        print("[migrate] common/json_store chưa khả dụng — hãy chạy: pip install -r requirements.txt")
        return 0

    count = 0
    with locked_update(ACCOUNTS_FILE, default=[]) as accs:  # type: ignore[arg-type]
        for a in accs:
            for k in _SENSITIVE_FIELDS:
                v = a.get(k)
                if v and not is_encrypted(v):
                    a[k] = encrypt(v)
                    count += 1
    print(f"[migrate] Mã hoá {count} field nhạy cảm trong {len(accs)} acc.")
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true",
                        help="Mã hoá password/2FA/cookie cũ trong accounts.json")
    args = parser.parse_args()

    if args.migrate:
        migrate_existing_accounts()
    else:
        print_summary()
