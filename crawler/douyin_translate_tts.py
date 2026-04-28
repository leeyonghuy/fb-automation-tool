"""
douyin_translate_tts.py

Fallback offline pipeline dịch video bằng:
  Whisper (transcribe) → deep-translator (vi) → edge-tts (TTS) → ffmpeg merge.

Dùng khi không có GEMINI_API_KEY hoặc muốn offline.

Usage:
    python douyin_translate_tts.py <input.mp4> [--output_dir DIR]
“Thiết kế hardcode 1 video cụ thể” cũ đã được thay bằng CLI args.
"""
import os, sys, re, json, subprocess, tempfile, asyncio, shutil, argparse

# Cho phép import config.py ở project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FFMPEG_CMD, EDITED_VIDEO_DIR, BASE_VIDEO_DIR  # noqa: E402

FFMPEG = FFMPEG_CMD
OUTPUT_DIR = EDITED_VIDEO_DIR
TMPDIR = os.path.join(BASE_VIDEO_DIR, "tmp_dub")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TMPDIR, exist_ok=True)

# Parse CLI
_parser = argparse.ArgumentParser(description="Whisper + deep-translator + edge-tts pipeline")
_parser.add_argument("input", nargs="?", help="Path to input mp4")
_parser.add_argument("--output_dir", default=OUTPUT_DIR)
_args = _parser.parse_args()

if not _args.input:
    print("Usage: python douyin_translate_tts.py <input.mp4> [--output_dir DIR]")
    sys.exit(2)

INPUT = _args.input
OUTPUT_DIR = _args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

if not os.path.isfile(INPUT):
    print(f"Input not found: {INPUT}")
    sys.exit(1)

# ── Step 1: Extract audio ─────────────────────────────────────────────────────
audio_wav = os.path.join(TMPDIR, 'audio.wav')
print("[1] Extracting audio...")
subprocess.run([FFMPEG, '-y', '-i', INPUT, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_wav], check=True, capture_output=True)
print(f"    Audio: {os.path.getsize(audio_wav):,} bytes")

# ── Step 2: Whisper transcribe ────────────────────────────────────────────────
print("[2] Whisper transcribe (auto-detect lang)...")
import whisper
model = whisper.load_model('small')
# auto-detect language, task=translate → translate to English first isn't needed
# transcribe in original language
result = model.transcribe(audio_wav, task='transcribe', fp16=False)
segments = result['segments']
detected_lang = result.get('language', 'unknown')
print(f"    Detected language: {detected_lang}")
print(f"    Transcribed {len(segments)} segments")
for s in segments[:3]:
    print(f"    [{s['start']:.1f}s] {s['text']}")

if not segments:
    # If still empty, try with verbose
    print("    No segments, retrying with tiny model...")
    model2 = whisper.load_model('tiny')
    result2 = model2.transcribe(audio_wav, fp16=False)
    segments = result2['segments']
    print(f"    Retry: {len(segments)} segments, lang={result2.get('language')}")

# ── Step 3: Translate -> vi ───────────────────────────────────────────────────
print("[3] Translating to Vietnamese...")
from deep_translator import GoogleTranslator

src_lang = detected_lang if detected_lang in ('zh', 'ko', 'ja', 'en') else 'auto'
lang_map = {'zh': 'zh-CN', 'ko': 'ko', 'ja': 'ja', 'en': 'en', 'auto': 'auto'}
src = lang_map.get(src_lang, 'auto')

translator = GoogleTranslator(source=src, target='vi')

vi_segments = []
for s in segments:
    text = s['text'].strip()
    if not text:
        continue
    try:
        vi_text = translator.translate(text)
    except Exception as e:
        vi_text = text
        print(f"    Trans error: {e}")
    vi_segments.append({'start': s['start'], 'end': s['end'], 'text_vi': vi_text or text})
    print(f"    {text[:40]} -> {(vi_text or text)[:40]}")

