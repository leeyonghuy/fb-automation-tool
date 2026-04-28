#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DICH_V2.py — Pipeline lồng tiếng video TQ → VN.

Pipeline: Whisper STT -> dịch (deep-translator) -> TTS -> ffmpeg merge + sub.

Tính năng:
  - CLI args (argparse) cho input/output/limit/model/lang/tts engine.
  - Resume thông minh: cache segments.json, SRT, TTS audio để chạy lại không tốn.
  - 3 TTS engine: gtts (mặc định), edge (chất lượng tốt, miễn phí), vieneu (local).
  - Tuỳ chọn giữ giọng gốc nền (--keep-original-audio) mix -20dB.
  - Lưu meta JSON (segments ZH+VI+duration) cho từng video → dùng làm caption.
  - Push event vào status_tracker.py để Dashboard thấy.
  - Retry dịch với backoff, không truncate câu.
  - Guard pydub.speedup.

Ví dụ:
  python DICH_V2.py                              # mặc định: chạy tất cả video trong review_phim
  python DICH_V2.py --limit 2 --tts edge         # chạy 2 video, dùng edge-tts
  python DICH_V2.py --model small --keep-original-audio
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Path bootstrap: cho phép import config.py + status_tracker.py từ project root
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import config  # type: ignore
except Exception:
    config = None  # type: ignore

try:
    import status_tracker  # type: ignore
except Exception:
    status_tracker = None  # type: ignore


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dịch + lồng tiếng video TQ → VN")
    p.add_argument("--input", default=None, help="Thư mục video gốc (.mp4)")
    p.add_argument("--output", default=None, help="Thư mục output")
    p.add_argument("--limit", type=int, default=0, help="Giới hạn số video (0 = tất cả)")
    p.add_argument("--start-from", type=int, default=0, help="Bỏ qua N video đầu")
    p.add_argument("--model", default="base",
                   choices=["tiny", "base", "small", "medium", "large"],
                   help="Whisper model size")
    p.add_argument("--lang-src", default="zh", help="Ngôn ngữ nguồn cho Whisper (zh/en/ja/auto)")
    p.add_argument("--tts", default="gtts", choices=["gtts", "edge", "vieneu"],
                   help="TTS engine")
    p.add_argument("--edge-voice", default="vi-VN-NamMinhNeural",
                   help="Voice cho edge-tts (vd: vi-VN-NamMinhNeural, vi-VN-HoaiMyNeural)")
    p.add_argument("--vieneu-voice", default="Xuân Vĩnh",
                   help="Voice cho vieneu-tts")
    p.add_argument("--keep-original-audio", action="store_true",
                   help="Mix giọng gốc nền -20dB")
    p.add_argument("--orig-volume-db", type=float, default=-20.0,
                   help="Mức volume giọng gốc khi mix (dB)")
    p.add_argument("--no-burn-sub", action="store_true",
                   help="Không burn subtitle vào video (để soft sub bằng -c:s mov_text)")
    p.add_argument("--no-resume", action="store_true",
                   help="Chạy lại từ đầu, không dùng cache")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "dich_v2.log"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    logger = logging.getLogger("dich_v2")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------------------
# Lazy deps install + import
# ---------------------------------------------------------------------------

def _pip_install(pkg: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"],
                   capture_output=True)


def import_or_install(import_name: str, pip_name: str | None = None):
    pip_name = pip_name or import_name
    try:
        return __import__(import_name)
    except Exception:
        _pip_install(pip_name)
        return __import__(import_name)


# ---------------------------------------------------------------------------
# ffmpeg discovery
# ---------------------------------------------------------------------------

def find_ffmpeg(log: logging.Logger) -> str | None:
    if config and getattr(config, "FFMPEG_CMD", None) and config.FFMPEG_CMD != "ffmpeg":
        if os.path.exists(config.FFMPEG_CMD):
            return config.FFMPEG_CMD
    candidates = [
        r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\Scripts\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True)
        if result.returncode == 0:
            line = result.stdout.strip().split("\n")[0]
            if line:
                return line
    except FileNotFoundError:
        pass
    log.warning("Không tìm thấy ffmpeg!")
    return None


