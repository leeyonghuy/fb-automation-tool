"""
content_manager.py
Thư viện nội dung: quản lý video, caption, hashtag theo chiến dịch.
Tham khảo tính năng Content Library của XiaoWei.
"""

import json
import os
import time
import datetime
from typing import List, Dict, Optional

DATA_FILE = os.path.join(os.path.dirname(__file__), "devices.json")


def _load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devices": [], "accounts": [], "proxies": [], "schedules": [],
            "content_library": [], "campaigns": []}


def _save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _ensure_key(data: dict, key: str, default):
    if key not in data:
        data[key] = default


# ─── CONTENT ITEM (Video + Caption + Hashtag) ─────────────────────────────────

def add_content(video_path: str, caption: str = "", hashtags: list = None,
                product_name: str = None, product_link: str = None,
                tags: list = None, note: str = "") -> Dict:
    """Thêm nội dung vào thư viện"""
    data = _load_data()
    _ensure_key(data, "content_library", [])

    content_id = f"content_{int(time.time())}_{len(data['content_library'])}"
    filename = os.path.basename(video_path) if video_path else ""
    content = {
        "id": content_id,
        "video_path": video_path,
        "filename": filename,
        "caption": caption,
        "hashtags": hashtags or [],
        "product_name": product_name,
        "product_link": product_link,
        "tags": tags or [],  # Tags để phân loại (VD: "shop_a", "viral", "morning")
        "note": note,
        "created_at": datetime.datetime.now().isoformat(),
        "use_count": 0,  # Số lần đã dùng
        "last_used": None
    }
    data["content_library"].append(content)
    _save_data(data)
    return content


def get_all_content(tag_filter: str = None) -> List[Dict]:
    """Lấy tất cả nội dung, có thể lọc theo tag"""
    data = _load_data()
    _ensure_key(data, "content_library", [])
    items = data.get("content_library", [])
    if tag_filter:
        items = [c for c in items if tag_filter in c.get("tags", [])]
    return items


def get_content(content_id: str) -> Optional[Dict]:
    for c in get_all_content():
        if c["id"] == content_id:
            return c
    return None


def update_content(content_id: str, **kwargs) -> bool:
    data = _load_data()
    _ensure_key(data, "content_library", [])
    for c in data["content_library"]:
        if c["id"] == content_id:
            c.update(kwargs)
            _save_data(data)
            return True
    return False


def remove_content(content_id: str) -> bool:
    data = _load_data()
    _ensure_key(data, "content_library", [])
    before = len(data["content_library"])
    data["content_library"] = [c for c in data["content_library"] if c["id"] != content_id]
    if len(data["content_library"]) < before:
        _save_data(data)
        return True
    return False


def mark_content_used(content_id: str):
    """Đánh dấu nội dung đã được dùng"""
    update_content(content_id,
                   use_count=get_content(content_id).get("use_count", 0) + 1,
                   last_used=datetime.datetime.now().isoformat())


def import_content_from_folder(folder_path: str, caption: str = "",
                                hashtags: list = None, tags: list = None) -> int:
    """
    Import tất cả video từ 1 thư mục vào thư viện.
    Hỗ trợ: .mp4, .mov, .avi, .mkv
    """
    VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    count = 0
    if not os.path.isdir(folder_path):
        return 0
    for fname in os.listdir(folder_path):
        ext = os.path.splitext(fname)[1].lower()
        if ext in VIDEO_EXTS:
            full_path = os.path.join(folder_path, fname)
            add_content(full_path, caption=caption, hashtags=hashtags or [],
                        tags=tags or [])
            count += 1
    return count


# ─── CAMPAIGN ─────────────────────────────────────────────────────────────────

