"""
proxy_manager.py
Quản lý proxy cho từng thiết bị BoxPhone.
Hỗ trợ HTTP/SOCKS5 proxy, gán proxy cho thiết bị, kiểm tra IP.
"""

import json
import os
import requests
import subprocess
from typing import List, Dict, Optional

DATA_FILE = os.path.join(os.path.dirname(__file__), "devices.json")


def _load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devices": [], "accounts": [], "proxies": []}


def _save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _ensure_proxies_key(data: dict):
    if "proxies" not in data:
        data["proxies"] = []


# ─── PROXY CRUD ───────────────────────────────────────────────────────────────

def add_proxy(host: str, port: int, username: str = "", password: str = "",
              proxy_type: str = "http", note: str = "") -> Dict:
    """Thêm proxy mới"""
    data = _load_data()
    _ensure_proxies_key(data)

    proxy_id = f"proxy_{len(data['proxies']) + 1:03d}"
    proxy = {
        "id": proxy_id,
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
        "type": proxy_type,  # http / socks5
        "note": note,
        "status": "unknown",  # unknown / ok / error
        "last_ip": "",
        "assigned_serial": None
    }
    data["proxies"].append(proxy)
    _save_data(data)
    return proxy


def get_all_proxies() -> List[Dict]:
    """Lấy tất cả proxy"""
    data = _load_data()
    _ensure_proxies_key(data)
    return data.get("proxies", [])


def get_proxy(proxy_id: str) -> Optional[Dict]:
    """Lấy proxy theo ID"""
    for p in get_all_proxies():
        if p["id"] == proxy_id:
            return p
    return None


def update_proxy(proxy_id: str, **kwargs) -> bool:
    """Cập nhật proxy"""
    data = _load_data()
    _ensure_proxies_key(data)
    for p in data["proxies"]:
        if p["id"] == proxy_id:
            p.update(kwargs)
            _save_data(data)
            return True
    return False


def remove_proxy(proxy_id: str) -> bool:
    """Xóa proxy"""
    data = _load_data()
    _ensure_proxies_key(data)
    before = len(data["proxies"])
    data["proxies"] = [p for p in data["proxies"] if p["id"] != proxy_id]
    if len(data["proxies"]) < before:
        # Gỡ proxy khỏi thiết bị đang dùng
        for d in data["devices"]:
            if d.get("proxy_id") == proxy_id:
                d["proxy_id"] = None
        _save_data(data)
        return True
    return False


def assign_proxy_to_device(serial: str, proxy_id: Optional[str]) -> bool:
    """Gán proxy cho thiết bị (proxy_id=None để gỡ proxy)"""
    data = _load_data()
    _ensure_proxies_key(data)

    # Gỡ proxy cũ khỏi thiết bị này
    for d in data["devices"]:
        if d["serial"] == serial:
            d["proxy_id"] = proxy_id
            _save_data(data)

            # Cập nhật assigned_serial trong proxy
            for p in data["proxies"]:
                if p["id"] == proxy_id:
                    p["assigned_serial"] = serial
                elif p.get("assigned_serial") == serial:
                    p["assigned_serial"] = None
            _save_data(data)
            return True
    return False


def get_proxy_for_device(serial: str) -> Optional[Dict]:
    """Lấy proxy đang gán cho thiết bị"""
    data = _load_data()
    for d in data["devices"]:
        if d["serial"] == serial:
            proxy_id = d.get("proxy_id")
            if proxy_id:
                return get_proxy(proxy_id)
    return None


def import_proxies_from_text(text: str) -> int:
    """
    Import proxy từ text, mỗi dòng 1 proxy.
    Formats hỗ trợ:
      - ip:port
      - ip:port:user:pass
      - http://ip:port
      - socks5://user:pass@ip:port
    """
    count = 0
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            proxy = _parse_proxy_line(line)
            if proxy:
                add_proxy(**proxy)
                count += 1
        except Exception:
            continue
    return count


def _parse_proxy_line(line: str) -> Optional[Dict]:
    """Parse 1 dòng proxy"""
    proxy_type = "http"

    # Xử lý scheme
    if line.startswith("socks5://"):
        proxy_type = "socks5"
        line = line[9:]
    elif line.startswith("http://"):
        line = line[7:]
    elif line.startswith("https://"):
        line = line[8:]

    # Xử lý user:pass@host:port
    if "@" in line:
        auth, hostport = line.rsplit("@", 1)
        if ":" in auth:
            username, password = auth.split(":", 1)
        else:
            username, password = auth, ""
        host, port = hostport.rsplit(":", 1)
        return {"host": host, "port": int(port), "username": username,
                "password": password, "proxy_type": proxy_type}

    # Xử lý ip:port:user:pass
    parts = line.split(":")
    if len(parts) == 4:
        return {"host": parts[0], "port": int(parts[1]),
                "username": parts[2], "password": parts[3],
                "proxy_type": proxy_type}
    elif len(parts) == 2:
        return {"host": parts[0], "port": int(parts[1]),
                "proxy_type": proxy_type}

    return None


# ─── PROXY CHECK ──────────────────────────────────────────────────────────────

def check_proxy(proxy_id: str, timeout: int = 10) -> Dict:
    """Kiểm tra proxy có hoạt động không, trả về IP thực"""
    proxy = get_proxy(proxy_id)
    if not proxy:
        return {"success": False, "error": "Proxy not found"}

    proxy_url = _build_proxy_url(proxy)
    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        r = requests.get("https://api.ipify.org?format=json",
                         proxies=proxies, timeout=timeout)
        if r.status_code == 200:
            ip = r.json().get("ip", "")
            update_proxy(proxy_id, status="ok", last_ip=ip)
            return {"success": True, "ip": ip}
        else:
            update_proxy(proxy_id, status="error")
            return {"success": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        update_proxy(proxy_id, status="error")
        return {"success": False, "error": str(e)}


def _build_proxy_url(proxy: Dict) -> str:
    """Tạo proxy URL từ dict"""
    scheme = proxy.get("type", "http")
    host = proxy["host"]
    port = proxy["port"]
    user = proxy.get("username", "")
    pwd = proxy.get("password", "")

    if user and pwd:
        return f"{scheme}://{user}:{pwd}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


# ─── SET PROXY ON DEVICE ──────────────────────────────────────────────────────

def set_proxy_on_device(serial: str, proxy_id: str) -> bool:
    """
    Cài proxy lên thiết bị Android qua ADB.
    Chỉ hoạt động với HTTP proxy trên WiFi.
    """
    from adb_manager import run_adb
    proxy = get_proxy(proxy_id)
    if not proxy:
        return False

    host = proxy["host"]
    port = proxy["port"]

    # Set global HTTP proxy
    _, _, code = run_adb(["shell", "settings", "put", "global",
                          "http_proxy", f"{host}:{port}"], serial)
    return code == 0


def remove_proxy_from_device(serial: str) -> bool:
    """Gỡ proxy khỏi thiết bị"""
    from adb_manager import run_adb
    _, _, code = run_adb(["shell", "settings", "put", "global",
                          "http_proxy", ":0"], serial)
    return code == 0


def get_device_current_ip(serial: str, timeout: int = 15) -> str:
    """Lấy IP hiện tại của thiết bị (qua curl trên device)"""
    from adb_manager import run_adb
    stdout, _, code = run_adb(
        ["shell", "curl", "-s", "--max-time", "10", "https://api.ipify.org"],
        serial, timeout=timeout
    )
    if code == 0 and stdout.strip():
        return stdout.strip()
    return ""
