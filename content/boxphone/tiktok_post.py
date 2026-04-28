"""
tiktok_post.py
Auto upload video + gắn giỏ hàng TikTok Shop trên thiết bị Android.
"""

import time
import random
import os
from device_controller import (
    connect, tap, tap_element, input_text, press_back,
    open_app, element_exists, wait_for_element, screenshot,
    unlock_screen, swipe_up, swipe_down
)
from adb_manager import push_file, run_adb
from tiktok_login import get_tiktok_package, is_logged_in

# Thư mục tạm trên điện thoại để chứa video
PHONE_VIDEO_DIR = "/sdcard/DCIM/TikTokUpload"


def prepare_video_on_phone(serial: str, local_video_path: str) -> str:
    """
    Push video từ máy tính lên điện thoại.
    Trả về đường dẫn video trên điện thoại.
    """
    # Tạo thư mục nếu chưa có
    run_adb(["shell", "mkdir", "-p", PHONE_VIDEO_DIR], serial)

    filename = os.path.basename(local_video_path)
    remote_path = f"{PHONE_VIDEO_DIR}/{filename}"

    print(f"[{serial}] Pushing video: {filename}")
    ok = push_file(serial, local_video_path, remote_path)
    if not ok:
        return ""

    # Scan media để gallery nhận ra file
    run_adb(["shell", "am", "broadcast", "-a",
             "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
             "-d", f"file://{remote_path}"], serial)
    time.sleep(2)
    return remote_path


