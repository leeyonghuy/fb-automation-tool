"""Extract full URLs from saved debug HTML and download."""
import re, os, urllib.parse
import requests

with open('D:/Videos/TikTok/douyin_debug.html', encoding='utf-8') as f:
    c = f.read()

# Get all zjcdn video URLs
urls = re.findall(r'https://v\d+-dy[^\s"\'\\>]+zjcdn\.com[^\s"\'\\>]+', c)
# Also try direct URL from the page
urls2 = re.findall(r'https://v\d+-dy[^\s"\'\\>]+', c)
print(f"zjcdn URLs: {len(urls)}")
for u in urls[:5]:
    print(f"  {u[:150]}")

# Check RENDER_DATA with full unescape
m = re.search(r'id="RENDER_DATA"[^>]*>([^<]+)', c)
render_data_urls = []
if m:
    raw = m.group(1)
    data = urllib.parse.unquote(raw)
    # Find all CDN video URLs
    render_data_urls = re.findall(r'https://[^\s"]+(?:zjcdn|douyinvod|amemv)[^\s"]+', data)
    print(f"\nRENDER_DATA all CDN URLs: {len(render_data_urls)}")
    for u in render_data_urls[:5]:
        print(f"  {u[:150]}")

all_candidates = urls + render_data_urls
# Filter: exclude detect, prefer longer URLs (full URL with params)
good = [u for u in all_candidates if 'detect' not in u and len(u) > 100]
print(f"\nGood candidates: {len(good)}")

if not good:
    # Try any
    good = all_candidates
    
if not good:
    print("No URLs found!")
    exit(1)

VIDEO_URL = good[0]
print(f"\nTrying: {VIDEO_URL[:150]}")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.douyin.com/',
}
r = requests.get(VIDEO_URL, headers=headers, stream=True, timeout=60)
print(f"Status: {r.status_code}, CT: {r.headers.get('Content-Type')}, Size: {r.headers.get('Content-Length')}")

if r.status_code == 200:
    out = 'D:/Videos/TikTok/douyin_7484836618228048154.mp4'
    with open(out, 'wb') as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
    print(f"✓ Saved: {out} ({os.path.getsize(out):,} bytes)")
else:
    print("Failed, trying second URL...")
    if len(good) > 1:
        r2 = requests.get(good[1], headers=headers, stream=True, timeout=60)
        print(f"Status2: {r2.status_code}")
