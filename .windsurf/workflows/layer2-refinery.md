---
description: Layer 2 Refinery — Download video, edit/băm, dịch, lồng tiếng, n8n workflow
---

# Layer 2: The Refinery (Ingestion & Video Processing)

## Nhiệm vụ
- Download video gốc (no watermark) từ Douyin/TikTok/XHS
- Edit/băm video (FFmpeg): lật, cắt, đổi tốc độ, filter, đổi MD5
- AI-enhanced: viết lại caption, đổi voice, chèn sub
- Dịch + lồng tiếng (TTS)
- n8n điều phối pipeline tự động

## Files chính

### Download & Crawl (Python)
| File | Vai trò |
|------|---------|
| `crawler/video_downloader.py` | Download video từ Douyin/TikTok (16KB, đầy đủ) |
| `crawler/douyin_download.py` | Douyin download helper |
| `crawler/douyin_direct.py` | Extract video URL từ HTML |
| `crawler/douyin_playwright.py` | Douyin via Playwright |
| `crawler/xiaohongshu.py` | XHS download (HTTP + Playwright fallback) |
| `crawler/tiktok_dl.py` | TikTok download |
| `crawler/tiktok_playwright.py` | TikTok via Playwright |
| `crawler/sheets_manager.py` | Google Sheets read/write (Channels + Videos tabs) |
| `crawler/orchestrator.py` | Pipeline orchestrator |
| `crawler/run_pipeline.py` | CLI entry point cho pipeline |

### Video Editing (Python)
| File | Vai trò |
|------|---------|
| `crawler/video_editor.py` | FFmpeg editing: flip, speed, filter, crop, MD5 change (27KB) |

### Dịch & Lồng tiếng
| File | Vai trò |
|------|---------|
| `DICH_V2.py` | Dịch video chính (27KB, phiên bản mới) |
| `DICH_LONG_TIENG.py` | Lồng tiếng video (10KB) |
| `crawler/douyin_translate_tts.py` | Douyin translate + TTS pipeline |
| `crawler/tts_engine.py` | TTS engine wrapper |
| `libs/vieneu-tts/` | Thư viện TTS tự host |

### Whisper (Speech-to-text)
| File | Vai trò |
|------|---------|
| `test_whisper.py` | Test Whisper GPU |
| `CHAY_WHISPER_GPU.bat` | Chạy Whisper trên GPU |

### n8n Workflow
| File | Vai trò |
|------|---------|
| `n8n/workflow_content_factory.json` | Workflow n8n (cần import vào n8n) |

### Shared
| File | Vai trò |
|------|---------|
| `common/json_store.py` | JSON file storage helper |
| `common/logging_config.py` | Logging config |
| `common/secret_store.py` | Secret management |
| `status_tracker.py` | Tracking trạng thái video pipeline |
| `status.db` | SQLite DB cho status tracking |

## Pipeline flow
```
Sheet [Raw Videos] status=approved
  → n8n trigger
  → video_downloader.py (download)
  → video_editor.py (băm/edit)
  → DICH_V2.py / tts_engine.py (dịch + lồng tiếng, nếu cần)
  → Output → Sheet [Processed Videos] status=done
```

## TODO
- [ ] Kết nối n8n workflow với Sheet schema mới
- [ ] Tự động trigger download khi Raw Video status = approved
- [ ] FFmpeg băm pipeline: tạo nhiều variants từ 1 video
- [ ] AI-enhanced editing (Gemini/Runway API)
- [ ] Lưu Processed Videos metadata vào Sheet
