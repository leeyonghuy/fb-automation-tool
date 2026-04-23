# 📘 SOP — Quy Trình Vận Hành Tool Nuôi Tài Khoản Facebook
**Phiên bản:** 1.0 | **Ngày:** 23/04/2026  
**Áp dụng cho:** Nhân viên vận hành hệ thống nuôi acc FB

---

## MỤC LỤC
1. [Yêu Cầu Máy Tính](#1-yêu-cầu-máy-tính)
2. [Cài Đặt Lần Đầu](#2-cài-đặt-lần-đầu)
3. [Khởi Động Tool Hàng Ngày](#3-khởi-động-tool-hàng-ngày)
4. [Hướng Dẫn Sử Dụng Web UI](#4-hướng-dẫn-sử-dụng-web-ui)
5. [Quy Trình Nuôi Tài Khoản Chuẩn](#5-quy-trình-nuôi-tài-khoản-chuẩn)
6. [Quản Lý Fanpage](#6-quản-lý-fanpage)
7. [Tối Ưu RAM Máy](#7-tối-ưu-ram-máy)
8. [Xử Lý Sự Cố](#8-xử-lý-sự-cố)
9. [Quy Tắc An Toàn Bắt Buộc](#9-quy-tắc-an-toàn-bắt-buộc)
10. [Checklist Cuối Ngày](#10-checklist-cuối-ngày)

---

## 1. Yêu Cầu Máy Tính

| Thành phần | Tối thiểu | Khuyến nghị |
|---|---|---|
| **RAM** | 8 GB | 16 GB trở lên |
| **CPU** | 4 core | 8 core |
| **Ổ cứng** | 50 GB trống | 100 GB SSD |
| **OS** | Windows 10 | Windows 10/11 64-bit |
| **Internet** | 20 Mbps | 50 Mbps+ ổn định |

### 🔴 Lưu ý RAM theo số tài khoản:
- **5–10 tài khoản/lần** → cần ít nhất **8 GB RAM**
- **10–20 tài khoản/lần** → cần ít nhất **16 GB RAM**
- **20–50 tài khoản/lần** → cần ít nhất **32 GB RAM**

> ⚠️ Mỗi profile IX Browser chiếm ~200 MB RAM. Máy yếu cần chia nhóm nhỏ và chạy **tuần tự**.

---

## 2. Cài Đặt Lần Đầu

> **Chỉ làm 1 lần duy nhất khi setup máy mới**

### Bước 1: Cài Python
1. Vào https://python.org/downloads → tải Python 3.10 trở lên
2. Khi cài: ✅ Tích chọn **"Add Python to PATH"**
3. Mở CMD, kiểm tra: `python --version`

### Bước 2: Cài IX Browser
1. Vào https://ixbrowser.com → Đăng ký tài khoản miễn phí
2. Tải và cài đặt IX Browser
3. Đăng nhập IX Browser → Kiểm tra có **100 profile miễn phí**
4. Để IX Browser **đang chạy** khi dùng tool

### Bước 3: Cài thư viện Python
Mở CMD, điều hướng đến thư mục tool:
```
cd d:\Contenfactory\content\nuoiaccfb
pip install -r requirements.txt
playwright install chromium
```

### Bước 4: Cài đặt Proxy
1. Mở file `proxies.txt` bằng Notepad
2. Nhập proxy theo định dạng:
   ```
   ip:port:username:password
   ```
   Ví dụ:
   ```
   1.2.3.4:1080:user1:pass1
   5.6.7.8:3128:user2:pass2
   ```
3. Mỗi dòng 1 proxy, **1 proxy cho 1 tài khoản FB**

### Bước 5: Tạo Profiles trong IX Browser
1. Mở CMD trong thư mục tool
2. Chạy: `python create_profiles.py`
3. Kiểm tra IX Browser → Profiles đã được tạo

---

## 3. Khởi Động Tool Hàng Ngày

### Thứ tự khởi động (QUAN TRỌNG — Phải đúng thứ tự):

```
Bước 1: Mở IX Browser → Đăng nhập tài khoản IX Browser
         (Chờ IX Browser load xong hoàn toàn)

Bước 2: Mở CMD → gõ lệnh:
         cd d:\Contenfactory\content\nuoiaccfb
         python app.py

Bước 3: Mở trình duyệt → vào địa chỉ:
         http://localhost:5000

Bước 4: Bắt đầu thao tác theo quy trình
```

> ⚠️ Nếu IX Browser chưa mở mà chạy tool → tool sẽ báo lỗi "Browser failed"

---

## 4. Hướng Dẫn Sử Dụng Web UI

Truy cập: **http://localhost:5000**

### 4.1 Tab Dashboard (Trang chủ)
- Xem tổng số tài khoản
- Xem trạng thái từng tài khoản (new / warming / active / checkpoint / die)
- Xem số profile IX Browser

### 4.2 Tab Accounts (Tài khoản)
**Thêm tài khoản mới:**
1. Click **"Import Accounts"**
2. Paste danh sách theo format: `email|password|uid`
3. Click **Import**

**Xem trạng thái tài khoản:**
- 🟡 `new` — Tài khoản mới chưa dùng
- 🔵 `warming` — Đang trong quá trình nuôi
- 🟢 `active` — Sẵn sàng sử dụng
- 🔴 `checkpoint` — Bị Facebook kiểm tra
- ⚫ `die` — Tài khoản đã chết

**Gán Profile:**
- Click **"Auto Assign"** để tự động gán profile IX Browser cho tài khoản

### 4.3 Tab Profiles
- Xem danh sách profile IX Browser
- Mở/đóng từng profile thủ công
- **Close All**: Đóng tất cả profile đang mở

### 4.4 Tab Proxy
- Xem danh sách proxy đang dùng
- Paste proxy mới → Click **Save**
- Click **Test** để kiểm tra proxy còn sống không

### 4.5 Tab Tasks (Quan trọng nhất)

| Task | Mô tả | Khi nào dùng |
|---|---|---|
| **Login** | Đăng nhập tất cả tài khoản | Lần đầu, hoặc sau khi bị logout |
| **Warmup** | Mô phỏng hành vi tự nhiên (scroll, xem, like) | Hàng ngày |
| **Interact** | Like, comment, kết bạn theo hashtag/group | Sau 7 ngày nuôi |
| **Post** | Đăng bài lên timeline | Sau 14 ngày nuôi |

**Cách chạy Task:**
1. Chọn loại Task cần chạy
2. Chọn intensity: `light` (nhẹ) / `medium` / `normal` (mạnh)
3. Click nút **Run**
4. Theo dõi log ở phần dưới màn hình
5. Đợi hoàn tất, KHÔNG tắt cửa sổ CMD

### 4.6 Tab Groups (Chia nhóm — Tiết kiệm RAM)
- Click **"Auto Assign Groups"** → nhập số acc/nhóm (ví dụ: 5)
- Dùng **"Run Group Task"** để chạy từng nhóm cuốn chiếu
- Cài delay giữa nhóm: **60–120 giây**

### 4.7 Tab Fanpage
- **Create Page**: Tự động tạo fanpage
- **Add Editor**: Thêm người quản trị vào page
- **Post**: Đăng bài/Reel lên fanpage

### 4.8 Sync Mode (Song song vs Tuần tự)
- **Tắt Sync Mode** (mặc định) = Chạy tuần tự từng acc → **Tiết kiệm RAM**
- **Bật Sync Mode** = Chạy song song tất cả acc cùng lúc → **Nhanh nhưng ngốn RAM**

> ✅ Máy dưới 16GB RAM: **Luôn tắt Sync Mode**

---

## 5. Quy Trình Nuôi Tài Khoản Chuẩn

### Tuần 1 (Ngày 1–7): Warm-up Nhẹ
| Thời điểm | Việc làm | Thao tác |
|---|---|---|
| Sáng 8h | Mở tool, Login tài khoản | Tab Tasks → Login |
| Sáng 9h | Warmup nhẹ | Tasks → Warmup → Light |
| Không cần làm gì thêm | — | — |

### Tuần 2 (Ngày 8–14): Tăng Tương Tác
| Thời điểm | Việc làm | Thao tác |
|---|---|---|
| Sáng 8h | Warmup | Tasks → Warmup → Medium |
| Chiều 3h | Interact | Tasks → Interact |

### Tuần 3+ (Ngày 15 trở đi): Chế Độ Active
| Thời điểm | Việc làm | Thao tác |
|---|---|---|
| Sáng 8h | Warmup | Tasks → Warmup → Normal |
| Trưa 12h | Đăng bài | Tasks → Post |
| Chiều 6h | Interact | Tasks → Interact |

---

## 6. Quản Lý Fanpage

### Quy trình tạo Fanpage mới:
1. Đảm bảo tài khoản chủ (owner) đã ở trạng thái `active` (nuôi ít nhất 14 ngày)
2. Tab **Fanpage** → **Create Page**
3. Điền: Tên page, Category, Mô tả
4. Chọn Profile của tài khoản chủ
5. Click **Tạo Page** → Đợi hoàn tất

### Thêm Editor/Admin vào Page:
1. Tab **Fanpage** → **Add Editor**
2. Nhập URL page, email editor, chọn role (Editor/Admin)
3. Click **Add**

### Đăng bài lên Page:
1. Tab **Fanpage** → **Post to Page**
2. Chọn page, nhập nội dung
3. Chọn loại: **Post** (văn bản/ảnh) hoặc **Reel** (video)
4. Click **Đăng**

---

## 7. Tối Ưu RAM Máy

### Khi máy bị chậm / lag:

**Cách 1: Chia nhóm nhỏ**
1. Tab Groups → Auto Assign Groups → nhập **5** (5 acc/nhóm)
2. Dùng Run Group Task thay vì chạy toàn bộ

**Cách 2: Đóng profile sau khi dùng**
- Tab Profiles → **Close All** sau mỗi task

**Cách 3: Tắt các app không cần thiết**
- Tắt Chrome, Word, Excel khi đang chạy tool

**Cách 4: Giảm số acc chạy song song**
- Tắt Sync Mode
- Chạy nhóm 5 acc thay vì 20 acc

### Dấu hiệu máy đang quá tải:
- IX Browser mở chậm / đơ
- Tool báo "Browser failed" liên tục
- Máy tính quạt chạy rất to
- Task Manager RAM > 85%

---

## 8. Xử Lý Sự Cố

### ❌ Lỗi: "Browser failed" / Profile không mở được
**Nguyên nhân:** IX Browser chưa mở hoặc API IX Browser lỗi  
**Xử lý:**
1. Kiểm tra IX Browser đang chạy chưa
2. Tắt hoàn toàn IX Browser → mở lại
3. Đợi 30 giây → thử lại

### ❌ Lỗi: "A task is already running"
**Nguyên nhân:** Đang có task khác chạy dở  
**Xử lý:**
1. Tab Tasks → Click **Stop Task**
2. Đợi 10 giây → chạy lại

### ❌ Tài khoản bị Checkpoint
**Dấu hiệu:** FB yêu cầu xác minh danh tính  
**Xử lý:**
1. Tab Accounts → Đổi status tài khoản đó thành `checkpoint`
2. Không chạy automation trên tài khoản đó
3. Mở IX Browser → profile đó → xác minh thủ công
4. Sau khi xác minh xong → đổi status về `warming`
5. Nuôi thêm 3–5 ngày trước khi dùng lại

### ❌ Tài khoản bị Die
**Dấu hiệu:** Không thể đăng nhập, bị khóa vĩnh viễn  
**Xử lý:**
1. Tab Accounts → Đổi status thành `die`
2. Báo cáo lại cho quản lý
3. Không xóa khỏi hệ thống (để lưu lịch sử)

### ❌ Tool không kết nối được IX Browser
**Xử lý:**
1. Kiểm tra IX Browser Local API đang chạy ở port **53200**
2. Thử vào: http://127.0.0.1:53200 trên trình duyệt
3. Nếu không vào được → restart IX Browser

### ❌ Proxy lỗi / Không kết nối
**Xử lý:**
1. Tab Proxy → Test từng proxy
2. Proxy báo lỗi → xóa và thay proxy mới
3. Liên hệ nhà cung cấp proxy để đổi IP

---

## 9. Quy Tắc An Toàn Bắt Buộc

> 🔴 Vi phạm các quy tắc này sẽ khiến tài khoản bị die hàng loạt

1. **1 profile = 1 proxy** — Tuyệt đối không dùng chung IP giữa các tài khoản
2. **Không chạy quá 2–3 action/ngày** với tài khoản dưới 7 ngày tuổi
3. **Không bật Sync Mode** khi nuôi tài khoản mới (chỉ dùng cho acc đã active 30+ ngày)
4. **Luôn để random delay** — Không tắt chức năng delay của tool
5. **Không đăng bài thương mại** khi acc chưa nuôi đủ 14 ngày
6. **Backup `accounts.json`** mỗi tuần một lần
7. **Không share màn hình** khi đang chạy tool (bảo mật thông tin)
8. **Báo ngay cho quản lý** khi có hơn 5 acc bị checkpoint cùng lúc

---

## 10. Checklist Cuối Ngày

Trước khi tắt máy, kiểm tra:

- [ ] Tất cả task đã hoàn tất (không còn task đang running)
- [ ] Click **Close All Profiles** trong tab Profiles
- [ ] Kiểm tra log xem có lỗi bất thường không
- [ ] Ghi chú lại số tài khoản bị checkpoint trong ngày
- [ ] Backup file `accounts.json` vào folder backup
- [ ] Tắt tool (Ctrl+C trong CMD)
- [ ] Tắt IX Browser

---

## 📞 Liên Hệ Hỗ Trợ

Khi gặp vấn đề không xử lý được:
- Chụp màn hình lỗi (Log trong tool)
- Ghi lại: Đang làm gì? Lỗi gì hiện ra? Bao nhiêu acc bị ảnh hưởng?
- Báo cáo cho quản lý kỹ thuật

---

*Tài liệu này chỉ dành cho nội bộ. Không chia sẻ ra ngoài.*