# ---------------------------------------------------------------------------
# SRT helpers
# ---------------------------------------------------------------------------

def format_time_srt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: str, segments: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time_srt(seg['start'])} --> {format_time_srt(seg['end'])}\n")
            f.write(f"{seg['vi']}\n\n")


# ---------------------------------------------------------------------------
# Translate (deep-translator with retry)
# ---------------------------------------------------------------------------

def translate_segments(segments: list[dict], src: str, log: logging.Logger) -> list[dict]:
    GoogleTranslator = import_or_install("deep_translator", "deep-translator")
    from deep_translator import GoogleTranslator  # type: ignore

    # deep-translator dùng "zh-CN" chứ không phải "zh"
    src_map = {"zh": "zh-CN", "auto": "auto"}
    src_code = src_map.get(src, src)

    translator = GoogleTranslator(source=src_code, target="vi")
    out = []
    for i, seg in enumerate(segments):
        text_zh = (seg.get("text") or "").strip()
        if not text_zh:
            out.append({"start": seg["start"], "end": seg["end"], "zh": "", "vi": ""})
            continue
        vi = None
        for attempt in range(3):
            try:
                # deep-translator hỗ trợ chunks tự động, nhưng giới hạn 5000 char/req
                vi = translator.translate(text_zh[:4500])
                break
            except Exception as e:
                log.warning(f"  Dịch lỗi đoạn {i} (lần {attempt + 1}/3): {e}")
                time.sleep(1.5 * (attempt + 1))
        if vi is None:
            log.error(f"  Không dịch được đoạn {i}, giữ tiếng gốc")
            vi = text_zh
        out.append({"start": seg["start"], "end": seg["end"], "zh": text_zh, "vi": vi})
        if i < 3:
            log.info(f"  ZH: {text_zh[:50]}")
            log.info(f"  VI: {vi[:50]}")
    return out


# ---------------------------------------------------------------------------
# TTS engines
# ---------------------------------------------------------------------------

