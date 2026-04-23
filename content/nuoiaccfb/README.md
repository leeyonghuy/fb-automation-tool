# 🐣 NuôiAccFB — Module Nuôi Tài Khoản & Fanpage Facebook

Module tích hợp **IX Browser** + **Playwright** để tự động hóa việc nuôi tài khoản Facebook/Fanpage số lượng lớn.

---

## 📁 Cấu trúc

```
content/nuoiaccfb/
├── ix_browser.py       # Điều khiển IX Browser qua Local API + Playwright CDP
├── proxy_manager.py    # Quản lý danh sách proxy (thêm/cập nhật/kiểm tra)
├── account_manager.py  # Quản lý tài khoản FB/Fanpage (trạng thái, gán profile)
├── proxies.txt         # Danh sách proxy (ip:port:user:pass)
├── accounts.json       # DB tài khoản (tự sinh khi thêm acc)
└── README.md
```

---

## ⚙️ Yêu cầu

```bash
pip install requests playwright
playwright install chromium
```

- **IX Browser** cài đặt và đang chạy trên máy (download tại https://ixbrowser.com)
- IX Browser Local API mặc định: `http://127.0.0.1:53200`

---

## 🚀 Hướng dẫn sử dụng

### 1. Thêm proxy vào danh sách

Chỉnh file `proxies.txt`, mỗi dòng một proxy:
```
# Format: ip:port hoặc ip:port:username:password
1.2.3.4:1080:user1:pass1
5.6.7.8:3128
```

Hoặc dùng code:
```python
from proxy_manager import add_proxy, add_proxies_bulk

# Thêm 1 proxy
add_proxy("1.2.3.4", "1080", "user", "pass")

# Thêm nhiều proxy
add_proxies_bulk([
    "1.2.3.4:1080:user1:pass1",
    "5.6.7.8:3128",
])
```

### 2. Gán proxy vào profile IX Browser

```python
from ix_browser import assign_proxies_to_profiles, update_profile_proxy

# Tự động gán proxy cho tất cả profile chưa có proxy
assign_proxies_to_profiles(proxy_type="socks5")

# Cập nhật proxy cho 1 profile cụ thể
update_profile_proxy("profile_id_here", "1.2.3.4", "1080", "user", "pass")
```

### 3. Quản lý tài khoản

```python
from account_manager import add_account, set_status, get_active_accounts

# Thêm tài khoản
add_account(fb_uid="100001234", name="Nguyễn Văn A",
            profile_id="ix_profile_001", account_type="personal")

# Thêm fanpage
add_account(fb_uid="pg_456789", name="Fanpage Bán Hàng",
            account_type="fanpage")

# Cập nhật trạng thái
set_status("100001234", "warming")  # new | warming | active | checkpoint | die

# Lấy tài khoản đang active
actives = get_active_accounts()
```

### 4. Mở trình duyệt & thao tác tự động

```python
import asyncio
from ix_browser import run_task_on_profile

async def warm_up_task(page):
    """Ví dụ task warm-up: vào FB, scroll newsfeed, like 1-2 bài"""
    await page.goto("https://facebook.com")
    await page.wait_for_timeout(3000)
    await page.mouse.wheel(0, 500)
    await page.wait_for_timeout(2000)
    print("Warm-up xong!")

asyncio.run(run_task_on_profile("your_profile_id", warm_up_task))
```

---

## 📊 So sánh SaaS thị trường

### Nhóm Antidetect Browser

| SaaS | Free Profiles | API | Giá trả phí | Phù hợp |
|---|---|---|---|---|
| **IX Browser** | ✅ 100 profiles | ✅ Local API | Thấp | ⭐ Đang dùng |
| **AdsPower** | ❌ 2 profiles | ✅ Local API + RPA | $10–50/tháng | Tốt cho non-dev |
| **Hidemyacc** | ❌ | ✅ | ~$15/tháng | Cộng đồng VN, hỗ trợ tốt |
| **GoLogin** | ❌ 3 profiles | ✅ Cloud API | $49–99/tháng | Enterprise |
| **Multilogin** | ❌ | ✅ | $99–199/tháng | Cao cấp nhất |
| **Dolphin Anty** | ✅ 10 profiles | ✅ | $89/tháng | Dev-friendly |

### Nhóm Auto Post / Social Management

| SaaS | Tính năng | Giá | Ghi chú |
|---|---|---|---|
| **n8n** (đang dùng) | Schedule, workflow | Free self-host | ✅ Tích hợp sẵn |
| **Publer** | Post FB Page/Group, schedule | $12/tháng | Nhiều trang cùng lúc |
| **Metricool** | Analytics + auto post | $18/tháng | Phù hợp fanpage |
| **Buffer** | Simple scheduler | $15/tháng | Hạn chế Group |
| **FBTool VN** | Nuôi acc, warm-up, kết bạn | Cộng đồng MMO VN | Nhiều tính năng thô |

### ✅ Khuyến nghị cho hệ thống này

```
IX Browser (100 profile free)
    ↓ Local API
ix_browser.py + Playwright (automation)
    ↓
n8n (scheduling, orchestration)     ← đã có sẵn
    ↓
account_manager.py + Google Sheets (tracking)
```

**Proxy:** Dùng residential proxy (BrightData, IPRoyal, Smartproxy) — tránh datacenter vì dễ bị Facebook detect.

---

## 🔒 Nguyên tắc nuôi tài khoản an toàn

1. **1 profile = 1 proxy** — không share IP giữa các tài khoản
2. **Warm-up 7–14 ngày** trước khi dùng để post/quảng cáo
3. **Hành vi tự nhiên:** Random delay 2–10s giữa các thao tác, scroll, di chuột
4. **Không làm quá nhiều** cùng lúc: mỗi ngày 1–2 action/tài khoản khi mới tạo
5. **Timezone & language** phải khớp với proxy location
6. **Backup cookie** thường xuyên
