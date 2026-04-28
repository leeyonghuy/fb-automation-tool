# OpenClaw MCP — Crawl Douyin / Xiaohongshu → Google Sheet

MCP HTTP server (Node) cho **OpenClaw gateway** đang chạy trong Docker (WSL2).

Expose 2 tool:

- `crawl_url(url, topic?, note?)` — crawl 1 link, append 1 dòng vào Google Sheet.
- `crawl_urls(urls, topic?)` — batch nhiều link.

Hỗ trợ:
- Douyin: `douyin.com`, `v.douyin.com`, `iesdouyin.com`
- Xiaohongshu: `xiaohongshu.com`, `xhslink.com`

---

## 1. Chuẩn bị Google Sheet

1. Tạo (hoặc dùng sẵn) Google Spreadsheet, copy `SPREADSHEET_ID` từ URL
   (đoạn giữa `/d/` và `/edit`).
2. Mày đã có service-account JSON ở
   `D:\Contenfactory\API\nha-may-content-208dc5165e29.json`.
3. **Share spreadsheet** với email service-account (field `client_email`),
   quyền **Editor**.

Tool sẽ tự tạo sheet `Crawled` với header:

```
Created At | Platform | URL | Video ID | Title | Author | Topic | Type | Description | Note
```

---

## 2. Cấu hình `.env`

```bash
cd d:\Contenfactory\agents\openclaw-mcp
copy .env.example .env
```

Sửa `.env` (dùng path POSIX cho WSL2 mount):

```
SPREADSHEET_ID=1AbC...xyz
SHEET_NAME=Crawled
DEFAULT_TOPIC=
DEDUPLICATE=true
SERVICE_ACCOUNT_FILE=/mnt/d/Contenfactory/API/nha-may-content-208dc5165e29.json
```

---

## 3. Build & Run

Container `crawler-mcp` sẽ join vào network `scratch_ai_network`
(network mà `openclaw-gateway`, `n8n`, `9router` đang chạy).

```powershell
wsl -d Ubuntu  # hoặc WSL distro mặc định
cd /mnt/d/Contenfactory/agents/openclaw-mcp
docker compose --env-file .env up -d --build
```

Kiểm tra:

```powershell
wsl -e docker logs -f crawler-mcp
wsl -e docker exec openclaw-gateway sh -c "wget -qO- http://crawler-mcp:7799/healthz"
# → {"ok":true}
```

---

## 4. Đăng ký MCP server với OpenClaw

Một dòng duy nhất (chạy trên host):

```powershell
wsl -e docker exec openclaw-gateway node openclaw.mjs mcp set crawler "{\"url\":\"http://crawler-mcp:7799/mcp\",\"transport\":\"streamable-http\"}"
```

Kiểm tra:

```powershell
wsl -e docker exec openclaw-gateway node openclaw.mjs mcp list
wsl -e docker exec openclaw-gateway node openclaw.mjs mcp show crawler
```

> Lệnh `mcp set` chỉ ghi vào config OpenClaw, **không** test kết nối.
> Để OpenClaw thực sự load MCP server này, mày cần restart gateway (hoặc
> agent runtime sẽ tự pick up tuỳ phiên bản):
>
> ```powershell
> wsl -e docker restart openclaw-gateway
> ```

---

## 5. Tạo agent dùng tool

Trong OpenClaw, mở dashboard hoặc dùng CLI để tạo agent. System prompt gợi ý:

```
Mày là agent thu thập video Douyin / Xiaohongshu cho Content Factory.

Khi user gửi 1 hay nhiều link Douyin (douyin.com, v.douyin.com) hoặc
Xiaohongshu (xiaohongshu.com, xhslink.com):

1. Trích xuất tất cả URL từ tin nhắn.
2. Nếu có 1 URL  → gọi tool `crawl_url(url, topic, note)`.
   Nếu có nhiều → gọi tool `crawl_urls(urls, topic)`.
3. Nếu user nói rõ topic (vd "lưu topic review_phim"), truyền vào.
4. Trả lời ngắn gọn: số OK / SKIP / FAIL kèm tên video. Không bịa metadata.
5. Nếu tool trả ERROR, nói nguyên văn lại cho user.
```

Mở dashboard:

```powershell
wsl -e docker exec openclaw-gateway node openclaw.mjs dashboard
```

Hoặc gửi message trực tiếp qua channel đã pair (Telegram, Discord, …).

---

## 6. Schema sheet `Crawled`

| Cột | Ý nghĩa |
|---|---|
| Created At | Thời điểm crawl (server time) |
| Platform | `douyin` / `xiaohongshu` |
| URL | Link đã resolve |
| Video ID | `aweme_id` (Douyin) / `note_id` (XHS) |
| Title | Tiêu đề (hoặc desc đầu) |
| Author | Tên kênh / tác giả |
| Topic | Truyền từ LLM |
| Type | `video` / `image` / `unknown` |
| Description | Description đầy đủ (cắt 1000 ký tự) |
| Note | Ghi chú do LLM truyền |

---

## 7. Troubleshooting

**`network scratch_ai_network not found`**
Compose chính (chứa openclaw) chưa lên. Chạy `docker compose -p scratch up -d`
ở `C:\Users\Admin\.gemini\antigravity\scratch\` trước.

**`ENOENT: /secrets/service-account.json`**
Sai `SERVICE_ACCOUNT_FILE` trong `.env`. Path phải là **POSIX** từ góc nhìn
WSL2 (vd `/mnt/d/...`), không phải `D:\...`.

**`ERROR Sheets: 403 ... does not have access`**
Chưa share spreadsheet cho `client_email` của service account.

**`no __INITIAL_STATE__ (anti-bot?)`**
XHS chặn IP container. Cần thêm cookie XHS vào request (chưa hỗ trợ trong
phiên bản này — báo tao nếu cần).

**OpenClaw không thấy tool**
- `docker exec openclaw-gateway node openclaw.mjs mcp show crawler` để chắc
  config đã ghi.
- Restart gateway: `docker restart openclaw-gateway`.
- Xem log: `docker logs --tail 100 openclaw-gateway | grep -i mcp`.

---

## 8. Phát triển local (không docker)

```powershell
cd d:\Contenfactory\agents\openclaw-mcp
npm install
$env:SPREADSHEET_ID="..."
$env:GOOGLE_SERVICE_ACCOUNT_JSON_FILE="D:\Contenfactory\API\nha-may-content-208dc5165e29.json"
npm start
# → server tại http://localhost:7799/mcp
```

Test bằng curl:

```bash
curl http://localhost:7799/healthz
```

(Để OpenClaw container access local server không qua compose, thêm
`extra_hosts: ["host.docker.internal:host-gateway"]` cho service `openclaw`,
rồi `mcp set` URL `http://host.docker.internal:7799/mcp`.)