def tts_gtts(text: str, out_mp3: str) -> None:
    from gtts import gTTS  # type: ignore
    # gTTS có giới hạn ~200 char nhưng tự xử lý chunk khi text dài;
    # vẫn chia nhỏ để chắc chắn không bị 5xx.
    chunks = _split_text_for_tts(text, max_len=200)
    if len(chunks) == 1:
        gTTS(text=chunks[0], lang="vi", slow=False).save(out_mp3)
        return
    from pydub import AudioSegment  # type: ignore
    combined = AudioSegment.silent(duration=0)
    for ch in chunks:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            gTTS(text=ch, lang="vi", slow=False).save(tmp_path)
            combined += AudioSegment.from_mp3(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    combined.export(out_mp3, format="mp3")


def tts_edge(text: str, out_mp3: str, voice: str) -> None:
    edge_tts = import_or_install("edge_tts", "edge-tts")
    import edge_tts  # type: ignore

    async def _run():
        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(out_mp3)

    asyncio.run(_run())


def tts_vieneu(text: str, out_mp3: str, voice: str) -> None:
    """VieNeu trả ra WAV, convert sang MP3 sau."""
    vieneu_path = Path(r"D:\Contenfactory\libs\vieneu-tts\src")
    if vieneu_path.exists() and str(vieneu_path) not in sys.path:
        sys.path.insert(0, str(vieneu_path))
    sys.path.insert(0, str(_ROOT / "crawler"))
    from tts_engine import text_to_speech  # type: ignore
    from pydub import AudioSegment  # type: ignore

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    try:
        text_to_speech(text, output_path=wav_path, voice=voice)
        AudioSegment.from_wav(wav_path).export(out_mp3, format="mp3")
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def _split_text_for_tts(text: str, max_len: int = 200) -> list[str]:
    """Cắt text thành chunk theo dấu câu, mỗi chunk <= max_len."""
    text = text.strip()
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    cur = ""
    for piece in _iter_sentences(text):
        if len(cur) + len(piece) + 1 <= max_len:
            cur = (cur + " " + piece).strip()
        else:
            if cur:
                chunks.append(cur)
            # piece có thể vẫn quá dài → cắt cứng
            while len(piece) > max_len:
                chunks.append(piece[:max_len])
                piece = piece[max_len:]
            cur = piece
    if cur:
        chunks.append(cur)
    return chunks


def _iter_sentences(text: str) -> Iterable[str]:
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?。！？,;，；":
            if buf.strip():
                yield buf.strip()
            buf = ""
    if buf.strip():
        yield buf.strip()


def synthesize_segments(translated: list[dict], out_mp3: str, args: argparse.Namespace,
                        log: logging.Logger) -> None:
    """Tạo audio TTS đồng bộ thời lượng theo segments, ghép thành 1 MP3."""
    from pydub import AudioSegment  # type: ignore

    combined = AudioSegment.silent(duration=0)
    cursor_ms = 0  # vị trí hiện tại trong combined

    for i, seg in enumerate(translated):
        start_ms = int(seg["start"] * 1000)
        end_ms = int(seg["end"] * 1000)
        dur_ms = max(end_ms - start_ms, 0)
        text_vi = (seg.get("vi") or "").strip()

        # Chèn silence để khớp start
        if start_ms > cursor_ms:
            combined += AudioSegment.silent(duration=start_ms - cursor_ms)
            cursor_ms = start_ms

        if not text_vi or dur_ms <= 0:
            combined += AudioSegment.silent(duration=max(dur_ms, 100))
            cursor_ms += max(dur_ms, 100)
            continue

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            try:
                if args.tts == "gtts":
                    tts_gtts(text_vi, tmp_path)
                elif args.tts == "edge":
                    tts_edge(text_vi, tmp_path, args.edge_voice)
                elif args.tts == "vieneu":
                    tts_vieneu(text_vi, tmp_path, args.vieneu_voice)
                else:
                    raise ValueError(f"TTS engine không hợp lệ: {args.tts}")
                seg_audio = AudioSegment.from_file(tmp_path)
            except Exception as e:
                log.warning(f"  TTS lỗi đoạn {i}: {e}")
                seg_audio = AudioSegment.silent(duration=max(dur_ms, 100))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        seg_audio = _fit_audio_to_duration(seg_audio, dur_ms)
        combined += seg_audio
        cursor_ms += len(seg_audio)

    combined.export(out_mp3, format="mp3")
    log.info(f"  TTS combined: {len(combined) / 1000:.1f}s -> {out_mp3}")


def _fit_audio_to_duration(seg_audio, dur_ms: int):
    """Co/giãn audio cho khớp dur_ms, an toàn với pydub.speedup."""
    from pydub import AudioSegment  # type: ignore

    if dur_ms <= 0:
        return AudioSegment.silent(duration=100)

    # Quá ngắn → pad silence
    if len(seg_audio) <= dur_ms:
        return seg_audio + AudioSegment.silent(duration=dur_ms - len(seg_audio))

    # Dài hơn → speedup nếu speed hợp lý, còn lại cắt cuối
    speed = len(seg_audio) / dur_ms
    if speed <= 1.5 and len(seg_audio) >= 200:  # speedup an toàn cho clip >= 200ms
        try:
            sped = seg_audio.speedup(playback_speed=min(speed, 1.5))
            if len(sped) > dur_ms:
                sped = sped[:dur_ms]
            elif len(sped) < dur_ms:
                sped = sped + AudioSegment.silent(duration=dur_ms - len(sped))
            return sped
        except Exception:
            pass
    return seg_audio[:dur_ms]


# ---------------------------------------------------------------------------
# Whisper transcribe (with cache)
# ---------------------------------------------------------------------------

def transcribe(video_path: str, segments_cache: str, model_size: str, lang: str,
               log: logging.Logger, no_resume: bool) -> list[dict] | None:
    if not no_resume and os.path.exists(segments_cache):
        try:
            with open(segments_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
            log.info(f"  Dùng cache transcribe: {segments_cache} ({len(data)} segs)")
            return data
        except Exception as e:
            log.warning(f"  Cache hỏng, transcribe lại: {e}")

    import torch  # type: ignore
    import whisper  # type: ignore
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"  Whisper device: {device}, model: {model_size}")
    model = whisper.load_model(model_size, device=device)
    kwargs = {"fp16": (device == "cuda")}
    if lang and lang != "auto":
        kwargs["language"] = lang
    result = model.transcribe(video_path, **kwargs)
    segments = result.get("segments", [])
    out = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segments]
    log.info(f"  Whisper xong: {len(out)} segs")
    try:
        with open(segments_cache, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"  Không ghi được cache transcribe: {e}")
    return out