def create_campaign(name: str, serials: list, content_ids: list,
                    mode: str = "sequential", interval_hours: float = 24,
                    note: str = "") -> Dict:
    """
    Tạo chiến dịch đăng bài.
    mode: "sequential" (lần lượt) | "random" (ngẫu nhiên) | "all_same" (tất cả cùng 1 video)
    interval_hours: khoảng cách giữa các lần đăng (giờ)
    """
    data = _load_data()
    _ensure_key(data, "campaigns", [])

    campaign_id = f"camp_{int(time.time())}_{len(data['campaigns'])}"
    campaign = {
        "id": campaign_id,
        "name": name,
        "serials": serials,
        "content_ids": content_ids,
        "mode": mode,
        "interval_hours": interval_hours,
        "note": note,
        "status": "active",  # active / paused / completed
        "created_at": datetime.datetime.now().isoformat(),
        "current_index": 0,  # Index nội dung hiện tại (cho sequential)
        "post_count": 0,
        "last_post": None
    }
    data["campaigns"].append(campaign)
    _save_data(data)
    return campaign


def get_all_campaigns() -> List[Dict]:
    data = _load_data()
    _ensure_key(data, "campaigns", [])
    return data.get("campaigns", [])


def get_campaign(campaign_id: str) -> Optional[Dict]:
    for c in get_all_campaigns():
        if c["id"] == campaign_id:
            return c
    return None


def update_campaign(campaign_id: str, **kwargs) -> bool:
    data = _load_data()
    _ensure_key(data, "campaigns", [])
    for c in data["campaigns"]:
        if c["id"] == campaign_id:
            c.update(kwargs)
            _save_data(data)
            return True
    return False


def remove_campaign(campaign_id: str) -> bool:
    data = _load_data()
    _ensure_key(data, "campaigns", [])
    before = len(data["campaigns"])
    data["campaigns"] = [c for c in data["campaigns"] if c["id"] != campaign_id]
    if len(data["campaigns"]) < before:
        _save_data(data)
        return True
    return False


def get_next_content_for_campaign(campaign_id: str) -> Optional[Dict]:
    """Lấy nội dung tiếp theo cho chiến dịch"""
    import random
    campaign = get_campaign(campaign_id)
    if not campaign or not campaign["content_ids"]:
        return None

    content_ids = campaign["content_ids"]
    mode = campaign.get("mode", "sequential")

    if mode == "random":
        content_id = random.choice(content_ids)
    elif mode == "sequential":
        idx = campaign.get("current_index", 0) % len(content_ids)
        content_id = content_ids[idx]
        # Cập nhật index
        update_campaign(campaign_id, current_index=(idx + 1) % len(content_ids))
    else:  # all_same - dùng content đầu tiên
        content_id = content_ids[0]

    return get_content(content_id)


def run_campaign_post(campaign_id: str) -> List[Dict]:
    """
    Chạy 1 lượt đăng bài cho chiến dịch.
    Đăng lên tất cả thiết bị trong campaign.
    """
    from tiktok_post import upload_video_full
    campaign = get_campaign(campaign_id)
    if not campaign:
        return [{"success": False, "error": "Campaign not found"}]

    results = []
    serials = campaign.get("serials", [])
    mode = campaign.get("mode", "sequential")

    for serial in serials:
        if mode == "all_same":
            content = get_next_content_for_campaign(campaign_id) if results == [] else content
        else:
            content = get_next_content_for_campaign(campaign_id)

        if not content:
            results.append({"serial": serial, "success": False, "error": "No content"})
            continue

        result = upload_video_full(
            serial=serial,
            local_video_path=content["video_path"],
            caption=content.get("caption", ""),
            hashtags=content.get("hashtags", []),
            product_name=content.get("product_name"),
            product_link=content.get("product_link")
        )
        result["serial"] = serial
        result["content_id"] = content["id"]
        results.append(result)

        if result.get("success"):
            mark_content_used(content["id"])

    # Cập nhật campaign stats
    success_count = sum(1 for r in results if r.get("success"))
    update_campaign(campaign_id,
                    post_count=campaign.get("post_count", 0) + success_count,
                    last_post=datetime.datetime.now().isoformat())

    return results


def get_content_stats() -> Dict:
    """Thống kê thư viện nội dung"""
    items = get_all_content()
    return {
        "total": len(items),
        "total_used": sum(c.get("use_count", 0) for c in items),
        "never_used": len([c for c in items if c.get("use_count", 0) == 0]),
        "tags": list(set(tag for c in items for tag in c.get("tags", [])))
    }