if not vi_segments:
    # Fallback: just use whisper translate task
    print("    No segments to translate, using whisper translate task...")
    result_en = model.transcribe(audio_wav, task='translate', fp16=False)
    for s in result_en['segments']:
        vi_segments.append({'start': s['start'], 'end': s['end'], 'text_vi': s['text'].strip()})
    print(f"    Got {len(vi_segments)} segments via Whisper translate")

# ── Step 4: Create SRT ────────────────────────────────────────────────────────
def fmt_time(t):
    h = int(t//3600); m = int((t%3600)//60); s = int(t%60); ms = int((t-int(t))*1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

srt_path = os.path.join(TMPDIR, 'vi.srt')
with open(srt_path, 'w', encoding='utf-8') as f:
    for i, seg in enumerate(vi_segments, 1):
        f.write(f"{i}\n{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}\n{seg['text_vi']}\n\n")
print(f"[4] SRT: {srt_path} ({len(vi_segments)} lines)")

# ── Step 5: TTS ───────────────────────────────────────────────────────────────
print("[5] Generating TTS...")
import edge_tts
full_text = ' '.join([s['text_vi'] for s in vi_segments])
print(f"    TTS text ({len(full_text)} chars): {full_text[:100]}")
tts_mp3 = os.path.join(TMPDIR, 'tts.mp3')

async def gen_tts():
    if not full_text.strip():
        return
    comm = edge_tts.Communicate(full_text, 'vi-VN-HoaiMyNeural')
    await comm.save(tts_mp3)
asyncio.run(gen_tts())
if os.path.exists(tts_mp3):
    print(f"    TTS: {os.path.getsize(tts_mp3):,} bytes")

# ── Step 6: Burn subtitle ────────────────────────────────────────────────────
print("[6] Burning subtitles...")
subbed = os.path.join(TMPDIR, 'subbed.mp4')
# SRT path for ffmpeg on Windows: D\:/path/to/file.srt
srt_ffmpeg = srt_path.replace('\\', '/').replace(':', '\\:')
vf = (f"subtitles='{srt_ffmpeg}':force_style='"
      f"FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,"
      f"OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=20'")
r = subprocess.run([FFMPEG, '-y', '-i', INPUT, '-vf', vf,
                '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
                '-c:a', 'copy', subbed], capture_output=True, text=True)
if r.returncode != 0:
    print(f"    subtitle err: {r.stderr[-300:]}")
    # Try without subtitles
    shutil.copy2(INPUT, subbed)
    print("    Fallback: no subtitle burn")
else:
    print(f"    Subtitles burned OK")

# ── Step 7: Merge TTS audio ───────────────────────────────────────────────────
_stem = os.path.splitext(os.path.basename(INPUT))[0]
out = os.path.join(OUTPUT_DIR, f'{_stem}_vi.mp4')
if os.path.exists(tts_mp3) and os.path.getsize(tts_mp3) > 1000:
    print("[7] Merging TTS audio...")
    r2 = subprocess.run([
        FFMPEG, '-y', '-i', subbed, '-i', tts_mp3,
        '-filter_complex', '[0:a]volume=0.05[orig];[1:a]volume=1.0[tts];[orig][tts]amix=inputs=2:duration=first[aout]',
        '-map', '0:v', '-map', '[aout]',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', out
    ], capture_output=True, text=True)
    if r2.returncode != 0:
        print(f"    merge err: {r2.stderr[-200:]}")
        shutil.copy2(subbed, out)
    else:
        print(f"    Merged OK")
else:
    shutil.copy2(subbed, out)
    print("[7] No TTS, copy subbed video")

print(f"\n✓ Done! Output: {out}")
print(f"   Size: {os.path.getsize(out):,} bytes")
print(f"\nSample translations:")
for seg in vi_segments[:5]:
    print(f"  [{seg['start']:.1f}s] {seg['text_vi']}")
