---
description: Layer 4 Infrastructure — Docker, proxy, network, config, monitoring
---

# Layer 4: Infrastructure (Network & Hardware)

## Nhiệm vụ
- Docker compose cho tất cả services
- Proxy / IP isolation cho mỗi tài khoản
- Config tập trung
- Monitoring & dashboard

## Docker Containers (WSL2)

| Container | Image | Port | Network | Vai trò |
|-----------|-------|------|---------|---------|
| `openclaw-gateway` | openclaw | 18789 | scratch_ai_network | AI Gateway |
| `crawler-mcp` | contenfactory/crawler-mcp | 7799 | scratch_ai_network | MCP server (Layer 1) |
| `n8n` | n8n | 5678 | scratch_ai_network | Workflow automation |
| `9router` | 9router | — | scratch_ai_network | Proxy/routing |

## Files chính

### Config
| File | Vai trò |
|------|---------|
| `config.py` | Config tập trung: paths, API keys, Sheet ID, AI providers |
| `.env` | Environment variables (root) |
| `.env.example` | Template |
| `agents/openclaw-mcp/.env` | Config cho MCP container |
| `agents/openclaw-mcp/docker-compose.yml` | Docker compose cho crawler-mcp |

### Network & Proxy
| File | Vai trò |
|------|---------|
| `content/nuoiaccfb/proxies.txt` | Proxy list cho FB |
| `content/nuoiaccfb/proxy_manager.py` | Proxy manager FB |
| `content/boxphone/proxy_manager.py` | Proxy manager TikTok |

### Auth & Secrets
| File | Vai trò |
|------|---------|
| `API/nha-may-content-208dc5165e29.json` | Google service account |
| `cookies/douyin_cookies.json` | Douyin cookies (hết hạn ~25/06/2026) |
| `common/secret_store.py` | Secret management |
| `EXPORT_COOKIES_ADMIN.bat` | Script export cookies |

### Monitoring
| File | Vai trò |
|------|---------|
| `dashboard/app.py` | Dashboard web app |
| `dashboard/templates/dashboard.html` | Dashboard UI |
| `START_DASHBOARD.bat` | Khởi động dashboard |
| `status_tracker.py` | Status tracking |
| `status.db` | SQLite status DB |

### n8n
| File | Vai trò |
|------|---------|
| `n8n/workflow_content_factory.json` | Exported workflow |

## Network topology
```
Internet
  │
  ├── 9router (proxy pool)
  │     ├── IP-1 → FB acc 1
  │     ├── IP-2 → FB acc 2
  │     ├── IP-3 → TikTok device 1
  │     └── ...
  │
  └── scratch_ai_network (Docker internal)
        ├── openclaw-gateway
        ├── crawler-mcp
        ├── n8n
        └── 9router
```

## TODO
- [ ] Dashboard tổng hợp tất cả layers
- [ ] Health check tự động cho tất cả containers
- [ ] Alert khi cookies sắp hết hạn
- [ ] Backup config + data tự động
- [ ] Log aggregation
