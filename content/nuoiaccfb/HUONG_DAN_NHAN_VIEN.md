# 📘 HƯỚNG DẪN VẬN HÀNH TOOL NUÔI ACC FACEBOOK
### Dành cho nhân viên — Không cần biết lập trình

---

## 🖥️ YÊU CẦU MÁY TÍNH

> ⚠️ **Tool này ngốn RAM khá nhiều vì mỗi tài khoản FB = 1 cửa sổ trình duyệt riêng (IX Browser)**

| Số tài khoản chạy cùng lúc | RAM tối thiểu | RAM khuyến nghị |
|---------------------------|---------------|-----------------|
| 5 tài khoản | 8 GB | 12 GB |
| 10 tài khoản | 12 GB | 16 GB |
| 20 tài khoản | 20 GB | 32 GB |
| 30+ tài khoản | 32 GB | 64 GB |

**Tại sao ngốn RAM?**
- IX Browser mở 1 cửa sổ Chromium riêng cho mỗi tài khoản → ~400–600 MB/tài khoản
- Python + Playwright điều khiển tự động → ~100–200 MB
- Tổng: **~500–800 MB mỗi tài khoản đang chạy**

**Giải pháp tiết kiệm RAM:**
- ✅ Không chạy tất cả cùng lúc — chạy theo **lô 5–10 tài khoản**, xong lô này mới chạy lô khác
- ✅ Đóng các ứng dụng không cần thiết (Chrome, Zalo, v.v.) trước khi chạy
- ✅ Sau mỗi lô, tool tự đóng trình duyệt — RAM được giải phóng

---

## 📦 CÀI ĐẶT LẦN ĐẦU (Chỉ làm 1 lần)

### Bước 1: Cài Python
1. Vào https://python.org/downloads → tải Python 3.11
2. Khi cài: **tick vào "Add Python to PATH"** ✅
3. Kiểm tra: mở CMD → gõ `python --version` → thấy số version là OK

### Bước 2: Cài IX Browser
1. Vào https://ixbrowser.com → tải và cài đặt
2. Đăng ký tài khoản miễn phí (100 profile free)
3. **Mở IX Browser lên và để chạy nền** — tool cần IX Browser đang chạy

### Bước 3: Cài thư viện Python
Mở CMD, gõ lần lượt:
```
cd d:\Contenfactory\content\nuoiaccfb
pip install -r requirements.txt
playwright install chromium
```
Chờ cài xong (5–10 phút, cần internet)

---

## 🚀 KHỞI ĐỘNG TOOL MỖI NGÀY

### Bước 1: Mở IX Browser
- Double-click icon IX Browser trên desktop
- Chờ IX Browser load xong (thấy giao diện danh sách profile)

### Bước 2: Mở Web Dashboard
Mở CMD, gõ:
```
cd d:\Contenfactory\content\nuoiaccfb
python app.py
```
Sau đó mở trình duyệt (Chrome/Edge) vào: **http://localhost:5000**

> 💡 Để CMD đó mở suốt ngày — đừng đóng lại!

---

## 📋 CÁC CÔNG VIỆC HÀNG NGÀY

### 🌅 BUỔI SÁNG (8:00 – 9:00): Warm-up tài khoản

**Warm-up là gì?** Tool tự động vào Facebook, scroll newsfeed, like bài, xem video — giả lập hành vi người dùng thật để tài khoản không bị khóa.

**Cách làm:**
1. Vào tab **"Warm-up"** trên dashboard
2. Chọn tài khoản cần warm (hoặc chọn tất cả)
3. Nhấn **"Bắt đầu Warm-up"**
4. Chờ tool chạy — **KHÔNG đụng vào máy** khi tool đang chạy
5. Xem log bên dưới — ✅ = thành công, ❌ = lỗi

**Thời gian:** ~3–5 phút/tài khoản

---

### ☀️ BUỔI TRƯA (11:30 – 12:30): Đăng bài

**Cách làm:**
1. Vào tab **"Đăng bài"**
2. Chọn tài khoản và loại bài (timeline / group / fanpage)
3. Nhập nội dung hoặc chọn file nội dung có sẵn
4. Nhấn **"Đăng ngay"** hoặc **"Lên lịch"**

**Lưu ý:**
- Mỗi tài khoản chỉ đăng **1–2 bài/ngày** khi mới nuôi (dưới 7 ngày)
- Tài khoản đã nuôi lâu (>14 ngày) có thể đăng 3–5 bài/ngày

---

