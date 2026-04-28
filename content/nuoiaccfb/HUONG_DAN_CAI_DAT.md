# 📘 Hướng Dẫn Cài Đặt — Facebook Automation Tool (Layer 3)

> Dành cho nhân viên cài đặt trên máy mới

---

## ✅ Yêu cầu phần mềm

| Phần mềm | Phiên bản | Link tải |
|----------|-----------|----------|
| Python | 3.10 trở lên | https://python.org/downloads |
| Git | Mới nhất | https://git-scm.com |
| IX Browser | Mới nhất | (nhận từ quản lý) |

---

## 🚀 Cài đặt từng bước

### Bước 1: Cài Python

1. Tải Python tại: https://python.org/downloads
2. Khi cài, **tick vào ô "Add Python to PATH"** (quan trọng!)
3. Nhấn Install Now
4. Kiểm tra: mở CMD → gõ `python --version` → phải hiện `Python 3.10.x` trở lên

---

### Bước 2: Cài Git

1. Tải Git tại: https://git-scm.com
2. Cài với tùy chọn mặc định (Next → Next → Install)
3. Kiểm tra: mở CMD → gõ `git --version`

---

### Bước 3: Tải code từ GitHub

Mở **Command Prompt** (CMD), gõ lần lượt:

```bash
cd C:\
git clone https://github.com/leeyonghuy/fb-automation-tool.git
cd fb-automation-tool\content\nuoiaccfb
```

---

### Bước 4: Cài thư viện Python (chạy 1 lần)

```bash
pip install -r requirements.txt
playwright install chromium
```

> ⏳ Bước này mất 3-5 phút, chờ cho đến khi xong

---

### Bước 5: Cài và chạy IX Browser

1. Nhận file cài IX Browser từ quản lý
2. Cài đặt bình thường
3. **Mở IX Browser trước** khi chạy tool
4. Đảm bảo IX Browser đang chạy ở cổng **53200** (mặc định)

---

### Bước 6: Chạy Web UI

```bash
cd C:\fb-automation-tool\content\nuoiaccfb
python app.py
```

Sau đó mở trình duyệt (Chrome/Edge) và vào:
```
http://localhost:5000
```

---

## ⚙️ Cấu hình ban đầu

### Thêm tài khoản Facebook

1. Vào Web UI → tab **Accounts**
2. Nhấn **Add Account**
3. Điền: Email, Password, Tên hiển thị
4. Nhấn Save

### Thêm Proxy

1. Vào Web UI → tab **Proxies**
2. Dán danh sách proxy (mỗi dòng 1 proxy)
3. Format: `host:port:user:password`
4. Nhấn Save

### Tạo IX Browser Profile

1. Vào Web UI → tab **Profiles**
2. Nhấn **Auto Assign** để tự động gán profile cho account

---

## 🔄 Cập nhật code mới (khi quản lý thông báo)

```bash
cd C:\fb-automation-tool
git pull origin main
```

---

## ❓ Lỗi thường gặp

### Lỗi: `python không được nhận dạng`
→ Cài lại Python, nhớ tick **"Add to PATH"**

### Lỗi: `playwright install chromium` thất bại
→ Chạy CMD với quyền **Administrator**

### Lỗi: `Connection refused` khi mở Web UI
→ Kiểm tra `python app.py` đang chạy chưa

### Lỗi: IX Browser không kết nối được
→ Mở IX Browser trước, kiểm tra đang chạy ở port 53200

---

## 📞 Liên hệ hỗ trợ

Gặp vấn đề → liên hệ quản lý qua Zalo/Telegram

---

*Cập nhật lần cuối: 2026-04*
