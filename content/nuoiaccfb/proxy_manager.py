"""
proxy_manager.py
Quản lý danh sách proxy cho các profile IX Browser.
- Đọc proxy từ proxies.json (có metadata: ngày thuê, hết hạn, ghi chú)
- Tương thích ngược với proxies.txt
- Kiểm tra proxy còn sống không
- Tính thời gian còn lại
"""

import json
import random
import socket
import time
from datetime import datetime, date
from pathlib import Path

PROXY_FILE = Path(__file__).parent / "proxies.txt"
PROXY_JSON = Path(__file__).parent / "proxies.json"


# ─────────────────────────────────────────────
# JSON store (metadata: ngày thuê, hết hạn)
# ─────────────────────────────────────────────

def _load_json_store() -> list[dict]:
    """Đọc proxies.json"""
    if not PROXY_JSON.exists():
        return []
    try:
        with open(PROXY_JSON, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _save_json_store(proxies: list[dict]):
    """Ghi proxies.json"""
    with open(PROXY_JSON, "w", encoding="utf-8") as f:
        json.dump(proxies, f, ensure_ascii=False, indent=2)


def _proxy_key(host: str, port: str) -> str:
    return f"{host}:{port}"


# ─────────────────────────────────────────────
# Load / Save
# ─────────────────────────────────────────────

def load_proxies() -> list[dict]:
    """
    Đọc danh sách proxy.
    Ưu tiên proxies.json, fallback sang proxies.txt.
    Mỗi proxy có: host, port, user, pass, note, rent_date, expire_date, days_left
    """
    store = {_proxy_key(p["host"], p["port"]): p for p in _load_json_store()}

    # Đọc proxies.txt để lấy danh sách cơ bản
    raw_proxies = []
    if PROXY_FILE.exists():
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) == 2:
                    raw_proxies.append({"host": parts[0], "port": parts[1], "user": "", "pass": ""})
                elif len(parts) == 4:
                    raw_proxies.append({"host": parts[0], "port": parts[1], "user": parts[2], "pass": parts[3]})

    # Merge: txt là nguồn chính, json bổ sung metadata
    result = []
    for p in raw_proxies:
        key = _proxy_key(p["host"], p["port"])
        meta = store.get(key, {})
        entry = {
            "host": p["host"],
            "port": p["port"],
            "user": p.get("user", ""),
            "pass": p.get("pass", ""),
            "note": meta.get("note", ""),
            "rent_date": meta.get("rent_date", ""),
            "expire_date": meta.get("expire_date", ""),
            "days_left": _calc_days_left(meta.get("expire_date", "")),
        }
        result.append(entry)
    return result


def _calc_days_left(expire_date: str) -> int | None:
    """Tính số ngày còn lại. None nếu chưa set."""
    if not expire_date:
        return None
    try:
        exp = datetime.strptime(expire_date, "%Y-%m-%d").date()
        delta = (exp - date.today()).days
        return delta
    except Exception:
        return None


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────

