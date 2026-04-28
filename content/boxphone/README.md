# 📱 BoxPhone TikTok Manager

Module điều khiển BoxPhone qua ADB để tự động hóa TikTok: đăng nhập, upload video, gắn giỏ hàng TikTok Shop.

> **Tách biệt hoàn toàn** với module nuôi acc FB. Chạy tại `http://localhost:5001`

---

## 🗂️ Cấu Trúc

```
content/boxphone/
├── adb_manager.py       # Quản lý kết nối ADB, detect thiết bị, scrcpy
├── device_controller.py # Tap, swipe, input text, screenshot (uiautomator2)
├── tiktok_login.py      # Auto login TikTok bằng email/password
├── tiktok_post.py       # Upload video + gắn sản phẩm TikTok Shop
├── device_manager.py    # Quản lý danh sách thiết bị + tài khoản (JSON)
├── app.py               # Web UI Flask tại localhost:5001
├── templates/
│   └── boxphone_index.html
├── devices.json         # Dữ liệu thiết bị + tài khoản (tự tạo khi chạy)
└── requirements.txt
```

---

## ⚙️ Yêu Cầu Cài Đặt

### 1. Python packages
```bash
cd content/boxphone
pip install -r requirements.txt
```

### 2. ADB (Android Debug Bridge)
- Tải: https://developer.android.com/tools/releases/platform-tools
- Giải nén vào `C:\platform-tools`
- Thêm vào PATH: `C:\platform-tools`
- Kiểm tra: `adb version`

### 3. scrcpy (Mirror màn hình)
- Tải: https://github.com/Genymobile/scrcpy/releases
- Giải nén vào `C:\scrcpy`
- Thêm vào PATH: `C:\scrcpy`
- Kiểm tra: `scrcpy --version`

### 4. Bật USB Debugging trên BoxPhone
- Vào **Cài đặt → Giới thiệu về điện thoại**
- Tap **Số bản dựng** 7 lần để bật Developer Options
- Vào **Cài đặt → Tùy chọn nhà phát triển**
- Bật **USB Debugging**
- Cắm USB vào máy tính → Chấp nhận popup "Allow USB Debugging"

---

## 🚀 Chạy Tool

```bash
cd d:\Contenfactory\content\boxphone
python app.py
```

Mở trình duyệt: **http://localhost:5001**

---

## 📋 Hướng Dẫn Sử Dụng

### Bước 1: Kết nối thiết bị
1. Cắm tất cả BoxPhone vào USB Hub
2. Vào tab **📱 Thiết Bị** → nhấn **Sync ADB**
3. Danh sách thiết bị hiện ra với trạng thái `online`

### Bước 2: Thêm tài khoản TikTok
- Vào tab **👤 Tài Khoản** → nhập email + password
- Hoặc **Import CSV** với format:
  ```
  serial,email,password,note
  ABC123,user@gmail.com,pass123,shop A
  ```

### Bước 3: Ghép cặp thiết bị ↔ tài khoản
- Khi thêm tài khoản, điền Serial của thiết bị vào ô "Serial thiết bị"
- Hoặc dùng API: `POST /api/devices/{serial}/assign`

### Bước 4: Đăng nhập TikTok
- Vào tab **🔐 Đăng Nhập**
- Nhấn **"Đăng nhập tất cả"** để login hàng loạt
- Hoặc đăng nhập từng máy một

### Bước 5: Upload Video
- Vào tab **📹 Upload Video**
- Chọn thiết bị, nhập đường dẫn video trên máy tính
- Nhập caption, hashtag, tên sản phẩm TikTok Shop
- Nhấn **Upload Video**

### Bước 6: Mirror màn hình
- Nhấn **🖥️ Mirror Tất Cả** để xem tất cả màn hình
- Hoặc nhấn icon 🖥️ ở từng thiết bị

---

## 🔧 API Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/api/devices` | Danh sách thiết bị |
| POST | `/api/devices/sync` | Sync từ ADB |
| POST | `/api/devices/{serial}/mirror` | Mở scrcpy |
| POST | `/api/devices/mirror_all` | Mở scrcpy tất cả |
| GET | `/api/accounts` | Danh sách tài khoản |
| POST | `/api/accounts` | Thêm tài khoản |
| POST | `/api/login` | Đăng nhập 1 thiết bị |
| POST | `/api/login/batch` | Đăng nhập hàng loạt |
| POST | `/api/upload` | Upload video 1 thiết bị |
| POST | `/api/upload/batch` | Upload hàng loạt |
| GET | `/api/tasks/{id}` | Trạng thái task |

---

## ⚠️ Lưu Ý

- **USB Hub có nguồn riêng** (powered hub) khi cắm 10+ điện thoại
- Mỗi thiết bị cần **chấp nhận USB Debugging** lần đầu
- TikTok có thể yêu cầu **captcha** khi đăng nhập → cần xử lý thủ công
- Không chạy quá nhiều thiết bị cùng lúc nếu máy tính RAM thấp
- RAM ước tính: ~200MB/thiết bị khi chạy scrcpy + uiautomator2

---

## 📊 Yêu Cầu Phần Cứng

| Số thiết bị | RAM tối thiểu | CPU |
|-------------|---------------|-----|
| 1-5 máy | 8 GB | i5 |
| 5-10 máy | 16 GB | i7 |
| 10+ máy | 32 GB | i9/Ryzen 9 |
