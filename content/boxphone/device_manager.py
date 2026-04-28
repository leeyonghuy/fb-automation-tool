"""
device_manager.py
Quản lý danh sách thiết bị + tài khoản TikTok.
Lưu trữ trong file JSON local.
"""

import json
import os
from typing import List, Dict, Optional
from adb_manager import get_devices, get_device_info

DATA_FILE = os.path.join(os.path.dirname(__file__), "devices.json")


def _load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devices": [], "accounts": []}


def _save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── DEVICE MANAGEMENT ────────────────────────────────────────────────────────

def sync_devices() -> List[Dict]:
    """Đồng bộ danh sách thiết bị từ ADB vào file JSON"""
    data = _load_data()
    connected = get_devices()
    existing_serials = {d["serial"] for d in data["devices"]}

    for dev in connected:
        serial = dev["serial"]
        if serial not in existing_serials:
            info = get_device_info(serial) if dev["status"] == "device" else {}
            data["devices"].append({
                "serial": serial,
                "status": dev["status"],
                "model": info.get("model", "Unknown"),
                "android_version": info.get("android_version", ""),
                "account_id": None,
                "note": ""
            })
        else:
            # Cập nhật status
            for d in data["devices"]:
                if d["serial"] == serial:
                    d["status"] = dev["status"]
                    break

    _save_data(data)
    return data["devices"]


def get_all_devices() -> List[Dict]:
    """Lấy tất cả thiết bị đã lưu"""
    return _load_data()["devices"]


def get_device(serial: str) -> Optional[Dict]:
    """Lấy thông tin một thiết bị"""
    for d in _load_data()["devices"]:
        if d["serial"] == serial:
            return d
    return None


def update_device(serial: str, **kwargs) -> bool:
    """Cập nhật thông tin thiết bị"""
    data = _load_data()
    for d in data["devices"]:
        if d["serial"] == serial:
            d.update(kwargs)
            _save_data(data)
            return True
    return False


def remove_device(serial: str) -> bool:
    """Xóa thiết bị khỏi danh sách"""
    data = _load_data()
    before = len(data["devices"])
    data["devices"] = [d for d in data["devices"] if d["serial"] != serial]
    if len(data["devices"]) < before:
        _save_data(data)
        return True
    return False


# ─── ACCOUNT MANAGEMENT ───────────────────────────────────────────────────────

def add_account(email: str, password: str, serial: str = None,
                note: str = "") -> Dict:
    """Thêm tài khoản TikTok"""
    data = _load_data()
    account_id = f"acc_{len(data['accounts']) + 1:03d}"
    account = {
        "id": account_id,
        "email": email,
        "password": password,
        "serial": serial,
        "status": "active",
        "note": note,
        "last_login": None,
        "last_post": None,
        "post_count": 0
    }
    data["accounts"].append(account)
    _save_data(data)

    # Gán account cho device nếu có serial
    if serial:
        assign_account_to_device(serial, account_id)

    return account


def get_all_accounts() -> List[Dict]:
    """Lấy tất cả tài khoản"""
    return _load_data()["accounts"]


def get_account(account_id: str) -> Optional[Dict]:
    """Lấy tài khoản theo ID"""
    for a in _load_data()["accounts"]:
        if a["id"] == account_id:
            return a
    return None


def get_account_by_serial(serial: str) -> Optional[Dict]:
    """Lấy tài khoản được gán cho thiết bị"""
    data = _load_data()
    device = next((d for d in data["devices"] if d["serial"] == serial), None)
    if not device or not device.get("account_id"):
        return None
    return get_account(device["account_id"])


def update_account(account_id: str, **kwargs) -> bool:
    """Cập nhật thông tin tài khoản"""
    data = _load_data()
    for a in data["accounts"]:
        if a["id"] == account_id:
            a.update(kwargs)
            _save_data(data)
            return True
    return False


def remove_account(account_id: str) -> bool:
    """Xóa tài khoản"""
    data = _load_data()
    before = len(data["accounts"])
    data["accounts"] = [a for a in data["accounts"] if a["id"] != account_id]
    if len(data["accounts"]) < before:
        _save_data(data)
        return True
    return False


def assign_account_to_device(serial: str, account_id: str) -> bool:
    """Gán tài khoản cho thiết bị"""
    data = _load_data()
    for d in data["devices"]:
        if d["serial"] == serial:
            d["account_id"] = account_id
            _save_data(data)
            # Cập nhật serial trong account
            for a in data["accounts"]:
                if a["id"] == account_id:
                    a["serial"] = serial
                    break
            _save_data(data)
            return True
    return False


def get_paired_list() -> List[Dict]:
    """
    Lấy danh sách thiết bị đã được gán tài khoản.
    Trả về: [{"serial": ..., "model": ..., "email": ..., "status": ...}]
    """
    data = _load_data()
    result = []
    for device in data["devices"]:
        account = None
        if device.get("account_id"):
            account = next((a for a in data["accounts"]
                           if a["id"] == device["account_id"]), None)
        result.append({
            "serial": device["serial"],
            "model": device.get("model", "Unknown"),
            "device_status": device.get("status", "offline"),
            "account_id": device.get("account_id"),
            "email": account["email"] if account else "",
            "account_status": account["status"] if account else "",
            "last_post": account["last_post"] if account else None,
            "post_count": account["post_count"] if account else 0,
            "note": device.get("note", "")
        })
    return result


def mark_post_done(serial: str):
    """Cập nhật thống kê sau khi đăng bài"""
    import datetime
    account = get_account_by_serial(serial)
    if account:
        update_account(account["id"],
                       last_post=datetime.datetime.now().isoformat(),
                       post_count=account.get("post_count", 0) + 1)


def import_accounts_csv(csv_path: str) -> int:
    """
    Import tài khoản từ file CSV.
    Format: serial,email,password,note
    """
    import csv
    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            add_account(
                email=row.get("email", ""),
                password=row.get("password", ""),
                serial=row.get("serial", None) or None,
                note=row.get("note", "")
            )
            count += 1
    return count
