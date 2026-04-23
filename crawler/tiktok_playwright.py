"""
Download TikTok video - intercept actual video bytes during playback.
"""
import os, sys, re, time, json
from playwright.sync_api import sync_playwright

os.makedirs('D:/Videos/TikTok', exist_ok=True)

video_data = bytearray()
video_found = {'id': None, 'total': 0}

def capture_video(route):
    resp = route.fetch()
    body = resp.body()
    if len(body) > 10000:  # Only capture real video chunks (>10KB)
        video_data.extend(body)
        video_found['total'] += len(body)
        print(f"  Captured {len(body):,} bytes (total: {video_found['total']:,})")
    route.fulfill(response=resp)

with sync_playwright() as p:
    print("Launching Chromium...")
    browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 800},
    )
    
    # Intercept all video CDN requests
    context.route(re.compile(r'v\d+[-\w]*\.(tiktok|tiktokcdn|tiktokv)'), capture_video)
    
    page = context.new_page()

    print("Loading explore...")
    page.goto('https://www.tiktok.com/explore', wait_until='domcontentloaded', timeout=60000)
    time.sleep(4)

    links = page.query_selector_all('a[href*="/video/"]')
    if not links:
        browser.close()
        print("No links")
        sys.exit(1)

    href = links[0].get_attribute('href')
    vid_match = re.search(r'/video/(\d+)', href)
    VIDEO_ID = vid_match.group(1) if vid_match else 'tiktok_video'
    video_found['id'] = VIDEO_ID
    print(f"Going to: {href}")

    # Navigate and wait for video to auto-play
    page.goto(href, wait_until='domcontentloaded', timeout=60000)
    
    # Wait for video to start loading/playing
    print("Waiting for video playback (15s)...")
    time.sleep(15)
    
    # Try to click/unmute to ensure playback
    try:
        page.click('video', timeout=3000)
    except:
        pass
    time.sleep(5)
    
    print(f"Total captured: {video_found['total']:,} bytes")
    browser.close()

if len(video_data) > 100000:
    out = f'D:/Videos/TikTok/{video_found["id"]}.mp4'
    with open(out, 'wb') as f:
        f.write(bytes(video_data))
    print(f"✓ Downloaded: {out} ({os.path.getsize(out):,} bytes)")
else:
    print(f"❌ Not enough video data captured: {len(video_data)} bytes")
    # Show what was captured to debug
    if len(video_data) > 0:
        with open('D:/Videos/TikTok/partial.mp4', 'wb') as f:
            f.write(bytes(video_data))
    sys.exit(1)