def add_proxy(host: str, port: str, user: str = "", password: str = "",
              note: str = "", rent_date: str = "", expire_date: str = "") -> bool:
    """Thêm proxy mới vào proxies.txt và metadata vào proxies.json"""
    # Kiểm tra trùng
    proxies = load_proxies()
    for p in proxies:
        if p["host"] == host and p["port"] == port:
            print(f"[proxy_manager] Proxy {host}:{port} đã tồn tại.")
            return False

    # Ghi vào proxies.txt
    line = f"{host}:{port}"
    if user and password:
        line += f":{user}:{password}"
    with open(PROXY_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    # Ghi metadata vào proxies.json
    _update_proxy_meta(host, port, note=note, rent_date=rent_date, expire_date=expire_date)
    print(f"[proxy_manager] Đã thêm proxy: {line}")
    return True


def add_proxies_bulk(proxy_list: list[str]) -> int:
    """
    Thêm nhiều proxy cùng lúc.
    proxy_list: list các string dạng "ip:port" hoặc "ip:port:user:pass"
    """
    count = 0
    for entry in proxy_list:
        parts = entry.strip().split(":")
        if len(parts) == 2:
            ok = add_proxy(parts[0], parts[1])
        elif len(parts) == 4:
            ok = add_proxy(parts[0], parts[1], parts[2], parts[3])
        else:
            print(f"[proxy_manager] Format không hợp lệ: {entry}")
            continue
        if ok:
            count += 1
    return count


def update_proxy_meta(host: str, port: str, **kwargs) -> bool:
    """
    Cập nhật metadata cho proxy: note, rent_date, expire_date
    kwargs: note, rent_date (YYYY-MM-DD), expire_date (YYYY-MM-DD)
    """
    return _update_proxy_meta(host, port, **kwargs)


def _update_proxy_meta(host: str, port: str, **kwargs) -> bool:
    store = _load_json_store()
    key = _proxy_key(host, port)
    # Tìm entry hiện có
    found = False
    for entry in store:
        if _proxy_key(entry["host"], entry["port"]) == key:
            entry.update({k: v for k, v in kwargs.items() if v is not None})
            found = True
            break
    if not found:
        new_entry = {"host": host, "port": port}
        new_entry.update({k: v for k, v in kwargs.items() if v is not None})
        store.append(new_entry)
    _save_json_store(store)
    return True


def delete_proxy(host: str, port: str) -> bool:
    """Xóa proxy khỏi proxies.txt và proxies.json"""
    # Xóa khỏi txt
    if PROXY_FILE.exists():
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue
            parts = stripped.split(":")
            if parts[0] == host and parts[1] == port:
                continue  # bỏ dòng này
            new_lines.append(line)
        with open(PROXY_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    # Xóa khỏi json
    store = _load_json_store()
    store = [p for p in store if not (_proxy_key(p["host"], p["port"]) == _proxy_key(host, port))]
    _save_json_store(store)
    print(f"[proxy_manager] Đã xóa proxy: {host}:{port}")
    return True


def save_proxies_text(text: str) -> int:
    """Lưu toàn bộ proxy từ textarea (plain text). Giữ nguyên metadata cũ."""
    with open(PROXY_FILE, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    lines = [l for l in text.strip().split("\n") if l.strip()]
    return len(lines)


# ─────────────────────────────────────────────
# Check alive
# ─────────────────────────────────────────────

def check_proxy_alive(host: str, port: int, timeout: int = 5) -> bool:
    """Kiểm tra proxy có kết nối được không (TCP check)"""
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def get_live_proxies() -> list[dict]:
    """Trả về danh sách proxy còn sống"""
    all_proxies = load_proxies()
    live = []
    for p in all_proxies:
        if check_proxy_alive(p["host"], p["port"]):
            live.append(p)
            print(f"[proxy_manager] ✅ {p['host']}:{p['port']} - ALIVE")
        else:
            print(f"[proxy_manager] ❌ {p['host']}:{p['port']} - DEAD")
    return live


def get_random_proxy() -> dict | None:
    """Lấy ngẫu nhiên 1 proxy từ danh sách"""
    proxies = load_proxies()
    if not proxies:
        return None
    return random.choice(proxies)


def get_expiring_proxies(days_threshold: int = 3) -> list[dict]:
    """Lấy danh sách proxy sắp hết hạn trong N ngày"""
    proxies = load_proxies()
    result = []
    for p in proxies:
        dl = p.get("days_left")
        if dl is not None and dl <= days_threshold:
            result.append(p)
    return result


if __name__ == "__main__":
    print("=== Proxy Manager ===")
    proxies = load_proxies()
    print(f"Tổng proxy: {len(proxies)}")
    for p in proxies:
        dl = p.get("days_left")
        expire_str = f" | hết hạn: {p['expire_date']} ({dl} ngày)" if p.get("expire_date") else ""
        print(f"  {p['host']}:{p['port']}{expire_str}")
