#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[DEPRECATED] — Dùng DICH_V2.py thay thế.

Script dich long tieng Viet cho cac video da tai ve (v1 legacy).
Vấn đề: hardcode path, không resume, chỉ gTTS, dùng googletrans (unstable).
Thay bằng: python DICH_V2.py --tts edge
"""
import os
import sys
import glob
import subprocess
import json
import io

# Fix encoding cho Windows terminal
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Log file de debug
LOG_FILE = r"D:\Contenfactory\dich_progress.log"
def log_progress(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except:
        pass

# Set ffmpeg path
FFMPEG = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\Scripts\ffmpeg.exe"
os.environ["FFMPEG_CMD"] = FFMPEG
os.environ["FFPROBE_CMD"] = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")

VIDEO_DIR = r"D:\Contenfactory\downloads\review_phim"
OUTPUT_DIR = r"D:\Contenfactory\downloads\review_phim_viet"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def check_deps():
    """Kiem tra cac thu vien can thiet"""
    missing = []
    try:
        import whisper
        print("[+] whisper OK")
    except ImportError:
        missing.append("openai-whisper")
    
    try:
        from googletrans import Translator
        print("[+] googletrans OK")
    except ImportError:
        missing.append("googletrans==4.0.0rc1")
    
    try:
        from gtts import gTTS
        print("[+] gTTS OK")
    except ImportError:
        missing.append("gTTS")
    
    try:
        import pydub
        print("[+] pydub OK")
    except ImportError:
        missing.append("pydub")
    
    return missing

def install_deps(missing):
    """Cai cac thu vien con thieu"""
    for pkg in missing:
        print(f"[*] Cai {pkg}...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)
    print("[+] Cai xong!")

def transcribe_video(video_path):
    """Dung Whisper de nhan dang giong noi"""
    import whisper
    import torch
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  [*] Dang nhan dang giong noi: {os.path.basename(video_path)}")
    print(f"  [*] Su dung device: {device.upper()}")
    if device == "cuda":
        print(f"  [*] GPU: {torch.cuda.get_device_name(0)}")
    
    model = whisper.load_model("base", device=device)
    result = model.transcribe(video_path, language="zh", fp16=(device=="cuda"))
    return result

def translate_to_vietnamese(segments):
    """Dich tung doan sang tieng Viet"""
    from googletrans import Translator
    translator = Translator()
    
    translated = []
    for seg in segments:
        try:
            text_zh = seg['text'].strip()
            if text_zh:
                result = translator.translate(text_zh, src='zh-cn', dest='vi')
                translated.append({
                    'start': seg['start'],
                    'end': seg['end'],
                    'original': text_zh,
                    'vietnamese': result.text
                })
                print(f"    ZH: {text_zh[:40]}")
                print(f"    VI: {result.text[:40]}")
        except Exception as e:
            print(f"    [!] Loi dich: {e}")
            translated.append({
                'start': seg['start'],
                'end': seg['end'],
                'original': seg['text'],
                'vietnamese': seg['text']
            })
    return translated

def create_srt(segments, output_path):
    """Tao file SRT tu cac doan da dich"""
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['vietnamese']}\n\n")
    print(f"  [+] Da tao SRT: {output_path}")

def create_tts_audio(segments, output_audio_path):
    """Tao audio TTS tieng Viet"""
    from gtts import gTTS
    from pydub import AudioSegment
    import tempfile
    
    print(f"  [*] Dang tao TTS tieng Viet...")
    
    # Tao audio cho tung doan
    combined = AudioSegment.silent(duration=0)
    
    for seg in segments:
        text_vi = seg['vietnamese']
        start_ms = int(seg['start'] * 1000)
        end_ms = int(seg['end'] * 1000)
        duration_ms = end_ms - start_ms
        
        if not text_vi.strip():
            combined += AudioSegment.silent(duration=duration_ms)
            continue
        
        try:
            # TTS
            tts = gTTS(text=text_vi, lang='vi', slow=False)
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp_path = tmp.name
            tts.save(tmp_path)
            
            # Load audio
            seg_audio = AudioSegment.from_mp3(tmp_path)
            os.unlink(tmp_path)
            
            # Dieu chinh toc do neu can
            if len(seg_audio) > duration_ms and duration_ms > 0:
                speed_factor = len(seg_audio) / duration_ms
                if speed_factor > 1.5:
                    speed_factor = 1.5
                seg_audio = seg_audio.speedup(playback_speed=speed_factor)
            
            # Padding neu can
            if len(seg_audio) < duration_ms:
                seg_audio += AudioSegment.silent(duration=duration_ms - len(seg_audio))
            
            combined += seg_audio[:duration_ms]
            
        except Exception as e:
            print(f"    [!] Loi TTS: {e}")
            combined += AudioSegment.silent(duration=duration_ms)
    
    # Luu audio
    combined.export(output_audio_path, format="mp3")
    print(f"  [+] Da tao TTS audio: {output_audio_path}")
    return output_audio_path

def merge_video_audio_sub(video_path, tts_audio_path, srt_path, output_path):
    """Gop video + TTS audio + phu de"""
    print(f"  [*] Dang gop video + audio + phu de...")
    
    cmd = [
        FFMPEG, "-y",
        "-i", video_path,
        "-i", tts_audio_path,
        "-vf", f"subtitles={srt_path}:force_style='FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [+] Xong: {output_path}")
        return True
    else:
        print(f"  [-] Loi ffmpeg: {result.stderr[-200:]}")
        return False

def process_video(video_path):
    """Xu ly 1 video: STT -> Dich -> TTS -> Gop"""
    basename = os.path.splitext(os.path.basename(video_path))[0]
    # Gioi han ten file
    safe_name = basename[:50].replace(' ', '_')
    
    srt_path = os.path.join(OUTPUT_DIR, f"{safe_name}_vi.srt")
    tts_path = os.path.join(OUTPUT_DIR, f"{safe_name}_tts.mp3")
    output_path = os.path.join(OUTPUT_DIR, f"{safe_name}_VIET.mp4")
    
    if os.path.exists(output_path):
        print(f"  [=] Da xu ly roi: {output_path}")
        return output_path
    
    print(f"\n{'='*50}")
    print(f"Xu ly: {basename[:60]}")
    print(f"{'='*50}")
    
    # Buoc 1: STT
    result = transcribe_video(video_path)
    segments = result.get('segments', [])
    print(f"  [+] Nhan dang duoc {len(segments)} doan")
    
    if not segments:
        print("  [-] Khong co giong noi, bo qua")
        return None
    
    # Buoc 2: Dich
    translated = translate_to_vietnamese(segments)
    
    # Buoc 3: Tao SRT
    create_srt(translated, srt_path)
    
    # Buoc 4: Tao TTS
    create_tts_audio(translated, tts_path)
    
    # Buoc 5: Gop
    success = merge_video_audio_sub(video_path, tts_path, srt_path, output_path)
    
    if success:
        return output_path
    return None

def main():
    print("="*60)
    print("  DICH LONG TIENG VIET CHO VIDEO REVIEW PHIM")
    print("="*60)
    
    # Kiem tra deps
    print("\n[*] Kiem tra thu vien...")
    missing = check_deps()
    if missing:
        print(f"[!] Thieu: {missing}")
        install_deps(missing)
    
    # Tim cac video da tai
    videos = glob.glob(os.path.join(VIDEO_DIR, "*.mp4"))
    videos += glob.glob(os.path.join(VIDEO_DIR, "*.webm"))
    
    if not videos:
        print(f"[-] Khong tim thay video trong: {VIDEO_DIR}")
        return
    
    print(f"\n[+] Tim thay {len(videos)} video:")
    for i, v in enumerate(videos, 1):
        size_mb = os.path.getsize(v) / 1024 / 1024
        print(f"  {i}. {os.path.basename(v)[:60]} ({size_mb:.1f}MB)")
    
    # Xu ly tung video
    results = []
    for i, video in enumerate(videos[:5], 1):
        print(f"\n[{i}/{min(5,len(videos))}] Bat dau xu ly...")
        output = process_video(video)
        results.append({
            'input': video,
            'output': output,
            'success': output is not None
        })
    
    # Bao cao
    print("\n" + "="*60)
    print("  KET QUA CUOI CUNG")
    print("="*60)
    success_count = sum(1 for r in results if r['success'])
    print(f"Thanh cong: {success_count}/{len(results)}")
    print(f"Thu muc output: {OUTPUT_DIR}")
    for r in results:
        status = "[OK]" if r['success'] else "[FAIL]"
        name = os.path.basename(r['input'])[:50]
        print(f"{status} {name}")
        if r['success']:
            print(f"     -> {r['output']}")

if __name__ == "__main__":
    main()
