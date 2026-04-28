---
description: Layer 1 Brain — OpenClaw, MCP crawler, search Douyin/XHS, ghi Google Sheet
---

# Layer 1: The Brain (Discovery & Orchestration)

## Nhiệm vụ
- Search video theo keyword trên Douyin (có cookies)
- Crawl metadata từ URL Douyin/Xiaohongshu
- Ghi metadata vào Google Sheet (tab `Crawled` hiện tại, sẽ chuyển sang `Raw Videos`)
- (Planned) AI đánh giá viral score

## Files chính

### MCP Server (Node.js)
| File | Vai trò |
|------|---------|
| `agents/openclaw-mcp/server.js` | MCP server — tool `crawl_and_save` |
| `agents/openclaw-mcp/package.json` | Dependencies |
| `agents/openclaw-mcp/Dockerfile` | Docker image |
| `agents/openclaw-mcp/docker-compose.yml` | Container config, network, volumes |
| `agents/openclaw-mcp/.env` | Runtime config (SPREADSHEET_ID, cookies path) |

### Config & Auth
| File | Vai trò |
|------|---------|
| `config.py` | Config tập trung (paths, API keys, sheet ID) |
| `API/nha-may-content-208dc5165e29.json` | Google service account |
| `cookies/douyin_cookies.json` | Douyin session cookies (hết hạn ~25/06/2026) |
| `setup_ggsheet.py` | Script tạo spreadsheet + set headers |

## Tool 1: crawl_and_save
- **Input keyword**: search Douyin → lấy metadata → ghi Sheet (status=new)
- **Input urls**: crawl URL Douyin/XHS → lấy metadata → ghi Sheet (status=new)
- Params: `keyword`, `count`, `urls`, `topic`, `note`
- Deduplication: check URL đã tồn tại trong Sheet

## Tool 2: sheet_manage
- **action=read**: đọc danh sách video, lọc theo status/platform/topic
- **action=update**: cập nhật Status, Topic, Note, AI_Score cho 1 hoặc nhiều dòng
- Dùng để agent đánh giá viral (ghi AI_Score), duyệt video (status: new→approved), v.v.

## Sheet columns
Created At, Platform, URL, Video ID, Title, Author, Topic, Type, Description, Note, **Status**, **AI_Score**

## Status flow
`new` → `approved` → `downloaded` → `processing` → `ready` → `done`

## Docker
- Container: `crawler-mcp` trên `scratch_ai_network`
- Port: 7799 (internal)
- MCP endpoint: `http://crawler-mcp:7799/mcp`
- Registered in OpenClaw: ✅

## TODO
- [ ] Test search Douyin qua OpenClaw agent
- [ ] Test sheet_manage (read/update) qua OpenClaw agent
- [ ] Thêm YouTube / TikTok search
- [ ] Tạo agent system prompt để tự đánh giá viral score
- [x] ~~Tool đọc/update status trên Sheet~~ → sheet_manage
- [x] ~~Thêm cột Status + AI_Score~~ → đã thêm
