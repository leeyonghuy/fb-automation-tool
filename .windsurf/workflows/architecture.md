---
description: Chỉ mục kiến trúc A.C.F — đọc file này đầu mỗi phiên để biết cần load gì
---

# AI Content Factory (A.C.F) — Architecture Index

## Cách dùng
- Đầu phiên mới, nói **"/architecture"** để xem tổng quan
- Nói **"/layer1-brain"** để làm việc với Layer 1 (search, crawl, OpenClaw)
- Nói **"/layer2-refinery"** để làm việc với Layer 2 (download, edit video, n8n)
- Nói **"/layer3-distribute"** để làm việc với Layer 3 (FB, TikTok, boxphone)
- Nói **"/layer4-infra"** để làm việc với Layer 4 (Docker, proxy, network)

## Luồng dữ liệu tổng

```
Layer 1: Brain (OpenClaw)          Layer 2: Refinery (n8n + scripts)
  Search keyword                     Download video
  → Crawl metadata                   → FFmpeg/AI edit
  → Ghi vào Sheet [Raw Videos]       → Tạo variants
  → AI đánh giá viral                → Ghi vào Sheet [Processed Videos]
        │                                   │
        └──────── Google Sheets ────────────┘
                       │
              Layer 3: Distribution
                FB (nuoiaccfb) ← Sheet [Publish Queue]
                TikTok (boxphone) ← Sheet [Publish Queue]
                       │
              Layer 4: Infrastructure
                Docker, 9router, proxy, IP isolation
```

## Layer Map

| Layer | Workflow file | Thư mục chính | Trạng thái |
|-------|--------------|---------------|------------|
| 1 — Brain | `/layer1-brain` | `agents/openclaw-mcp/`, `mcp-server/` | ✅ Search Douyin + crawl + ghi Sheet |
| 2 — Refinery | `/layer2-refinery` | `crawler/`, `DICH_*.py`, `libs/vieneu-tts/` | ⚠️ Scripts rời rạc, chưa nối n8n |
| 3 — Distribution | `/layer3-distribute` | `content/nuoiaccfb/`, `content/boxphone/` | ✅ FB + TikTok automation có sẵn |
| 4 — Infrastructure | `/layer4-infra` | `docker-compose`, `n8n/`, `config.py` | ✅ Docker + proxy đang chạy |

## Google Sheets Schema (planned)

| Sheet | Mục đích | Owner |
|-------|----------|-------|
| `Sources` | Kênh/nguồn theo dõi | Layer 1 ghi, n8n đọc |
| `Raw Videos` | Video thô phát hiện | Layer 1 ghi, Layer 2 đọc + update |
| `Processed Videos` | Video đã edit | Layer 2 ghi, Layer 3 đọc |
| `Publish Queue` | Hàng đợi đăng bài | Layer 2 tạo, Layer 3 update |
| `Accounts` | Quản lý tài khoản FB/TikTok | Layer 3 đọc + update |

## Tech Stack
- **AI Gateway**: OpenClaw (Docker, WSL2)
- **Workflow**: n8n (Docker)
- **MCP Server**: Node.js (`agents/openclaw-mcp/`)
- **Crawler/Processing**: Python 3.x (`crawler/`)
- **FB Automation**: Python + iXBrowser (`content/nuoiaccfb/`)
- **TikTok Automation**: Python + ADB (`content/boxphone/`)
- **TTS**: vieneu-tts (`libs/vieneu-tts/`)
- **Storage**: Google Sheets + local filesystem
- **Proxy**: 9router, PPPoE
- **Cookies**: `cookies/douyin_cookies.json` (hết hạn ~25/06/2026)
