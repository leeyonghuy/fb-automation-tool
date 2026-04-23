# Content Factory - Video Crawler System

Hệ thống tự động tìm kiếm và tải video từ YouTube, Douyin, Xiaohongshu.

## Cấu trúc thư mục

```
D:\Contenfactory\
├── API\
│   └── nha-may-content-208dc5165e29.json   # Google Service Account credentials
├── crawler\
│   ├── video_downloader.py     # Engine tải video (yt-dlp)
│   ├── sheets_manager.py       # Đọc/ghi Google Sheets
│   ├── orchestrator.py         # Điều phối 2 luồng chính
│   └── requirements.txt        # Python dependencies
├── n8n\
│   └── workflow_content_factory.json  # n8n workflow import
├── logs\                        # Log files (tự tạo)
├── setup_ggsheet.py             # Tạo Google Sheet lần đầu
└── README.md
```

---

## Bước 1: Cài đặt môi trường

```powershell
# Cài Python dependencies
pip install -r D:\Contenfactory\crawler\requirements.txt

# Cài yt-dlp (nếu chưa có)
pip install yt-dlp

# Cài ffmpeg (cần để merge video+audio)
# Tải từ https://ffmpeg.org/download.html và thêm vào PATH
```

---

## Bước 2: Tạo Google Sheet

```powershell
cd D:\Contenfactory
python setup_ggsheet.py
```

Lệnh này sẽ in ra URL và **Spreadsheet ID** (dạng `1BxiMVs0XRA...`).  
**Lưu lại Spreadsheet ID này!**

### Cấu trúc Google Sheet

**Tab Channels:**
| Platform | Channel Link | Channel Name | Topic | Last Video URL | Status |
|----------|-------------|--------------|-------|----------------|--------|
| youtube  | https://youtube.com/@... | Tên kênh | Beauty | | Active |

**Tab Videos:**
| Video Link | Platform | Topic | Download Status | File Path | Created At |
|-----------|---------|-------|----------------|-----------|------------|
| https://... | douyin | Travel | Pending | | 2026-04-22 |

> Để kích hoạt tải video thủ công: thêm link vào cột **Video Link**, đặt **Download Status = Pending**

---

## Bước 3: Cấu hình Spreadsheet ID

Mở file `D:\Contenfactory\crawler\orchestrator.py`, cập nhật dòng:

```python
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "YOUR_SPREADSHEET_ID_HERE")
```

Hoặc set biến môi trường:
```powershell
$env:SPREADSHEET_ID = "1BxiMVs0XRA..."
```

---

## Bước 4: Chạy thủ công (test)

```powershell
cd D:\Contenfactory\crawler

# Tải 1 video đơn
python video_downloader.py "https://www.youtube.com/watch?v=xxx" --topic "Beauty"

# Quét kênh
python video_downloader.py "https://youtube.com/@channelname" --mode channel --topic "Travel"

# Chạy Luồng 1 (quét kênh từ GSheet)
python orchestrator.py --mode channels --spreadsheet-id "YOUR_ID"

# Chạy Luồng 2 (xử lý video Pending từ GSheet)
python orchestrator.py --mode videos --spreadsheet-id "YOUR_ID"

# Chạy cả 2 luồng
python orchestrator.py --mode all --spreadsheet-id "YOUR_ID"
```

---

## Bước 5: Tích hợp n8n

1. Mở n8n UI (thường tại `http://localhost:5678`)
2. Vào **Settings → Import workflow**
3. Import file: `D:\Contenfactory\n8n\workflow_content_factory.json`
4. Vào **Settings → Environment Variables**, thêm:
   - `SPREADSHEET_ID` = Spreadsheet ID của bạn
5. Activate workflow

### Luồng n8n:

```
[Schedule: 3h]  →  [Run Channel Scan]  →  [Parse Result]
[Webhook POST /download-video]  →  [Run Manual Download]  →  [Response]
```

**Trigger thủ công qua Webhook:**
```bash
curl -X POST http://localhost:5678/webhook/download-video
```

---

## Cấu trúc thư mục Video tải về

```
D:\Videos\
├── Beauty\
│   └── 2026-04-22\
│       ├── abc123.mp4
│       └── def456.mp4
├── Travel\
│   └── 2026-04-22\
│       └── xyz789.mp4
```

---

## Hỗ trợ nền tảng

| Platform | Hỗ trợ | Ghi chú |
|----------|---------|---------|
| YouTube | ✅ Đầy đủ | Kênh + video đơn |
| Douyin | ✅ Cơ bản | Video công khai |
| Xiaohongshu | ⚠️ Hạn chế | Cần cookies nếu video private |
| TikTok | ✅ Cơ bản | Qua Douyin extractor |

### Cookies cho Xiaohongshu/Douyin (nếu cần)

1. Cài extension "Get cookies.txt" trên Chrome
2. Đăng nhập vào xiaohongshu.com hoặc douyin.com
3. Export cookies → lưu vào `D:\Contenfactory\crawler\cookies\xhs_cookies.txt`

---

## Log files

- `D:\Contenfactory\logs\downloader.log` — Log tải video
- `D:\Contenfactory\logs\orchestrator.log` — Log điều phối

---

## Xử lý lỗi thường gặp

| Lỗi | Giải pháp |
|-----|-----------|
| `yt-dlp not found` | `pip install yt-dlp` hoặc thêm vào PATH |
| `ffmpeg not found` | Tải ffmpeg và thêm vào PATH |
| `403 Forbidden` | Video bị giới hạn, cần cookies |
| `Spreadsheet not found` | Kiểm tra lại SPREADSHEET_ID |
| `Service account permission denied` | Share sheet với email service account |
