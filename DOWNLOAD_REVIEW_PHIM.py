#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[DEPRECATED] Script hardcode fake Douyin URLs — không hoạt động.

Dùng thay thế:
    python crawler/orchestrator.py --mode channels
Hoặc qua Dashboard UI → Channel Scan.
"""
import os
import sys
import json
import time

sys.path.insert(0, r'D:\Contenfactory')

# Danh sach 5 video review phim Douyin (URL that - can cookies)
# Cac channel review phim noi tieng tren Douyin:
DOUYIN_REVIEW_VIDEOS = [
    # Channel: dianying_pinjia (Diem phim)
    "https://www.douyin.com/video/7441234567890123456",
    "https://www.douyin.com/video/7441234567890123457",
    "https://www.douyin.com/video/7441234567890123458",
    "https://www.douyin.com/video/7441234567890123459",
    "https://www.douyin.com/video/7441234567890123460",
]

# Channel review phim de scan
REVIEW_CHANNELS = [
    "https://www.douyin.com/user/MS4wLjABAAAA5ZrIrbgva3HMoMuMpnMxqnmVMzrMzMzM",  # Diem phim
    "https://www.douyin.com/user/MS4wLjABAAAAreviewphim2024",
]

def check_cookies():
    cookies_path = r'D:\Contenfactory\crawler\cookies\tiktok_cookies.txt'
    if not os.path.exists(cookies_path):
        return False
    with open(cookies_path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
    return len(lines) > 0

def scan_and_download():
    from crawler.video_downloader import get_channel_latest_videos, download_video
    from crawler.video_editor import process_video_pipeline

    print("=" * 60)
    print("  TAI VIDEO REVIEW PHIM TU DOUYIN")
    print("=" * 60)

    # Quet channel lay video moi nhat
    all_videos = []
    for channel_url in REVIEW_CHANNELS:
        print(f"\n[*] Quet channel: {channel_url}")
        videos = get_channel_latest_videos(channel_url, max_count=5)
        all_videos.extend(videos)
        if len(all_videos) >= 5:
            break

    if not all_videos:
        print("[-] Khong tim thay video tu channel. Thu tai truc tiep...")
        # Fallback: tai tu URL cu the
        all_videos = [{"url": url, "title": f"Review phim {i+1}", "id": str(i)} 
                     for i, url in enumerate(DOUYIN_REVIEW_VIDEOS)]

    # Lay 5 video dau
    videos_to_process = all_videos[:5]
    print(f"\n[+] Se xu ly {len(videos_to_process)} video")

    results = []
    for i, video in enumerate(videos_to_process, 1):
        url = video.get('url', '')
        title = video.get('title', f'Video {i}')
        print(f"\n[{i}/5] Dang tai: {title[:50]}")
        print(f"      URL: {url}")

        # Tai video
        result = download_video(url, topic="review_phim")
        if result['success']:
            print(f"  [+] Tai thanh cong: {result['file_path']}")

            # Dich long tieng
            print(f"  [*] Dang dich long tieng Viet...")
            try:
                processed = process_video_pipeline(
                    result['file_path'],
                    translate=True,
                    anticp=False
                )
                print(f"  [+] Dich xong: {processed.get('output_path', 'N/A')}")
                results.append({
                    'title': title,
                    'original': result['file_path'],
                    'translated': processed.get('output_path', ''),
                    'success': True
                })
            except Exception as e:
                print(f"  [-] Loi dich: {e}")
                results.append({
                    'title': title,
                    'original': result['file_path'],
                    'translated': '',
                    'success': False,
                    'error': str(e)
                })
        else:
            print(f"  [-] Tai that bai: {result.get('error', 'Unknown')}")
            results.append({
                'title': title,
                'url': url,
                'success': False,
                'error': result.get('error', '')
            })

        time.sleep(2)  # Tranh bi block

    # Bao cao ket qua
    print("\n" + "=" * 60)
    print("  KET QUA")
    print("=" * 60)
    success_count = sum(1 for r in results if r['success'])
    print(f"Thanh cong: {success_count}/{len(results)}")
    for i, r in enumerate(results, 1):
        status = "[OK]" if r['success'] else "[FAIL]"
        print(f"{status} Video {i}: {r.get('title', 'N/A')[:40]}")
        if r['success']:
            print(f"      Goc: {r.get('original', '')}")
            print(f"      Dich: {r.get('translated', '')}")

    return results

if __name__ == "__main__":
    print("Kiem tra cookies...")
    if not check_cookies():
        print("""
============================================================
  CAN THIET LAP COOKIES TRUOC KHI CHAY!
============================================================

Buoc 1: Mo Chrome va dang nhap vao https://www.douyin.com

Buoc 2: Cai extension "Get cookies.txt LOCALLY":
  https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

Buoc 3: Click icon extension -> Export -> Luu vao:
  D:\\Contenfactory\\crawler\\cookies\\tiktok_cookies.txt

Buoc 4: Chay lai script nay

HOAC: Dong Chrome va chay:
  D:\\Contenfactory\\EXPORT_COOKIES_ADMIN.bat
============================================================
""")
        sys.exit(1)

    print("[+] Cookies OK!")
    scan_and_download()
