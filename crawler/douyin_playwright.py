"""
Download Douyin video using Playwright - intercept video CDN bytes during playback.
"""
import os, sys, re, time, json
from playwright.sync_api import sync_playwright

os.makedirs('D:/Videos/TikTok', exist_ok=True)

video_data = bytearray()
video_meta = {'id': None, 'total': 0, 'title': ''}

def capture_video(route):
    try:
        resp = route.fetch()
        body = resp.body()
        ct = resp.headers.get('content-type', '')
        if len(body) > 50000 and ('video' in ct or 'octet' in ct):
            video_data.extend(body)
            video_meta['total'] += len(body)
            print(f"  Captured {len(body):,} bytes (total: {video_meta['total']:,})")
        route.fulfill(response=resp)
    except Exception as e:
        try:
            route.continue_()
        except:
            pass

with sync_playwright() as p:
    print("Launching Chromium...")
    browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 800},
        locale='zh-CN',
    )
    
    # Intercept video CDN requests for Douyin
    context.route(re.compile(r'(v\d+\-\w+\.douyinvod\.com|v\d+\.douyinvod|amemv\.com|bytefcdn|douyinvod)'), capture_video)
    
    page = context.new_page()

    # Try a trending Douyin video
    douyin_url = 'https://www.douyin.com/video/7484836618228048154'
    print(f"Loading: {douyin_url}")
    try:
        page.goto(douyin_url, wait_until='domcontentloaded', timeout=60000)
    except Exception as e:
        print(f"Nav: {e}")
    
    time.sleep(5)
    print(f"URL: {page.url}")
    
    # Extract video ID
    vid_match = re.search(r'/video/(\d+)', page.url) or re.search(r'/video/(\d+)', douyin_url)
    if vid_match:
        video_meta['id'] = vid_match.group(1)
    
    # Try to get video info from page
    content = page.content()
    
    # Look for title
    title_match = re.search(r'"desc"\s*:\s*"([^"]{5,100})"', content)
    if title_match:
        video_meta['title'] = title_match.group(1)
        print(f"Title: {video_meta['title']}")
    
    print("Waiting 15s for video playback...")
    time.sleep(15)
    
    # Scroll/click to ensure playback
    try:
        page.click('video', timeout=3000)
    except:
        pass
    time.sleep(5)
    
    print(f"\nTotal captured: {video_meta['total']:,} bytes")
    
    # If no bytes captured, try from page JSON directly
    if video_meta['total'] == 0:
        print("No video captured via intercept, trying page JSON...")
        content = page.content()
        
        # Save for debug
        with open('D:/Videos/TikTok/douyin_debug.html', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Find video URL in page data
        patterns = [
            r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["(https://[^"]+)"',
            r'"playApi"\s*:\s*"(https://[^"]+)"',
            r'(https://[^"\']+douyinvod[^"\']+\.mp4[^"\']*)',
            r'(https://[^"\']+amemv[^"\']+\.mp4[^"\']*)',
        ]
        VIDEO_URL = None
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                VIDEO_URL = m.group(1).replace('\\u0026', '&').replace('\\/', '/')
                print(f"Found URL: {VIDEO_URL[:100]}")
                break
        
        if VIDEO_URL:
            # Get cookies from browser
            cookies = context.cookies()
            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
            browser.close()
            
            import requests as req
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120',
                'Referer': 'https://www.douyin.com/',
                'Cookie': cookie_str,
            }
            r = req.get(VIDEO_URL, headers=headers, stream=True, timeout=60)
            print(f"Download status: {r.status_code}, CT: {r.headers.get('Content-Type')}")
            vid = video_meta['id'] or 'douyin_video'
            out = f'D:/Videos/TikTok/{vid}.mp4'
            with open(out, 'wb') as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
            size = os.path.getsize(out)
            print(f"✓ Downloaded: {out} ({size:,} bytes)")
            sys.exit(0)
        else:
            browser.close()
            print("❌ No video URL found")
            sys.exit(1)
    
    browser.close()

if len(video_data) > 100000:
    vid = video_meta['id'] or 'douyin_video'
    out = f'D:/Videos/TikTok/{vid}.mp4'
    with open(out, 'wb') as f:
        f.write(bytes(video_data))
    print(f"✓ Downloaded: {out} ({os.path.getsize(out):,} bytes)")
else:
    print(f"❌ Not enough video data: {len(video_data)} bytes")
    sys.exit(1)
