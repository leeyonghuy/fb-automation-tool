import requests, os, sys, json, re

os.makedirs('D:/Videos/TikTok', exist_ok=True)
video_id = '7466476783476823337'
out = f'D:/Videos/TikTok/{video_id}.mp4'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

url = f'https://www.tiktok.com/@cgtn_official/video/{video_id}'
print(f"Fetching: {url}")
r = requests.get(url, headers=headers, timeout=30)
print(f"Status: {r.status_code}")
print("Content:")
print(r.text[:2000])