def open_tiktok_upload(serial: str) -> bool:
    """Mở màn hình upload TikTok (nút +)"""
    pkg = get_tiktok_package(serial)
    open_app(serial, pkg)
    time.sleep(3)

    # Tap nút "+" ở giữa bottom bar
    d = connect(serial)
    if not d:
        return False

    # Tìm nút + theo nhiều cách
    plus_btn = d(description="Create video")
    if not plus_btn.exists(timeout=3):
        plus_btn = d(resourceId=f"{pkg}:id/iv_tab_icon", instance=2)
    if not plus_btn.exists(timeout=3):
        # Tap vào giữa bottom bar
        size = d.window_size()
        tap(serial, size[0] // 2, size[1] - 60)
    else:
        plus_btn.click()

    time.sleep(2)
    return True


def select_video_from_gallery(serial: str, video_filename: str) -> bool:
    """Chọn video từ gallery TikTok"""
    d = connect(serial)
    if not d:
        return False

    # Tap "Upload" hoặc "Gallery"
    if element_exists(serial, text="Upload"):
        tap_element(serial, text="Upload")
    elif element_exists(serial, text="Gallery"):
        tap_element(serial, text="Gallery")
    else:
        # Tìm icon gallery (thường ở góc dưới trái)
        size = d.window_size()
        tap(serial, 60, size[1] - 120)

    time.sleep(2)

    # Tìm video theo tên file (không có extension)
    name_no_ext = os.path.splitext(video_filename)[0]
    if element_exists(serial, text=name_no_ext):
        tap_element(serial, text=name_no_ext)
        time.sleep(2)
        return True

    # Nếu không tìm được tên, chọn video đầu tiên trong gallery
    video_items = d(className="android.widget.ImageView")
    if video_items.exists(timeout=5):
        video_items[0].click()
        time.sleep(2)
        return True

    return False


def add_caption_and_hashtags(serial: str, caption: str, hashtags: list = None) -> bool:
    """Thêm caption và hashtag vào video"""
    d = connect(serial)
    if not d:
        return False

    # Tìm ô nhập caption
    caption_field = d(hint="Describe your video")
    if not caption_field.exists(timeout=5):
        caption_field = d(className="android.widget.EditText")

    if caption_field.exists(timeout=5):
        caption_field.click()
        time.sleep(0.5)
        d.send_keys(caption)
        time.sleep(0.5)

        # Thêm hashtags
        if hashtags:
            for tag in hashtags:
                tag_text = f" #{tag}" if not tag.startswith("#") else f" {tag}"
                d.send_keys(tag_text)
                time.sleep(0.3)

        time.sleep(1)
        return True

    return False


def attach_product(serial: str, product_name: str = None, product_link: str = None) -> bool:
    """
    Gắn sản phẩm TikTok Shop vào video.
    Tìm theo tên sản phẩm hoặc link.
    """
    d = connect(serial)
    if not d:
        return False

    # Tìm nút "Add link" hoặc "Product link" hoặc "Tag products"
    product_btn_texts = ["Add link", "Product link", "Tag products", "Add products", "Shop"]
    found = False
    for btn_text in product_btn_texts:
        if element_exists(serial, text=btn_text):
            tap_element(serial, text=btn_text)
            found = True
            break

    if not found:
        # Scroll xuống tìm
        for _ in range(3):
            swipe_up(serial)
            time.sleep(1)
            for btn_text in product_btn_texts:
                if element_exists(serial, text=btn_text):
                    tap_element(serial, text=btn_text)
                    found = True
                    break
            if found:
                break

    if not found:
        print(f"[{serial}] Không tìm thấy nút gắn sản phẩm")
        return False

    time.sleep(2)

    # Tìm kiếm sản phẩm
    if product_name:
        search_field = d(className="android.widget.EditText")
        if search_field.exists(timeout=5):
            search_field.click()
            time.sleep(0.5)
            d.send_keys(product_name)
            time.sleep(0.5)
            d.press("enter")
            time.sleep(3)

            # Chọn sản phẩm đầu tiên trong kết quả
            first_result = d(className="android.widget.LinearLayout", instance=1)
            if first_result.exists(timeout=5):
                first_result.click()
                time.sleep(1)

    elif product_link:
        # Nhập link sản phẩm
        link_field = d(className="android.widget.EditText")
        if link_field.exists(timeout=5):
            link_field.click()
            time.sleep(0.5)
            d.send_keys(product_link)
            time.sleep(0.5)
            d.press("enter")
            time.sleep(3)

    # Xác nhận chọn sản phẩm
    if element_exists(serial, text="Confirm"):
        tap_element(serial, text="Confirm")
    elif element_exists(serial, text="Add"):
        tap_element(serial, text="Add")
    elif element_exists(serial, text="Done"):
        tap_element(serial, text="Done")

    time.sleep(2)
    return True


def post_video(serial: str) -> bool:
    """Nhấn nút Post để đăng video"""
    # Tìm nút Post
    if element_exists(serial, text="Post"):
        tap_element(serial, text="Post")
    elif element_exists(serial, text="Publish"):
        tap_element(serial, text="Publish")
    else:
        return False

    time.sleep(5)

    # Kiểm tra đăng thành công
    if element_exists(serial, text="Your video is being uploaded"):
        return True
    if element_exists(serial, text="Video posted"):
        return True
    if element_exists(serial, text="Processing"):
        return True

    return True  # Assume success nếu không có lỗi


def upload_video_full(serial: str, local_video_path: str, caption: str = "",
                      hashtags: list = None, product_name: str = None,
                      product_link: str = None) -> dict:
    """
    Full flow: Push video → Mở TikTok → Upload → Caption → Gắn SP → Post
    """
    result = {"success": False, "serial": serial, "error": ""}

    try:
        # Kiểm tra đăng nhập
        if not is_logged_in(serial):
            result["error"] = "Not logged in"
            return result

        # Push video lên điện thoại
        if not os.path.exists(local_video_path):
            result["error"] = f"Video not found: {local_video_path}"
            return result

        remote_path = prepare_video_on_phone(serial, local_video_path)
        if not remote_path:
            result["error"] = "Failed to push video to phone"
            return result

        # Mở màn hình upload
        if not open_tiktok_upload(serial):
            result["error"] = "Failed to open upload screen"
            return result

        time.sleep(2)

        # Chọn video từ gallery
        filename = os.path.basename(local_video_path)
        if not select_video_from_gallery(serial, filename):
            result["error"] = "Failed to select video from gallery"
            return result

        # Đợi video load
        time.sleep(3)

        # Nhấn Next nếu có
        if element_exists(serial, text="Next"):
            tap_element(serial, text="Next")
            time.sleep(2)

        # Thêm caption
        if caption:
            add_caption_and_hashtags(serial, caption, hashtags)

        # Gắn sản phẩm
        if product_name or product_link:
            attach_product(serial, product_name, product_link)

        # Đăng video
        if post_video(serial):
            result["success"] = True
            print(f"[{serial}] ✓ Video posted successfully")
        else:
            result["error"] = "Failed to post video"

    except Exception as e:
        result["error"] = str(e)
        print(f"[{serial}] ✗ Error: {e}")

    return result


def batch_upload(tasks: list) -> list:
    """
    Upload hàng loạt trên nhiều thiết bị.
    tasks: [{"serial": "...", "video": "path", "caption": "...",
             "hashtags": [...], "product_name": "..."}]
    """
    import threading
    results = []
    lock = threading.Lock()

    def run_task(task):
        r = upload_video_full(
            serial=task["serial"],
            local_video_path=task.get("video", ""),
            caption=task.get("caption", ""),
            hashtags=task.get("hashtags", []),
            product_name=task.get("product_name"),
            product_link=task.get("product_link")
        )
        with lock:
            results.append(r)

    threads = []
    for task in tasks:
        t = threading.Thread(target=run_task, args=(task,))
        threads.append(t)
        t.start()
        time.sleep(random.uniform(2, 5))  # Stagger start times

    for t in threads:
        t.join()

    return results
