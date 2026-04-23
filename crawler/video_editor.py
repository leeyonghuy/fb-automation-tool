#!/usr/bin/env python3
"""
Video Editor - Content Factory (Sayaz)
3 tầng xử lý:
  Tầng 1: Anti-copyright template (crop, speed, color, watermark "Sayaz")
  Tầng 2: Dịch + blur phụ đề gốc + phụ đề tiếng Việt + lồng tiếng TTS
  Tầng 3: AI Metadata - Gemini tạo caption/hashtag/title
"""

import os
import sys
import json
import logging
import subprocess
import random
import tempfile
import re
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = r"D:\Contenfactory\logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "video_editor.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  # Set env var GEMINI_API_KEY
EDITED_VIDEO_DIR = r"D:\Videos\Edited"
FFMPEG_CMD = os.environ.get("FFMPEG_CMD", "ffmpeg")
FFPROBE_CMD = os.environ.get("FFPROBE_CMD", "ffprobe")

os.makedirs(EDITED_VIDEO_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def get_video_duration(file_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        FFPROBE_CMD, "-v", "quiet", "-print_format", "json",
        "-show_format", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def get_video_dimensions(file_path: str) -> tuple:
    """Returns (width, height)."""
    cmd = [
        FFPROBE_CMD, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except Exception:
        return 1280, 720


def build_output_path(input_path: str, suffix: str = "_edited") -> str:
    """Build output path in EDITED_VIDEO_DIR."""
    name = Path(input_path).stem
    out_name = sanitize_filename(name) + suffix + ".mp4"
    return os.path.join(EDITED_VIDEO_DIR, out_name)


# ---------------------------------------------------------------------------
# TẦNG 1: Anti-Copyright Template
# ---------------------------------------------------------------------------

def apply_anticp_template(input_path: str, output_path: str = None,
                           brand_text: str = "Sayaz",
                           flip: bool = None) -> dict:
    """
    Áp dụng template chống bản quyền:
    - Crop 2% viền + scale lại về kích thước gốc
    - Thay đổi tốc độ ngẫu nhiên ±1.5%
    - Điều chỉnh màu nhẹ
    - Watermark chữ thương hiệu mờ 98% (alpha ~5/255)
    - Flip ngang ngẫu nhiên (hoặc theo tham số)
    - Xóa metadata
    - Re-encode H.264/AAC
    """
    if not output_path:
        output_path = build_output_path(input_path, "_t1")

    width, height = get_video_dimensions(input_path)

    # Random speed factor: 0.985 ~ 1.015
    speed_factor = round(random.uniform(0.985, 1.015), 4)
    audio_tempo = round(1.0 / speed_factor, 4)  # compensate audio tempo

    # Flip: random nếu không chỉ định
    do_flip = flip if flip is not None else random.choice([True, False])

    # Video filters
    vf_parts = []

    # 1. Crop 2% + scale lại
    crop_w = int(width * 0.98)
    crop_h = int(height * 0.98)
    crop_x = int(width * 0.01)
    crop_y = int(height * 0.01)
    vf_parts.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
    vf_parts.append(f"scale={width}:{height}")

    # 2. Flip ngang
    if do_flip:
        vf_parts.append("hflip")

    # 3. Điều chỉnh màu nhẹ
    brightness = round(random.uniform(0.01, 0.03), 3)
    saturation = round(random.uniform(1.02, 1.05), 3)
    vf_parts.append(f"eq=brightness={brightness}:saturation={saturation}")

    # 4. Watermark text "Sayaz" - mờ 98% (alpha=0.02)
    font_size = max(24, int(height * 0.04))
    # Đặt ở giữa dưới, alpha cực thấp
    vf_parts.append(
        f"drawtext=text='{brand_text}':fontsize={font_size}:"
        f"fontcolor=white@0.02:x=(w-text_w)/2:y=h-th-20"
    )

    # 5. Speed (setpts)
    vf_parts.append(f"setpts={round(1.0/speed_factor, 4)}*PTS")

    vf = ",".join(vf_parts)
    af = f"asetrate=44100*{speed_factor},aresample=44100,atempo={audio_tempo}"

    cmd = [
        FFMPEG_CMD, "-y", "-i", input_path,
        "-vf", vf,
        "-af", af,
        "-map_metadata", "-1",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]

    logger.info(f"[Tầng 1] Xử lý anti-copyright: {input_path}")
    logger.info(f"  speed={speed_factor}, flip={do_flip}, brightness={brightness}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            logger.info(f"  ✓ Tầng 1 xong: {output_path}")
            return {"success": True, "output_path": output_path, "error": None}
        else:
            err = result.stderr[-300:]
            logger.error(f"  ✗ ffmpeg lỗi: {err}")
            return {"success": False, "output_path": None, "error": err}
    except Exception as e:
        logger.error(f"  ✗ Exception: {e}")
        return {"success": False, "output_path": None, "error": str(e)}


# ---------------------------------------------------------------------------
# TẦNG 2: Dịch + Phụ đề Tiếng Việt + TTS
# ---------------------------------------------------------------------------

def extract_audio(video_path: str, audio_path: str) -> bool:
    """Trích xuất audio từ video sang WAV."""
    cmd = [
        FFMPEG_CMD, "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    return result.returncode == 0


def transcribe_and_translate_gemini(audio_path: str, source_lang: str = "zh") -> list:
    """
    Dùng Gemini API để nhận dạng giọng nói và dịch sang tiếng Việt.
    Trả về list segments: [{start, end, text_vi}]
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)

        # Upload audio file
        logger.info("  Upload audio lên Gemini...")
        audio_file = genai.upload_file(audio_path, mime_type="audio/wav")

        model = genai.GenerativeModel("gemini-1.5-pro")

        prompt = """Bạn là chuyên gia phiên âm và dịch thuật.
Hãy phiên âm toàn bộ nội dung audio này (tiếng Trung/Quảng Đông) và dịch sang tiếng Việt.
Trả về JSON array theo định dạng:
[
  {"start": 0.0, "end": 3.5, "text_vi": "Nội dung tiếng Việt..."},
  ...
]
CHỈ trả về JSON, không giải thích thêm."""

        response = model.generate_content([prompt, audio_file])
        raw = response.text.strip()

        # Parse JSON từ response
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if json_match:
            segments = json.loads(json_match.group())
            logger.info(f"  ✓ Gemini dịch xong: {len(segments)} đoạn")
            return segments
        else:
            logger.warning("  Không parse được JSON từ Gemini response")
            return []

    except ImportError:
        logger.error("  Chưa cài google-generativeai: pip install google-generativeai")
        return []
    except Exception as e:
        logger.error(f"  Lỗi Gemini transcribe: {e}")
        return []


def segments_to_srt(segments: list, srt_path: str):
    """Tạo file .srt từ danh sách segments."""
    def fmt_time(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}\n")
            f.write(f"{seg['text_vi']}\n\n")
    logger.info(f"  ✓ Tạo SRT: {srt_path}")


def blur_original_subtitles(video_path: str, output_path: str,
                             height_ratio: float = 0.12) -> bool:
    """
    Làm mờ vùng phụ đề gốc (dòng dưới cùng ~12% chiều cao).
    """
    _, height = get_video_dimensions(video_path)
    blur_h = int(height * height_ratio)
    blur_y = height - blur_h

    # Dùng boxblur trên vùng crop rồi overlay lại
    vf = (
        f"[0:v]split[main][blur];"
        f"[blur]crop=iw:{blur_h}:0:{blur_y},boxblur=20:5[blurred];"
        f"[main][blurred]overlay=0:{blur_y}"
    )

    cmd = [
        FFMPEG_CMD, "-y", "-i", video_path,
        "-filter_complex", vf,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode == 0:
        logger.info(f"  ✓ Blur phụ đề gốc xong")
        return True
    else:
        logger.error(f"  ✗ Blur lỗi: {result.stderr[-200:]}")
        return False


def add_vietnamese_subtitles(video_path: str, srt_path: str,
                              output_path: str) -> bool:
    """Render phụ đề tiếng Việt lên video."""
    # Escape path for ffmpeg filter
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

    vf = (
        f"subtitles='{srt_escaped}':force_style='"
        f"FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,Outline=2,Alignment=2,"
        f"MarginV=25'"
    )

    cmd = [
        FFMPEG_CMD, "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode == 0:
        logger.info(f"  ✓ Thêm phụ đề tiếng Việt xong")
        return True
    else:
        logger.error(f"  ✗ Subtitle lỗi: {result.stderr[-200:]}")
        return False


def generate_tts_vietnamese(segments: list, output_audio_path: str,
                             voice: str = "vi-VN-HoaiMyNeural") -> bool:
    """
    Tạo file audio tiếng Việt từ segments dùng edge-tts.
    Ghép các đoạn audio theo timestamp.
    """
    try:
        import edge_tts
        import asyncio

        async def _generate():
            # Tạo full text
            full_text = " ".join([s["text_vi"] for s in segments])
            communicate = edge_tts.Communicate(full_text, voice)
            await communicate.save(output_audio_path)

        asyncio.run(_generate())
        logger.info(f"  ✓ TTS tiếng Việt xong: {output_audio_path}")
        return True
    except ImportError:
        logger.error("  Chưa cài edge-tts: pip install edge-tts")
        return False
    except Exception as e:
        logger.error(f"  Lỗi TTS: {e}")
        return False


def merge_tts_audio(video_path: str, tts_audio_path: str, output_path: str) -> bool:
    """Thay audio gốc bằng TTS tiếng Việt."""
    # Mix: TTS chính + audio gốc rất nhỏ (5%) làm background
    cmd = [
        FFMPEG_CMD, "-y",
        "-i", video_path,
        "-i", tts_audio_path,
        "-filter_complex",
        "[0:a]volume=0.05[orig];[1:a]volume=1.0[tts];[orig][tts]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode == 0:
        logger.info(f"  ✓ Merge TTS audio xong")
        return True
    else:
        logger.error(f"  ✗ Merge audio lỗi: {result.stderr[-200:]}")
        return False


def apply_translation_layer(input_path: str, output_path: str = None,
                              with_tts: bool = True) -> dict:
    """
    Tầng 2 đầy đủ:
    1. Trích audio
    2. Gemini transcribe + dịch
    3. Blur phụ đề gốc
    4. Thêm phụ đề tiếng Việt
    5. (Optional) TTS lồng tiếng
    """
    if not output_path:
        output_path = build_output_path(input_path, "_t2")

    if not GEMINI_API_KEY:
        logger.error("  GEMINI_API_KEY chưa được cấu hình!")
        return {"success": False, "output_path": None, "error": "No GEMINI_API_KEY"}

    logger.info(f"[Tầng 2] Xử lý dịch & phụ đề: {input_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.wav")
        srt_path = os.path.join(tmpdir, "vi_subtitles.srt")
        blurred_path = os.path.join(tmpdir, "blurred.mp4")
        subbed_path = os.path.join(tmpdir, "subbed.mp4")
        tts_path = os.path.join(tmpdir, "tts.mp3")

        # 1. Trích audio
        logger.info("  [2.1] Trích xuất audio...")
        if not extract_audio(input_path, audio_path):
            return {"success": False, "output_path": None, "error": "Extract audio failed"}

        # 2. Gemini dịch
        logger.info("  [2.2] Gemini nhận dạng + dịch...")
        segments = transcribe_and_translate_gemini(audio_path)
        if not segments:
            logger.warning("  Không có segments, bỏ qua phụ đề")
            # Vẫn tiếp tục nhưng không có subtitles
            segments = []

        # 3. Tạo SRT
        if segments:
            segments_to_srt(segments, srt_path)

        # 4. Blur phụ đề gốc
        logger.info("  [2.3] Blur phụ đề gốc...")
        blur_ok = blur_original_subtitles(input_path, blurred_path)
        working_video = blurred_path if blur_ok else input_path

        # 5. Thêm phụ đề tiếng Việt
        if segments and os.path.exists(srt_path):
            logger.info("  [2.4] Thêm phụ đề tiếng Việt...")
            sub_ok = add_vietnamese_subtitles(working_video, srt_path, subbed_path)
            working_video = subbed_path if sub_ok else working_video

        # 6. TTS lồng tiếng
        if with_tts and segments:
            logger.info("  [2.5] Tạo TTS tiếng Việt...")
            tts_ok = generate_tts_vietnamese(segments, tts_path)
            if tts_ok:
                merge_ok = merge_tts_audio(working_video, tts_path, output_path)
                if merge_ok:
                    logger.info(f"  ✓ Tầng 2 xong (có TTS): {output_path}")
                    return {"success": True, "output_path": output_path,
                            "segments": segments, "error": None}

        # Copy working video to output nếu không có TTS
        import shutil
        shutil.copy2(working_video, output_path)
        logger.info(f"  ✓ Tầng 2 xong: {output_path}")
        return {"success": True, "output_path": output_path,
                "segments": segments, "error": None}


# ---------------------------------------------------------------------------
# TẦNG 3: AI Metadata với Gemini
# ---------------------------------------------------------------------------

def generate_ai_metadata(video_path: str, segments: list = None,
                          topic: str = "", platform: str = "tiktok") -> dict:
    """
    Dùng Gemini để tạo:
    - Tiêu đề hấp dẫn
    - Caption
    - Hashtag phù hợp
    Trả về dict: {title, caption, hashtags}
    """
    if not GEMINI_API_KEY:
        logger.error("  GEMINI_API_KEY chưa được cấu hình!")
        return {}

    logger.info(f"[Tầng 3] Tạo AI metadata...")

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Chuẩn bị transcript
        transcript = ""
        if segments:
            transcript = " ".join([s.get("text_vi", "") for s in segments])
        elif topic:
            transcript = f"Video về chủ đề: {topic}"

        platform_note = {
            "tiktok": "TikTok (ngắn gọn, trendy, dùng nhiều emoji)",
            "facebook": "Facebook (chi tiết hơn, storytelling)",
            "youtube": "YouTube (SEO-friendly, keyword rich)"
        }.get(platform, "mạng xã hội")

        prompt = f"""Bạn là chuyên gia content marketing Việt Nam cho {platform_note}.

Dựa trên nội dung video sau:
"{transcript[:1500]}"

Chủ đề: {topic}
Thương hiệu: Sayaz

Hãy tạo:
1. Tiêu đề hấp dẫn (tối đa 100 ký tự)
2. Caption (150-300 ký tự, có emoji)
3. 15-20 hashtag phù hợp

Trả về JSON:
{{
  "title": "...",
  "caption": "...",
  "hashtags": "#tag1 #tag2 ..."
}}"""

        response = model.generate_content(prompt)
        raw = response.text.strip()

        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            metadata = json.loads(json_match.group())
            logger.info(f"  ✓ AI metadata xong: {metadata.get('title', '')[:50]}")
            return metadata
        else:
            logger.warning("  Không parse được JSON metadata")
            return {"title": "", "caption": raw[:300], "hashtags": ""}

    except ImportError:
        logger.error("  Chưa cài google-generativeai: pip install google-generativeai")
        return {}
    except Exception as e:
        logger.error(f"  Lỗi Gemini metadata: {e}")
        return {}


# ---------------------------------------------------------------------------
# Pipeline tổng hợp
# ---------------------------------------------------------------------------

def process_video(input_path: str,
                  topic: str = "Uncategorized",
                  platform: str = "tiktok",
                  mode: str = "full",
                  with_tts: bool = True) -> dict:
    """
    Pipeline xử lý đầy đủ:
      mode="full"    → Tầng 1 + 2 + 3
      mode="anticp"  → Chỉ Tầng 1
      mode="translate" → Chỉ Tầng 2
      mode="metadata" → Chỉ Tầng 3

    Trả về:
      {
        "success": bool,
        "edited_path": str,
        "metadata": {title, caption, hashtags},
        "error": str
      }
    """
    logger.info("=" * 60)
    logger.info(f"BẮT ĐẦU XỬ LÝ VIDEO: {input_path}")
    logger.info(f"  mode={mode}, topic={topic}, platform={platform}")
    logger.info("=" * 60)

    if not os.path.exists(input_path):
        return {"success": False, "edited_path": None,
                "metadata": {}, "error": f"File không tồn tại: {input_path}"}

    result = {
        "success": False,
        "edited_path": input_path,
        "metadata": {},
        "error": None
    }

    segments = []

    # Tầng 1: Anti-copyright
    if mode in ("full", "anticp"):
        t1_out = build_output_path(input_path, "_t1")
        t1 = apply_anticp_template(input_path, t1_out)
        if t1["success"]:
            result["edited_path"] = t1_out
        else:
            result["error"] = f"Tầng 1 thất bại: {t1['error']}"
            return result

    # Tầng 2: Dịch & phụ đề
    if mode in ("full", "translate"):
        t2_input = result["edited_path"]
        t2_out = build_output_path(input_path, "_t2")
        t2 = apply_translation_layer(t2_input, t2_out, with_tts=with_tts)
        if t2["success"]:
            result["edited_path"] = t2_out
            segments = t2.get("segments", [])
        else:
            logger.warning(f"  Tầng 2 thất bại: {t2['error']} - giữ video Tầng 1")

    # Tầng 3: AI Metadata
    if mode in ("full", "metadata"):
        metadata = generate_ai_metadata(
            result["edited_path"],
            segments=segments,
            topic=topic,
            platform=platform
        )
        result["metadata"] = metadata

    result["success"] = True
    logger.info(f"✓ HOÀN THÀNH: {result['edited_path']}")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sayaz Video Editor")
    parser.add_argument("input", help="Đường dẫn video đầu vào")
    parser.add_argument("--topic", default="Uncategorized", help="Chủ đề video")
    parser.add_argument("--platform", choices=["tiktok", "facebook", "youtube"],
                        default="tiktok", help="Nền tảng đăng")
    parser.add_argument("--mode", choices=["full", "anticp", "translate", "metadata"],
                        default="full", help="Chế độ xử lý")
    parser.add_argument("--no-tts", action="store_true", help="Bỏ qua lồng tiếng TTS")
    args = parser.parse_args()

    result = process_video(
        args.input,
        topic=args.topic,
        platform=args.platform,
        mode=args.mode,
        with_tts=not args.no_tts
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
