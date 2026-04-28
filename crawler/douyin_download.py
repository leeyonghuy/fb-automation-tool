"""
[DEPRECATED] Debug script — hardcode VIDEO_ID, chỉ dùng test 1 lần.

Dùng thay thế:
    python crawler/video_downloader.py <URL> --topic review_phim
Hoặc qua Dashboard UI.
"""
import os, sys, re, time, json, urllib.parse
from playwright.sync_api import sync_playwright

os.makedirs('D:/Videos/TikTok', exist_ok=True)

VIDEO_URL = None
VIDEO_ID = '7484836618228048154'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--no-sandbox'])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 800},
        locale='zh-CN',
    )
    page = context.new_page()
    
    page.goto(f'https://www.douyin.com/video/{VIDEO_ID}', wait_until='domcontentloaded', timeout=60000)
    time.sleep(8)
    
    content = page.content()
    
    # Extract URLs from page - zjcdn pattern
    patterns = [
        r'(https://v\d+-dy[^"\'\\]+\.zjcdn\.com/[^"\'\\]+)',
        r'(https://v\d+-dy[^"\'\\]+\.douyinvod\.com/[^"\'\\]+)',
        r'(https://[^"\'\\]+zjcdn\.com/[^"\'\\]+/video/[^"\'\\]+)',
    ]
    
    candidates = []
    for pat in patterns:
        matches = re.findall(pat, content)
        for m in matches:
            clean = m.replace('\\u0026', '&').replace('\\/', '/')
            if 'mp4' not in clean.lower() and len(clean) > 80:  # video CDN URLs don't always end in .mp4
                candidates.append(clean)
    
    print(f"Candidates: {len(candidates)}")
    for c in candidates[:5]:
        print(f"  {c[:120]}")
    
    # Also get from RENDER_DATA
    m = re.search(r'id="RENDER_DATA"[^>]*>([^<]+)', content)
    render_urls = []
    if m:
        data = urllib.parse.unquote(m.group(1))
        # zjcdn URLs
        render_urls = re.findall(r'https://v\d+-dy[^"]+zjcdn\.com/[^"]+', data)
        print(f"\nRENDER_DATA zjcdn URLs: {len(render_urls)}")
        for u in render_urls[:3]:
            print(f"  {u[:120]}")
    
    all_urls = candidates + render_urls
    # Pick first non-detect URL (prefer without 'detect')
    for u in all_urls:
        if 'detect' not in u and 'download' not in u.lower():
            VIDEO_URL = u
            break
    if not VIDEO_URL and all_urls:
        VIDEO_URL = all_urls[0]
    
    # Get cookies
    cookies = context.cookies()
    cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
    browser.close()

print(f"\nVideo URL: {VIDEO_URL[:120] if VIDEO_URL else 'None'}")

if not VIDEO_URL:
    sys.exit(1)

import requests as req
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.douyin.com/',
    'Cookie': cookie_str,
    'Accept': '*/*',
    'Range': 'bytes=0-',
}

out = f'D:/Videos/TikTok/{VIDEO_ID}.mp4'
print(f"Downloading to {out}...")
r = req.get(VIDEO_URL, headers=headers, stream=True, timeout=120)
print(f"Status: {r.status_code}, CT: {r.headers.get('Content-Type')}, Size: {r.headers.get('Content-Length')}")

if r.status_code not in (200, 206):
    print("Failed!")
    sys.exit(1)

with open(out, 'wb') as f:
    for chunk in r.iter_content(65536):
        f.write(chunk)

size = os.path.getsize(out)
print(f"✓ Done: {out} ({size:,} bytes)")
