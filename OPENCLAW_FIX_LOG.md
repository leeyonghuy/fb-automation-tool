# OpenClaw Gateway Fix Log
**Cập nhật:** 2026-04-27 18:15  
**Trạng thái:** Deps đã cài đầy đủ — cần restart AG IDE

---

## Root Cause (đã xác định)

Antigravity IDE chạy `openclaw` gateway **native trong WSL** (process user `leeyonghuy`, bind port 18789).  
Compose file có thêm Docker `openclaw` service → hai gateway conflict nhau:
- Docker gateway dùng `--force` kill listener của AG
- AG restart gateway của nó
- Docker gateway thấy port bị chiếm → restart loop

**AG IDE luôn kill bất kỳ process nào bind port 18789 và spawn native gateway của nó.**  
**Không thể chạy Docker gateway khi AG IDE đang mở.**

---

## Fix đã áp dụng (2026-04-27)

### 1. Cài đầy đủ bundled plugin runtime deps
Vào volume `openclaw_config`, folder `plugin-runtime-deps/openclaw-2026.4.24-f53b52ad6d21/`:

**Đã cài (dùng openclaw image node v24, user root):**
- Batch 1-3: express, ws, axios, openai, anthropic, google-generativeai, telegram, etc.
- Batch 4: `acpx@0.5.3`, `commander@^14.0.3`, `@clack/prompts@^1.2.0`, `@homebridge/ciao@^1.3.6`, `mpg123-decoder@^1.0.3`, `silk-wasm@^3.7.1`, `@tencent-connect/qqbot-connector@^1.1.0`
- Batch 5: `@aws-sdk/client-bedrock@3.1034.0`, `@aws-sdk/client-bedrock-runtime@3.1034.0`, `@aws-sdk/credential-provider-node@3.972.34`
- Batch 6: `@aws/bedrock-token-generator@^1.1.0`

### 2. Fix permissions
```bash
docker run --rm -v openclaw_config:/home/node/.openclaw --user root ghcr.io/openclaw/openclaw:latest \
  sh -c 'chown -R node:node /home/node/.openclaw/plugin-runtime-deps'
```

### 3. Xóa lock file bị kẹt
```bash
docker run --rm -v openclaw_config:/data --user root alpine \
  sh -c 'rm -rf /data/plugin-runtime-deps/openclaw-2026.4.24-f53b52ad6d21/.openclaw-runtime-deps.lock'
```

---

## Trạng thái hiện tại

- ✅ Tất cả deps đã cài trong volume `openclaw_config`
- ✅ Permissions đã fix (node:node)
- ✅ Lock file đã xóa
- ⚠️ AG IDE đang kill Docker gateway → cần **restart AG IDE** để spawn native gateway

---

## Hành động cần làm

**Restart AG IDE** → AG sẽ tự spawn openclaw gateway native trong WSL → gateway sẽ tìm thấy đủ deps → hoạt động bình thường.

Verify sau khi restart:
```bash
wsl -- ps aux | grep openclaw
wsl -- ss -tlnp | grep 18789
```

Test Telegram: nhắn tin vào bot để kiểm tra phản hồi.

---

## Config openclaw.json (đã đúng)
- **Gateway:** mode=local, port=18789, bind=lan, token auth
- **Telegram:** enabled, botToken đã set, dmPolicy=open, allowFrom=*
- **Agent:** main → model Trollllm/gpt-4o (9router)
- **MCP:** crawler-mcp tại http://crawler-mcp:7799/mcp
- **Binding:** agent main → telegram channel

---

## Lưu ý quan trọng

**KHÔNG thêm `openclaw` service vào docker-compose.yml** — AG tự quản lý gateway.  
**KHÔNG chạy Docker gateway khi AG IDE đang mở** — sẽ bị kill ngay.

Nếu cần chạy gateway thủ công (khi AG không chạy):
```bash
wsl -- openclaw gateway run --allow-unconfigured --bind lan
```
