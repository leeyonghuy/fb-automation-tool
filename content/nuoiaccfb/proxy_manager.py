"""
proxy_manager.py
Quản lý danh sách proxy cho các profile IX Browser.
- Đọc proxy từ file proxies.txt
- Thêm proxy mới
- Cập nhật proxy cho profile
- Kiểm tra proxy còn sống không
"""

import requests
import json
import random
import socket
import time
from pathlib import Path

PROXY_FILE = Path(__file__).parent / "proxies.txt"


def load_proxies() -> list[dict]:
    """Đọc danh sách proxy từ file. Format: ip:port hoặc ip:port:user:pass"""
    proxies = []
    if not PROXY_FILE.exists():
        return proxies
    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) == 2:
                proxies.append({"host": parts[0], "port": parts[1], "user": "", "pass": ""})
            elif len(parts) == 4:
                proxies.append({"host": parts[0], "port": parts[1], "user": parts[2], "pass": parts[3]})
    return proxies


def add_proxy(host: str, port: str, user: str = "", password: str = "") -> bool:
    """Thêm proxy mới vào file proxies.txt"""
    line = f"{host}:{port}"
    if user and password:
        line += f":{user}:{password}"
    # Kiểm tra trùng
    proxies = load_proxies()
    for p in proxies:
        if p["host"] == host and p["port"] == port:
            print(f"[proxy_manager] Proxy {host}:{port} đã tồn tại.")
            return False
    with open(PROXY_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"[proxy_manager] Đã thêm proxy: {line}")
    return True


def add_proxies_bulk(proxy_list: list[str]) -> int:
    """
    Thêm nhiều proxy cùng lúc.
    proxy_list: list các string dạng "ip:port" hoặc "ip:port:user:pass"
    Trả về số proxy đã thêm thành công.
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


if __name__ == "__main__":
    print("=== Proxy Manager ===")
    proxies = load_proxies()
    print(f"Tổng proxy: {len(proxies)}")
    for p in proxies:
        print(f"  {p['host']}:{p['port']}")
