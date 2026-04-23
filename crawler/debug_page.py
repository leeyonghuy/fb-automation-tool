import re, json

with open('D:/Videos/TikTok/page_debug.html', encoding='utf-8') as f:
    content = f.read()

m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', content, re.DOTALL)
if m:
    try:
        d = json.loads(m.group(1))
        print("Top keys:", list(d.keys())[:10])
        
        def find_keys(obj, path='', depth=0):
            if depth > 8:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if any(x in k.lower() for x in ['video', 'play', 'item', 'aweme', 'url_list']):
                        print(f"  {path}.{k}: {str(v)[:120]}")
                    find_keys(v, path+'.'+k, depth+1)
            elif isinstance(obj, list):
                for i, v in enumerate(obj[:3]):
                    find_keys(v, path+f'[{i}]', depth+1)
        
        find_keys(d)
    except Exception as e:
        print(f"JSON parse error: {e}")
        # Just look for patterns
        urls = re.findall(r'https://[^\s"\'<>\\]+(?:mp4|video)[^\s"\'<>\\]*', m.group(1))
        print("Video URLs:", urls[:10])
else:
    print("Script tag not found")
    # Check what script tags exist
    scripts = re.findall(r'<script[^>]*id="([^"]+)"', content)
    print("Script ids:", scripts)
