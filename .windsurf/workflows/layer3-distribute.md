---
description: Layer 3 Distribution — Facebook automation, TikTok phonefarm, đăng bài đa nền tảng
---

# Layer 3: Distribution (Publishing & Automation)

## Nhiệm vụ
- Đăng video đã xử lý lên Facebook Fanpage (10-100 page)
- Đăng video lên TikTok qua phonefarm (boxphone + ADB)
- Quản lý tài khoản, profile, proxy
- Rate limiting, tránh ban
- Tracking trạng thái đăng bài

## Nhánh Facebook (Desktop-based)

### Files: `content/nuoiaccfb/`
| File | Vai trò |
|------|---------|
| `app.py` | Web UI chính (Flask, 40KB) |
| `account_manager.py` | Quản lý FB accounts |
| `fb_login.py` | Facebook login automation |
| `fb_interact.py` | Tương tác (like, comment, share) |
| `fb_warmup.py` | Nuôi acc (warm-up trước khi đăng) |
| `fb_post.py` | Đăng bài profile |
| `fb_page.py` | Quản lý fanpage |
| `fb_page_post.py` | Đăng bài lên fanpage |
| `fb_page_editor.py` | Chỉnh sửa fanpage |
| `ix_browser.py` | iXBrowser antidetect integration |
| `create_profiles.py` | Tạo browser profiles |
| `proxy_manager.py` | Quản lý proxy cho FB |
| `scheduler.py` | Lập lịch đăng bài |
| `accounts.json` | Data tài khoản |
| `proxies.txt` | Danh sách proxy |
| `profiles_created.json` | Profiles đã tạo |

### Docs
| File | Vai trò |
|------|---------|
| `README.md` | Hướng dẫn setup |
| `HUONG_DAN_NHAN_VIEN.md` | SOP cho nhân viên |
| `SOP_DaoTao_NhanVien.md` | Tài liệu đào tạo |

## Nhánh TikTok (Hardware-based)

### Files: `content/boxphone/`
| File | Vai trò |
|------|---------|
| `app.py` | Web UI chính (Flask, 40KB) |
| `adb_manager.py` | ADB connection manager |
| `device_manager.py` | Quản lý thiết bị |
| `device_controller.py` | Điều khiển thiết bị |
| `app_manager.py` | Quản lý app trên device |
| `content_manager.py` | Quản lý nội dung upload |
| `tiktok_login.py` | TikTok login automation |
| `tiktok_post.py` | Đăng video TikTok |
| `tiktok_warmup.py` | Nuôi acc TikTok |
| `proxy_manager.py` | Proxy cho phonefarm |
| `scheduler.py` | Lập lịch |
| `devices.json` | Data thiết bị |

## Publishing flow
```
Sheet [Publish Queue] status=queued
  → scheduler.py chọn acc + video + proxy
  → FB: ix_browser → fb_login → fb_page_post
  → TikTok: adb_manager → tiktok_login → tiktok_post
  → Update Sheet [Publish Queue] status=published
  → Update Sheet [Accounts] last_used, daily_posts
```

## TODO
- [ ] Kết nối scheduler với Sheet [Publish Queue]
- [ ] IP isolation: 1 acc = 1 proxy cố định
- [ ] Rate limit: max posts/ngày per acc
- [ ] Dedup: không đăng cùng video hash lên cùng acc
- [ ] Error handling + retry logic
- [ ] Dashboard tracking hiệu suất đăng bài
