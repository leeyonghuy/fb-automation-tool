"""
create_profiles.py
Create 10 independent IX Browser profiles and open Facebook on each.
Each profile has unique fingerprint (screen, language, timezone, canvas noise).
"""

import requests
import random
import time
import json
import sys

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

IX_BASE = "http://127.0.0.1:53200/api/v2"

SCREEN_RESOLUTIONS = [
    [1920, 1080], [1366, 768], [1440, 900], [1280, 800],
    [1600, 900], [1280, 1024], [1920, 1200], [2560, 1440],
    [1024, 768], [1680, 1050]
]

TIMEZONES = [
    "Asia/Ho_Chi_Minh", "Asia/Bangkok", "Asia/Singapore",
    "Asia/Jakarta", "Asia/Kuala_Lumpur", "Asia/Manila",
    "America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Paris"
]

LANGUAGES = [
    "vi-VN,vi,en-US,en",
    "en-US,en",
    "en-GB,en",
    "th-TH,th,en",
    "id-ID,id,en",
    "ms-MY,ms,en",
    "ko-KR,ko,en",
    "ja-JP,ja,en",
    "zh-TW,zh,en",
    "fr-FR,fr,en",
]


def make_fingerprint(index: int) -> dict:
    """Create independent fingerprint config for each profile"""
    random.seed(index * 7919)
    screen = SCREEN_RESOLUTIONS[index % len(SCREEN_RESOLUTIONS)]
    tz = TIMEZONES[index % len(TIMEZONES)]
    lang = LANGUAGES[index % len(LANGUAGES)]

    return {
        "screen_width": screen[0],
        "screen_height": screen[1],
        "language": lang,
        "timezone": tz,
        "canvas": 1,
        "webgl": 1,
        "webgl_info": 1,
        "audio": 1,
        "fonts": 1,
        "do_not_track": random.choice([0, 1]),
        "hardware_concurrency": random.choice([2, 4, 6, 8]),
        "device_memory": random.choice([2, 4, 8]),
    }


def _post(path: str, payload: dict) -> dict:
    url = f"{IX_BASE}{path}"
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] POST {path}: {e}")
        return {}


def create_profile(name: str, index: int):
    """Create 1 profile with independent fingerprint"""
    fingerprint = make_fingerprint(index)
    payload = {
        "name": name,
        "site_url": "https://www.facebook.com",
        "fingerprint_config": fingerprint,
        "preference_config": {
            "start_url": "https://www.facebook.com",
        }
    }
    result = _post("/profile-create", payload)
    code = result.get("error", {}).get("code", -1)
    if code == 0:
        data = result.get("data")
        if isinstance(data, dict):
            profile_id = data.get("profile_id") or data.get("id")
        else:
            profile_id = data  # data is the profile_id directly
        print(f"  [OK] Profile [{name}] created -> ID: {profile_id}")
        return {"name": name, "profile_id": profile_id}
    else:
        msg = result.get("error", {}).get("message", "unknown")
        print(f"  [FAIL] Profile [{name}]: {msg}")
        print(f"         Raw: {result}")
        return None


def open_profile(profile_id) -> str:
    """Open profile, return ws endpoint"""
    result = _post("/profile-open", {"profile_id": profile_id})
    code = result.get("error", {}).get("code", -1)
    if code == 0:
        ws = result.get("data", {}).get("ws", "")
        print(f"  [OPEN] Profile {profile_id} | WS: {ws[:80]}")
        return ws
    else:
        msg = result.get("error", {}).get("message", "unknown")
        print(f"  [FAIL] Open profile {profile_id}: {msg}")
        return ""


def main():
    print("=" * 55)
    print("  Creating 10 IX Browser profiles + Open Facebook")
    print("=" * 55)

    # Step 1: Create 10 profiles
    created = []
    for i in range(1, 11):
        name = f"FB_Account_{i:02d}"
        print(f"\n[{i}/10] Creating: {name}")
        profile = create_profile(name, i)
        if profile:
            created.append(profile)
        time.sleep(0.5)

    print(f"\n[DONE] Created {len(created)}/10 profiles")

    if not created:
        print("No profiles created. Check IX Browser is running.")
        return

    # Step 2: Open Facebook on each profile
    print("\n" + "=" * 55)
    print("  Opening Facebook on each profile...")
    print("=" * 55)

    ws_list = []
    for i, p in enumerate(created):
        pid = p["profile_id"]
        name = p["name"]
        print(f"\n[{i+1}/{len(created)}] Opening {name} (ID: {pid})")
        ws = open_profile(pid)
        if ws:
            ws_list.append({"name": name, "profile_id": pid, "ws": ws})
        time.sleep(1)

    print(f"\n[DONE] Opened {len(ws_list)} profiles on Facebook")
    print("\nCDP endpoints:")
    for item in ws_list:
        print(f"  [{item['name']}] {item['ws']}")

    # Save profile list
    out_file = "d:/Contenfactory/content/nuoiaccfb/profiles_created.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(created, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVED] Profile list -> {out_file}")


if __name__ == "__main__":
    main()