### 🌆 BUỔI CHIỀU (17:00 – 18:00): Tương tác

**Cách làm:**
1. Vào tab **"Tương tác"**
2. Nhấn **"Chạy tương tác"**
3. Tool tự động: like bài, comment, kết bạn, tham gia group

---

### 🌙 CUỐI NGÀY: Kiểm tra trạng thái

1. Vào tab **"Tài khoản"**
2. Kiểm tra cột **"Trạng thái"**:
   - 🟢 `active` = bình thường
   - 🟡 `warming` = đang nuôi, chưa dùng được
   - 🔴 `checkpoint` = FB yêu cầu xác minh → báo cáo ngay
   - ⚫ `die` = tài khoản chết → báo cáo ngay

---

## ⚠️ XỬ LÝ SỰ CỐ THƯỜNG GẶP

### ❌ Lỗi "IX Browser không kết nối được"
**Nguyên nhân:** IX Browser chưa mở hoặc bị crash
**Cách xử lý:**
1. Kiểm tra IX Browser có đang chạy không
2. Nếu không → mở lại IX Browser
3. Chờ 30 giây → thử lại

---

### ❌ Lỗi "Không mở được profile"
**Nguyên nhân:** Profile bị lỗi hoặc đang mở ở nơi khác
**Cách xử lý:**
1. Vào IX Browser → tìm profile đó → đóng thủ công
2. Thử lại từ dashboard

---

### ❌ Máy bị đơ / chậm khi tool chạy
**Nguyên nhân:** Hết RAM
**Cách xử lý:**
1. Dừng tool (Ctrl+C trong CMD)
2. Đóng bớt ứng dụng khác
3. Giảm số tài khoản chạy cùng lúc (vào Settings → giảm `max_concurrent`)
4. Chạy lại

---

### ❌ Tài khoản bị checkpoint
**Nguyên nhân:** Facebook phát hiện hành vi bất thường
**Cách xử lý:**
1. **Không** tiếp tục chạy tài khoản đó
2. Vào IX Browser → mở profile đó thủ công
3. Vào Facebook → làm theo hướng dẫn xác minh (số điện thoại / email)
4. Sau khi xác minh xong → cập nhật trạng thái về `active`
5. Báo cáo cho quản lý

---

### ❌ Tool báo lỗi "proxy failed"
**Nguyên nhân:** Proxy hết hạn hoặc bị chặn
**Cách xử lý:**
1. Báo cáo cho quản lý để thay proxy mới
2. Không tự ý thay proxy nếu chưa được hướng dẫn

---

## 📊 THEO DÕI & BÁO CÁO

### Mỗi ngày cần ghi lại:
| Thông tin | Ghi chú |
|-----------|---------|
| Số tài khoản warm-up thành công | |
| Số bài đã đăng | |
| Số tài khoản bị lỗi/checkpoint | |
| Thời gian bắt đầu / kết thúc | |

### Báo cáo ngay cho quản lý khi:
- Có tài khoản bị `checkpoint` hoặc `die`
- Máy tính bị lỗi không khởi động được tool
- Proxy hàng loạt bị lỗi (>5 tài khoản cùng lúc)

---

## ⏰ LỊCH CHẠY KHUYẾN NGHỊ

```
08:00  Mở IX Browser + khởi động tool
08:15  Chạy Warm-up (lô 1: 10 tài khoản)
09:00  Chạy Warm-up (lô 2: 10 tài khoản tiếp theo)
09:45  Nghỉ — tool đóng trình duyệt, giải phóng RAM
11:30  Chạy Đăng bài
12:30  Nghỉ trưa
17:00  Chạy Tương tác
18:00  Kiểm tra trạng thái + ghi báo cáo
18:15  Tắt tool (Ctrl+C) + tắt IX Browser
```

---

## 🔒 QUY TẮC BẮT BUỘC

1. **KHÔNG** dùng máy tính cho việc khác khi tool đang chạy
2. **KHÔNG** tự ý thay đổi file cấu hình
3. **KHÔNG** đóng cửa sổ CMD khi tool đang chạy
4. **KHÔNG** chạy quá số tài khoản được phân công
5. **LUÔN** báo cáo lỗi ngay — đừng tự xử lý nếu không chắc

---

## 📞 LIÊN HỆ HỖ TRỢ

Khi gặp vấn đề không xử lý được:
- Chụp màn hình lỗi
- Ghi lại thời gian xảy ra
- Liên hệ quản lý kỹ thuật qua [kênh liên lạc nội bộ]
