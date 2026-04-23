import re
with open('D:/Videos/TikTok/douyin_debug.html', encoding='utf-8') as f:
    c = f.read()
print(f'Page size: {len(c)}')
if 'verify' in c.lower()[:2000] or 'captcha' in c.lower()[:2000]:
    print('WAF/Captcha detected!')
urls = re.findall(r'https://[^\s"\'<>]+(?:mp4|douyinvod|amemv)[^\s"\'<>]*', c)
print(f'Video URLs: {len(urls)}')
for u in urls[:5]:
    print(' ', u[:120])
if 'RENDER_DATA' in c:
    m = re.search(r'id="RENDER_DATA"[^>]*>([^<]+)', c)
    if m:
        import urllib.parse
        data = urllib.parse.unquote(m.group(1))
        print(f'RENDER_DATA size: {len(data)}')
        video_urls = re.findall(r'https://[^"]+(?:douyinvod|amemv)[^"]+', data)
        print(f'Video CDN URLs in RENDER_DATA: {len(video_urls)}')
        for u in video_urls[:3]:
            print(' ', u[:120])
print('Has aweme:', 'aweme' in c.lower())
print('Has play_addr:', 'play_addr' in c)
print('Page preview:', c[:500])
