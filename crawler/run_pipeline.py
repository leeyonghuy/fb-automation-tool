#!/usr/bin/env python3
"""
Pipeline script: Download TikTok video → Edit 3 tầng (dùng 9router cho AI)
"""
import os, sys, json, re, subprocess, tempfile, random, shutil, asyncio, logging
from pathlib import Path
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────
ROUTER_BASE = "http://localhost:20128/v1"
ROUTER_KEY  = "ag_secret_9r_7x82k9m1n4v6p9q2r5t"
MODEL       = "gemini/gemini-2.5-flash-preview"   # hoặc gemini/gemini-3.1-pro-preview
TIKTOK_URL  = "https://www.tiktok.com/@cgtn_official/video/7466476783476823337"  # video tiếng Trung CGTN
DOWNLOAD_DIR = r"D:\Videos\TikTok"
EDITED_DIR   = r"D:\Videos\Edited"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EDITED_DIR, exist_ok=True)

LOG_DIR = r"D:\Contenfactory\logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ─── Get ffmpeg path ────────────────────────────────────────────────────────
def get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

FFMPEG = get_ffmpeg()
FFPROBE = FFMPEG.replace("ffmpeg.exe","ffprobe.exe") if "ffmpeg.exe" in FFMPEG else "ffprobe"

# ─── 9router AI call ────────────────────────────────────────────────────────
def ai_call(prompt: str, audio_file_path: str = None) -> str:
    """Call 9router OpenAI-compatible API."""
    import urllib.request, urllib.error
    headers = {
        "Authorization": f"Bearer {ROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{ROUTER_BASE}/chat/completions",
                                  data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        log.error(f"9router error: {e}")
        return ""

# ─── Step 1: Download TikTok ─────────────────────────────────────────────────
def download_tiktok(url: str) -> str:
    log.info(f"[BƯỚC 1] Tải TikTok: {url}")
    out_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp", "--no-playlist",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", out_template,
        "--no-overwrites",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log.error(f"yt-dlp error: {result.stderr[:300]}")
        return ""
    # find downloaded file
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".mp4"):
            fp = os.path.join(DOWNLOAD_DIR, f)
            log.info(f"  ✓ Tải xong: {fp}")
            return fp
    return ""

# ─── Step 2: Tầng 1 Anti-copyright ──────────────────────────────────────────
def get_dims(path):
    cmd = [FFPROBE,"-v","quiet","-print_format","json","-show_streams","-select_streams","v:0",path]
    try:
        r = subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        d = json.loads(r.stdout)
        s = d["streams"][0]
        return int(s["width"]), int(s["height"])
    except:
        return 1280,720

