#!/usr/bin/env python3
import os, sys, glob

# Write to log file directly
LOG = r"D:\Contenfactory\test_log.txt"

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode())

log("=== TEST WHISPER ===")

VIDEO_DIR = r"D:\Contenfactory\downloads\review_phim"
videos = glob.glob(os.path.join(VIDEO_DIR, "*.mp4"))
log(f"Tim thay {len(videos)} video:")
for v in videos:
    size = os.path.getsize(v)/1024/1024
    log(f"  {os.path.basename(v)[:60]} ({size:.1f}MB)")

try:
    import torch
    log(f"Torch: {torch.__version__}")
    log(f"CUDA: {torch.cuda.is_available()}")
except Exception as e:
    log(f"Loi torch: {e}")

try:
    import whisper
    log("Whisper: OK")
    log("Dang load model base...")
    model = whisper.load_model("base", device="cpu")
    log("Load model: OK")
    
    if videos:
        video = videos[0]
        log(f"Dang transcribe: {os.path.basename(video)[:50]}")
        result = model.transcribe(video, language="zh", fp16=False)
        segments = result.get('segments', [])
        log(f"Nhan dang duoc {len(segments)} doan")
        for seg in segments[:3]:
            log(f"  [{seg['start']:.1f}s] {seg['text'][:50]}")
except Exception as e:
    import traceback
    log(f"LOI: {e}")
    log(traceback.format_exc())

log("=== XONG ===")