# ---------------------------------------------------------------------------
# ffmpeg merge
# ---------------------------------------------------------------------------

def _escape_srt_for_ffmpeg(srt_path: str) -> str:
    return srt_path.replace("\\", "/").replace(":", "\\:")


def merge_video(video_path: str, tts_mp3: str, srt_path: str, output_path: str,
                ffmpeg: str, args: argparse.Namespace, log: logging.Logger) -> bool:
    if not ffmpeg:
        log.error("  Thiếu ffmpeg, không merge được")
        return False

    burn_sub = not args.no_burn_sub
    keep_orig = args.keep_original_audio

    cmd: list[str] = [ffmpeg, "-y", "-i", video_path, "-i", tts_mp3]

    # Audio mapping
    if keep_orig:
        # mix: input0 audio (volume=...) + input1 audio
        filter_a = (
            f"[0:a]volume={args.orig_volume_db}dB[orig];"
            f"[orig][1:a]amix=inputs=2:duration=longest:dropout_transition=0[aout]"
        )
        if burn_sub:
            filter_v = f"[0:v]subtitles='{_escape_srt_for_ffmpeg(srt_path)}':"\
                       f"force_style='FontSize=16,PrimaryColour=&H00FFFFFF,"\
                       f"OutlineColour=&H00000000,Outline=2'[vout]"
            cmd += ["-filter_complex", f"{filter_v};{filter_a}",
                    "-map", "[vout]", "-map", "[aout]"]
        else:
            cmd += ["-filter_complex", filter_a, "-map", "0:v", "-map", "[aout]"]
    else:
        if burn_sub:
            cmd += ["-vf",
                    f"subtitles='{_escape_srt_for_ffmpeg(srt_path)}':"
                    f"force_style='FontSize=16,PrimaryColour=&H00FFFFFF,"
                    f"OutlineColour=&H00000000,Outline=2'",
                    "-map", "0:v", "-map", "1:a"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]

    cmd += ["-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", output_path]

    log.info(f"  ffmpeg: {' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode == 0:
        size = os.path.getsize(output_path) / 1024 / 1024
        log.info(f"  XONG: {output_path} ({size:.1f}MB)")
        return True

    log.error(f"  ffmpeg lỗi (code {result.returncode}): {result.stderr[-400:]}")

    # Fallback: bỏ sub, không mix
    log.info("  Thử fallback merge không sub, không mix...")
    fallback = [ffmpeg, "-y", "-i", video_path, "-i", tts_mp3,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                "-shortest", output_path]
    r2 = subprocess.run(fallback, capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    if r2.returncode == 0:
        log.info(f"  XONG (fallback): {output_path}")
        return True
    log.error(f"  Fallback ffmpeg cũng lỗi: {r2.stderr[-300:]}")
    return False


# ---------------------------------------------------------------------------
# Process 1 video
# ---------------------------------------------------------------------------

def safe_basename(path: str, max_len: int = 40) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    cleaned = "".join(c if c.isalnum() or c in " _-" else "_" for c in base)
    return cleaned[:max_len].strip() or "video"


def process_video(video_path: str, output_dir: str, ffmpeg: str,
                  args: argparse.Namespace, log: logging.Logger,
                  task_id: str | None = None) -> str | None:
    safe = safe_basename(video_path)
    segments_json = os.path.join(output_dir, f"{safe}_segments.json")
    meta_json = os.path.join(output_dir, f"{safe}_meta.json")
    srt_path = os.path.join(output_dir, f"{safe}_vi.srt")
    tts_path = os.path.join(output_dir, f"{safe}_tts.mp3")
    output_path = os.path.join(output_dir, f"{safe}_VIET.mp4")

    if not args.no_resume and os.path.exists(output_path):
        log.info(f"  Đã có output, skip: {output_path}")
        if status_tracker and task_id:
            status_tracker.update_task(task_id, status="done", progress=100,
                                       message="Đã có output (resume skip)",
                                       output_data={"output": output_path, "skipped": True})
        return output_path

    log.info(f"\n{'=' * 60}")
    log.info(f"Xử lý: {os.path.basename(video_path)[:60]}")
    log.info(f"{'=' * 60}")

    # 1. Whisper
    log.info(f"[1/5] Whisper transcribe...")
    if status_tracker and task_id:
        status_tracker.update_task(task_id, status="running", progress=10,
                                   message="Whisper transcribe")
    try:
        segments = transcribe(video_path, segments_json, args.model, args.lang_src,
                              log, args.no_resume)
    except Exception as e:
        log.error(f"  Whisper lỗi: {e}\n{traceback.format_exc()}")
        if status_tracker and task_id:
            status_tracker.finish_task(task_id, False, f"Whisper lỗi: {e}")
        return None
    if not segments:
        log.error("  Không có segment nào!")
        if status_tracker and task_id:
            status_tracker.finish_task(task_id, False, "Không có giọng nói")
        return None

    # 2. Translate (cache qua meta_json)
    log.info(f"[2/5] Dịch tiếng Việt ({len(segments)} segs)...")
    if status_tracker and task_id:
        status_tracker.update_task(task_id, progress=35, message="Dịch tiếng Việt")
    translated: list[dict] | None = None
    if not args.no_resume and os.path.exists(meta_json):
        try:
            with open(meta_json, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("segments") and len(cached["segments"]) == len(segments):
                translated = cached["segments"]
                log.info(f"  Dùng cache dịch: {meta_json}")
        except Exception:
            translated = None
    if translated is None:
        translated = translate_segments(segments, args.lang_src, log)
        try:
            with open(meta_json, "w", encoding="utf-8") as f:
                json.dump({
                    "video": video_path,
                    "model": args.model,
                    "lang_src": args.lang_src,
                    "segments": translated,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"  Ghi meta lỗi: {e}")

    # 3. SRT
    log.info(f"[3/5] Ghi SRT...")
    try:
        write_srt(srt_path, translated)
        log.info(f"  SRT: {srt_path}")
    except Exception as e:
        log.error(f"  SRT lỗi: {e}")
        if status_tracker and task_id:
            status_tracker.finish_task(task_id, False, f"SRT lỗi: {e}")
        return None

    # 4. TTS
    log.info(f"[4/5] TTS ({args.tts})...")
    if status_tracker and task_id:
        status_tracker.update_task(task_id, progress=60, message=f"TTS ({args.tts})")
    if args.no_resume or not os.path.exists(tts_path):
        try:
            synthesize_segments(translated, tts_path, args, log)
        except Exception as e:
            log.error(f"  TTS lỗi: {e}\n{traceback.format_exc()}")
            if status_tracker and task_id:
                status_tracker.finish_task(task_id, False, f"TTS lỗi: {e}")
            return None
    else:
        log.info(f"  Dùng cache TTS: {tts_path}")

    # 5. Merge
    log.info(f"[5/5] ffmpeg merge...")
    if status_tracker and task_id:
        status_tracker.update_task(task_id, progress=85, message="ffmpeg merge")
    ok = merge_video(video_path, tts_path, srt_path, output_path, ffmpeg, args, log)
    if not ok:
        if status_tracker and task_id:
            status_tracker.finish_task(task_id, False, "ffmpeg merge thất bại")
        return None

    if status_tracker and task_id:
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        status_tracker.finish_task(
            task_id, True, f"Xong ({size_mb:.1f}MB)",
            output_data={
                "output": output_path,
                "srt": srt_path,
                "meta": meta_json,
                "tts_engine": args.tts,
                "model": args.model,
            },
        )
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    # Resolve paths
    video_dir = args.input or (
        config and getattr(config, "BASE_VIDEO_DIR", None)
        and str(Path(config.BASE_VIDEO_DIR).parent / "review_phim")
    ) or r"D:\Contenfactory\downloads\review_phim"
    output_dir = args.output or r"D:\Contenfactory\downloads\review_phim_viet"
    log_dir = Path((config and getattr(config, "LOG_DIR", None)) or _ROOT / "logs")
    os.makedirs(output_dir, exist_ok=True)

    log = setup_logging(log_dir)
    log.info("=== DICH LONG TIENG V2 ===")
    log.info(f"Input: {video_dir}")
    log.info(f"Output: {output_dir}")
    log.info(f"Args: model={args.model} tts={args.tts} limit={args.limit} "
             f"keep_orig={args.keep_original_audio}")

    # Eager-import core deps (cài nếu thiếu)
    import_or_install("torch")
    import_or_install("whisper", "openai-whisper")
    import_or_install("pydub")
    import_or_install("gtts", "gTTS")
    import_or_install("deep_translator", "deep-translator")

    # Tìm video
    videos = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))
    log.info(f"Tìm thấy {len(videos)} video .mp4 trong {video_dir}")
    if not videos:
        log.error("Không có video nào!")
        return 1

    if args.start_from:
        videos = videos[args.start_from:]
    if args.limit and args.limit > 0:
        videos = videos[:args.limit]
    log.info(f"Sẽ xử lý {len(videos)} video")

    ffmpeg = find_ffmpeg(log)
    log.info(f"ffmpeg: {ffmpeg}")

    results = []
    for i, video in enumerate(videos, 1):
        log.info(f"\n[Video {i}/{len(videos)}]")
        task_id = None
        if status_tracker:
            try:
                task_id = status_tracker.make_task_id("dich")
                status_tracker.create_task(
                    task_id, "dich_video", os.path.basename(video),
                    {"video": video, "model": args.model, "tts": args.tts},
                )
            except Exception as e:
                log.warning(f"  status_tracker lỗi: {e}")
                task_id = None

        try:
            out = process_video(video, output_dir, ffmpeg, args, log, task_id)
            results.append({"input": video, "output": out, "ok": out is not None})
        except Exception as e:
            log.error(f"LỖI nghiêm trọng: {e}\n{traceback.format_exc()}")
            if status_tracker and task_id:
                try:
                    status_tracker.finish_task(task_id, False, str(e))
                except Exception:
                    pass
            results.append({"input": video, "output": None, "ok": False})

    log.info(f"\n=== KẾT QUẢ ===")
    ok = sum(1 for r in results if r["ok"])
    log.info(f"Thành công: {ok}/{len(results)}")
    for r in results:
        status = "OK  " if r["ok"] else "FAIL"
        log.info(f"[{status}] {os.path.basename(r['input'])[:50]}")
        if r["ok"]:
            log.info(f"        -> {r['output']}")

    return 0 if ok == len(results) else (2 if ok > 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