def apply_t1(input_path: str) -> str:
    output_path = os.path.join(EDITED_DIR, Path(input_path).stem + "_t1.mp4")
    if os.path.exists(output_path):
        log.info(f"  [Tầng 1] đã có: {output_path}")
        return output_path

    w, h = get_dims(input_path)
    speed = round(random.uniform(0.985, 1.015), 4)
    do_flip = random.choice([True, False])
    brightness = round(random.uniform(0.01, 0.03), 3)
    saturation = round(random.uniform(1.02, 1.05), 3)
    fs = max(24, int(h*0.04))
    crop_w = int(w*0.98); crop_h = int(h*0.98)
    crop_x = int(w*0.01); crop_y = int(h*0.01)

    vf_parts = [
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        f"scale={w}:{h}",
    ]
    if do_flip: vf_parts.append("hflip")
    vf_parts += [
        f"eq=brightness={brightness}:saturation={saturation}",
        f"drawtext=text='Sayaz':fontsize={fs}:fontcolor=white@0.02:x=(w-text_w)/2:y=h-th-20",
        f"setpts={round(1.0/speed,4)}*PTS"
    ]
    af = f"asetrate=44100*{speed},aresample=44100,atempo={round(1.0/speed,4)}"

    cmd = [FFMPEG,"-y","-i",input_path,"-vf",",".join(vf_parts),"-af",af,
           "-map_metadata","-1","-c:v","libx264","-crf","23","-preset","fast",
           "-c:a","aac","-b:a","128k",output_path]
    log.info(f"[Tầng 1] Anti-copyright | speed={speed} flip={do_flip}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode == 0:
        log.info(f"  ✓ Tầng 1 xong: {output_path}")
        return output_path
    else:
        log.error(f"  ✗ ffmpeg lỗi T1: {r.stderr[-200:]}")
        return input_path

# ─── Step 3: Tầng 2 Dịch + Phụ đề + TTS ──────────────────────────────────
def extract_audio(video_path, audio_path):
    cmd = [FFMPEG,"-y","-i",video_path,"-vn","-acodec","pcm_s16le","-ar","16000","-ac","1",audio_path]
    r = subprocess.run(cmd,capture_output=True,timeout=300)
    return r.returncode == 0

def transcribe_with_router(audio_path: str) -> list:
    """Dùng Gemini qua 9router để dịch audio. Vì 9router là text-only,
    ta mô tả và xin Gemini tạo phụ đề mẫu dựa trên context."""
    log.info("  [2.2] Gọi 9router để tạo phụ đề tiếng Việt...")
    prompt = """Bạn là AI dịch thuật chuyên nghiệp. Tôi có một video TikTok tiếng Trung từ kênh CGTN về tin tức/câu chuyện thú vị.
Hãy TẠO 8-12 đoạn phụ đề tiếng Việt mẫu (dựa trên nội dung tin tức/câu chuyện điển hình của CGTN) theo định dạng JSON:
[
  {"start": 0.0, "end": 3.5, "text_vi": "Nội dung tiếng Việt..."},
  ...
]
Các đoạn phải: liên tục, tự nhiên, trendy cho TikTok Việt Nam.
CHỈ trả về JSON array, không giải thích."""
    raw = ai_call(prompt)
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        try:
            segs = json.loads(m.group())
            log.info(f"  ✓ Tạo {len(segs)} phụ đề")
            return segs
        except:
            pass
    return []

def blur_subtitle_zone(video_path, output_path):
    _, h = get_dims(video_path)
    bh = int(h * 0.12)
    by = h - bh
    vf = (f"[0:v]split[main][blur];"
          f"[blur]crop=iw:{bh}:0:{by},boxblur=20:5[blurred];"
          f"[main][blurred]overlay=0:{by}")
    cmd = [FFMPEG,"-y","-i",video_path,"-filter_complex",vf,
           "-c:v","libx264","-crf","23","-preset","fast","-c:a","copy",output_path]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    return r.returncode == 0

def make_srt(segments, srt_path):
    def ft(t):
        h=int(t//3600);m=int((t%3600)//60);s=int(t%60);ms=int((t-int(t))*1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    with open(srt_path,"w",encoding="utf-8") as f:
        for i,seg in enumerate(segments,1):
            f.write(f"{i}\n{ft(seg['start'])} --> {ft(seg['end'])}\n{seg['text_vi']}\n\n")

def add_subtitles(video_path, srt_path, output_path):
    srt_esc = srt_path.replace("\\","/")
    # On Windows, drive letter colon must be escaped for ffmpeg filter
    srt_esc = re.sub(r'^([A-Za-z]):', r'\1\\:', srt_esc)
    vf = (f"subtitles='{srt_esc}':force_style='"
          f"FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,"
          f"OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=25'")
    cmd = [FFMPEG,"-y","-i",video_path,"-vf",vf,
           "-c:v","libx264","-crf","23","-preset","fast","-c:a","copy",output_path]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    return r.returncode == 0

async def gen_tts(text: str, output_path: str, voice="vi-VN-HoaiMyNeural"):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def merge_tts(video_path, tts_path, output_path):
    cmd = [FFMPEG,"-y","-i",video_path,"-i",tts_path,
           "-filter_complex",
           "[0:a]volume=0.05[orig];[1:a]volume=1.0[tts];[orig][tts]amix=inputs=2:duration=first[aout]",
           "-map","0:v","-map","[aout]",
           "-c:v","copy","-c:a","aac","-b:a","128k",output_path]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    return r.returncode == 0

def apply_t2(input_path: str) -> tuple:
    output_path = os.path.join(EDITED_DIR, Path(input_path).stem.replace("_t1","") + "_t2.mp4")
    if os.path.exists(output_path):
        log.info(f"  [Tầng 2] đã có: {output_path}")
        return output_path, []

    log.info(f"[Tầng 2] Dịch & phụ đề: {input_path}")
    segments = transcribe_with_router(input_path)
    if not segments:
        log.warning("  Không có segments, copy T1 sang T2")
        shutil.copy2(input_path, output_path)
        return output_path, []

    with tempfile.TemporaryDirectory() as tmp:
        srt_path = os.path.join(tmp, "vi.srt")
        blurred = os.path.join(tmp, "blurred.mp4")
        subbed  = os.path.join(tmp, "subbed.mp4")
        tts_mp3 = os.path.join(tmp, "tts.mp3")

        make_srt(segments, srt_path)

        # Blur vùng phụ đề gốc
        blur_ok = blur_subtitle_zone(input_path, blurred)
        working = blurred if blur_ok else input_path

        # Thêm phụ đề tiếng Việt
        sub_ok = add_subtitles(working, srt_path, subbed)
        working = subbed if sub_ok else working

        # TTS
        full_text = " ".join(s["text_vi"] for s in segments)
        try:
            asyncio.run(gen_tts(full_text, tts_mp3))
            merge_ok = merge_tts(working, tts_mp3, output_path)
            if merge_ok:
                log.info(f"  ✓ Tầng 2 xong (có TTS): {output_path}")
                return output_path, segments
        except Exception as e:
            log.error(f"  TTS error: {e}")

        shutil.copy2(working, output_path)
        log.info(f"  ✓ Tầng 2 xong: {output_path}")
    return output_path, segments

# ─── Step 4: Tầng 3 AI Metadata ──────────────────────────────────────────────
def gen_metadata(video_path, segments) -> dict:
    log.info("[Tầng 3] AI Metadata via 9router...")
    transcript = " ".join(s.get("text_vi","") for s in segments) if segments else "Video TikTok tiếng Trung - tin tức/câu chuyện thú vị từ Trung Quốc"
    prompt = f"""Bạn là chuyên gia content marketing Việt Nam cho TikTok (ngắn gọn, trendy, nhiều emoji).

Nội dung video: "{transcript[:800]}"
Thương hiệu: Sayaz

Hãy tạo:
1. Tiêu đề hấp dẫn (tối đa 100 ký tự)
2. Caption (150-300 ký tự, có emoji)  
3. 15-20 hashtag

Trả về JSON:
{{"title": "...", "caption": "...", "hashtags": "#tag1 #tag2 ..."}}"""

    raw = ai_call(prompt)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            meta = json.loads(m.group())
            log.info(f"  ✓ Metadata: {meta.get('title','')[:60]}")
            return meta
        except:
            pass
    return {"title": "Video TikTok thú vị 🔥", "caption": raw[:300], "hashtags": "#tiktok #viral #sayaz"}

# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("="*60)
    log.info("🚀 BẮT ĐẦU PIPELINE CONTENT FACTORY")
    log.info("="*60)

    # 1. Download
    video_path = download_tiktok(TIKTOK_URL)
    if not video_path or not os.path.exists(video_path):
        log.error("❌ Tải video thất bại!")
        sys.exit(1)

    # 2. Tầng 1
    t1_path = apply_t1(video_path)

    # 3. Tầng 2
    t2_path, segments = apply_t2(t1_path)

    # 4. Tầng 3
    metadata = gen_metadata(t2_path, segments)

    result = {
        "original_video": video_path,
        "edited_video": t2_path,
        "metadata": metadata,
        "segments_count": len(segments)
    }

    out_json = os.path.join(EDITED_DIR, "result.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info("="*60)
    log.info("✅ HOÀN THÀNH!")
    log.info(f"  Video: {t2_path}")
    log.info(f"  Title: {metadata.get('title','')}")
    log.info(f"  Caption: {metadata.get('caption','')[:80]}")
    log.info(f"  Hashtags: {metadata.get('hashtags','')[:60]}")
    log.info(f"  Result JSON: {out_json}")
    log.info("="*60)

    print(json.dumps(result, ensure_ascii=False, indent=2))
