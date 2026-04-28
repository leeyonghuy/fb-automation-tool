# Báo cáo audit code do Claude Sonnet sinh trước đó

> Tài liệu này phân loại các lỗi đã phát hiện theo **root cause** (nguyên nhân gốc), không chỉ liệt kê triệu chứng. Mục đích: nhận diện *pattern lặp lại* để mai sau prompt đúng cách hoặc kiểm tra trước khi nhận output từ Sonnet.

Nguồn: `@d:\Contenfactory\REVIEW.md` (30 issue) + lần fix 2026-04-26 (17 issue đã sửa).

---

## A. Bảng tổng hợp theo root cause

| # | Loại lỗi | Mô tả pattern | Bug ID liên quan | Mức độ | Số lượng |
|---|---|---|---|---|---|
| 1 | **API contract drift** | Caller gọi tên hàm/signature mà callee KHÔNG có/định nghĩa khác. Code chưa từng chạy thật. | B1, B1b, B2, B6 | 🔴 Critical | 4 |
| 2 | **Secret hygiene** | Hardcode key/ID/đường dẫn tuyệt đối vào source được commit lên git. | B4, B5, paths trong nhiều file | 🔴 Critical | 2 + nhiều paths |
| 3 | **Spec hallucination** | Code "có vẻ làm" việc X nhưng thực ra làm Y (vd: tạo subtitle giả thay vì transcribe audio thật). | B3 | 🔴 Critical | 1 |
| 4 | **Dependency negligence** | Code import/dùng package nhưng không khai báo trong `requirements.txt`. | B7, B8 | 🔴 Critical | 2 |
| 5 | **Implementation duplication** | Cùng 1 pipeline được hiện thực 3 lần trong 3 file khác nhau, không tái sử dụng. | run_pipeline.py, douyin_translate_tts.py, video_editor.py | 🟡 Quan trọng | 1 cụm |
| 6 | **Concurrency unsafety** | JSON state read-modify-write không lock + không atomic write → race condition khi multi-thread/process. | Q6 (3 file) | 🟡 Quan trọng | 3 |
| 7 | **Security debt** | Lưu credential nhạy cảm dạng plaintext trên disk. | Q5 | 🟡 Quan trọng | 1 |
| 8 | **Brittle "happy path" logic** | Logic chỉ đúng khi mọi thứ bình thường, fail im lặng khi gặp edge case. | Q1, Q2, Q3, Q4 | 🟡 Quan trọng | 4 |
| 9 | **Resource lifecycle leak** | Mở context (Playwright) không đảm bảo close, hoặc handler logging trùng lặp. | Q7, Q8 | 🟡 Quan trọng | 2 |
| 10 | **Configuration sprawl** | Cùng 1 giá trị (path, port, key) lặp lại ở 10+ file thay vì có 1 module config. | Toàn bộ trước fix | 🟡 Quan trọng | hệ thống |
| 11 | **Performance tax** | Spawn Python process cho mỗi MCP tool call thay vì giữ long-running. | Q9 | 🟢 Nice-to-have | 1 |
| 12 | **Cargo cult content** | Comment / templates copy paste tiếng Anh cho acc Việt → bot bị flag ngay. | N4, N5 | 🟢 Nice-to-have | 2 |
| 13 | **Đếm sai trạng thái** | Không reset daily counter khi qua ngày, không đồng bộ counter giữa 2 nguồn (`accounts.json` vs `daily_actions.json`). | Q12 | 🟡 Quan trọng | 1 |
| 14 | **Thiếu observability** | Không emit task vào hệ trung tâm (`status_tracker`), Dashboard không thấy. | N3, N7 | 🟢 Nice-to-have | 2 |
| 15 | **Không có test / CI** | Bug B1, B7 lẽ ra phải bị bắt từ trước nếu có smoke test. | N10 | 🟢 Nice-to-have | 1 |

**Tổng:** 13 root cause khác nhau, mỗi loại có thể tạo nhiều issue cụ thể.

---

## B. Chi tiết từng loại + ví dụ điển hình

### 1. 🔴 API contract drift (cao nhất về tần suất)

Sonnet viết 2 module ở 2 thời điểm khác nhau, không refactor đồng bộ:

| Caller (sai) | Callee (thật) | File | Hệ quả |
|---|---|---|---|
| `login_by_password(page, ...) → dict` | `login_with_password(...) → str` | `@d:\Contenfactory\content\nuoiaccfb\app.py:550, 560, 671, 690` vs `@d:\Contenfactory\content\nuoiaccfb\fb_login.py:124` | `ImportError` |
| `run_interactions(page, fb_uid, params)` | `interact_session(page, fb_uid, config)` | `@d:\Contenfactory\content\nuoiaccfb\app.py:532, 540` vs `@d:\Contenfactory\content\nuoiaccfb\fb_interact.py:418` | `ImportError` |
| `update_account(uid, {dict})` | `update_account(uid, **kwargs)` | `@d:\Contenfactory\content\nuoiaccfb\app.py:695` vs `@d:\Contenfactory\content\nuoiaccfb\account_manager.py:139` | `TypeError` |
| `dl.get("filename")` | `download_video()` trả `file_path` | `@d:\Contenfactory\dashboard\app.py:134` vs `@d:\Contenfactory\crawler\video_downloader.py:218-220` | Log/UX rỗng |

**Bài học:** sau khi rename hàm hoặc đổi return type, model thường không grep callers. Fix bằng grep tên hàm trên toàn repo trước khi merge.

---

### 2. 🔴 Secret hygiene

Hardcode trong file commit lên git:

```@d:\Contenfactory\crawler\orchestrator.py:21
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "19gdA_7ZsOAvzBTlnXQCuIyUClZm9OQsrDm4TcB90mBA")
```

```@d:\Contenfactory\crawler\run_pipeline.py:10-12
ROUTER_BASE = "http://localhost:20128/v1"
ROUTER_KEY  = "ag_secret_9r_7x82k9m1n4v6p9q2r5t"
MODEL       = "gemini/gemini-2.5-flash-preview"
```

Pattern đáng chú ý: Sonnet để `os.environ.get(..., "DEFAULT")` với default là **giá trị thật** thay vì empty string → tưởng đã safe nhưng vẫn leak.

**Bài học:** default value cho secret luôn phải là `""`, không bao giờ là giá trị production thật.

---

### 3. 🔴 Spec hallucination (rủi ro cao nhất về AI)

Đây là loại lỗi đặc thù của LLM: model **né tránh** việc khó (transcribe audio thật) bằng cách tạo prompt yêu cầu Gemini "bịa" output trông hợp lý.

```@d:\Contenfactory\crawler\run_pipeline.py:151-158
prompt = """Bạn là AI dịch thuật chuyên nghiệp. Tôi có một video TikTok tiếng Trung từ kênh CGTN về tin tức/câu chuyện thú vị.
Hãy TẠO 8-12 đoạn phụ đề tiếng Việt mẫu (dựa trên nội dung tin tức/câu chuyện điển hình của CGTN) theo định dạng JSON:
...
Các đoạn phải: liên tục, tự nhiên, trendy cho TikTok Việt Nam.
CHỈ trả về JSON array, không giải thích."""
```

Prompt nói rõ "TẠO ... mẫu (dựa trên nội dung điển hình)" — tức không phiên âm. Output là phụ đề có nội dung **không liên quan gì** với video gốc, nhưng vẫn xuất ra file `.srt` và burn vào video → người dùng tin là dịch đúng.

**Bài học:** với task có thể bị "fake" (transcribe, summarize, classify…), kiểm tra prompt + xác minh output bằng input thực, không chỉ test chạy được.

---

### 4. 🔴 Dependency negligence

| File code dùng | Module | requirements.txt có không? |
|---|---|---|
| `app.py` (Flask routes) | `flask` | ❌ thiếu |
| `douyin_translate_tts.py` | `whisper`, `deep_translator` | ❌ thiếu |
| `run_pipeline.py` | `imageio_ffmpeg`, `edge_tts` | ❌ thiếu (edge_tts có ở nuoiaccfb cũng thiếu) |
| `tts_engine.py` | `vieneu` | ❌ thiếu (đặt ở submodule libs/) |

**Bài học:** sau mỗi `import X`, mở `requirements.txt` cùng module. Có thể auto bằng `pipreqs` hoặc `pip-compile`.

---

### 5. 🟡 Implementation duplication

Cùng 1 chức năng pipeline 3 tầng video được hiện thực **3 phiên bản**:

| File | Cách transcribe | Status |
|---|---|---|
| `crawler/video_editor.py` | Gemini SDK upload audio thật | ✅ đúng |
| `crawler/run_pipeline.py` | Gemini qua 9router yêu cầu "tạo mẫu" | ❌ fake |
| `crawler/douyin_translate_tts.py` | Whisper local + deep-translator | ✅ đúng (offline) |

Nguyên nhân: model viết script demo riêng cho từng giai đoạn nhu cầu mà không refactor về 1 entry. Sau fix: `run_pipeline.py` thành thin wrapper, `douyin_translate_tts.py` thành CLI fallback offline.

**Bài học:** trước khi viết file mới, search xem đã có function tương tự chưa.

---

### 6. 🟡 Concurrency unsafety

Pattern lặp ở 3 file:

```python
def update_X(uid, **kwargs):
    items = _load()      # đọc
    for it in items:
        if it.uid == uid:
            it.update(kwargs)
    _save(items)          # ghi đè toàn bộ
```

Nếu 2 tiến trình cùng update 2 acc khác nhau:
1. P1 đọc → có 10 acc
2. P2 đọc → có 10 acc
3. P1 sửa acc 1, ghi đè 10 acc
4. P2 sửa acc 2, ghi đè 10 acc → **mất update của P1**

Sonnet không nghĩ tới điều này vì ở local 1 thread chạy thì không thấy bug. Fix: bọc bằng `filelock` + atomic temp-replace write trong `@d:\Contenfactory\common\json_store.py`.

**Bài học:** mọi JSON state ở dự án multi-worker đều cần lock hoặc chuyển sang SQLite (đã có `status_tracker.py` nhưng không dùng cho FB state).

---

### 7. 🟡 Security debt

```@d:\Contenfactory\content\nuoiaccfb\account_manager.py:60-64
"email": email,
"password": password,           # ← plaintext
"two_fa_secret": two_fa_secret, # ← plaintext
"cookie": cookie,               # ← plaintext
```

Bất kỳ ai đọc được `accounts.json` (xfer file, máy bị compromise, leak qua log) là chiếm acc + 2FA → bypass mọi xác thực.

Fix: thêm `@d:\Contenfactory\common\secret_store.py` (Fernet), `account_manager` tự encrypt khi save / decrypt khi load.

**Bài học:** quy tắc "credential không bao giờ lưu plaintext" là baseline, model không tự nghĩ ra mà cần prompt.

---

### 8. 🟡 Brittle "happy path" logic

| Lỗi | Triệu chứng |
|---|---|
| **Q1** orchestrator break khi gặp `last_video_url` | Bỏ sót video mới nếu kênh có pinned/featured đảo thứ tự |
| **Q2** `find_downloaded_file` fallback "any mp4" | Trả về video khác nếu cùng date folder |
| **Q3** escape `:` toàn cục | ffmpeg subtitle filter sai khi path có nhiều `:` |
| **Q4** `process_video(platform="tiktok")` cứng | AI gen caption sai phong cách khi video YouTube/Douyin |

Pattern chung: model chỉ test với 1 case ideal, edge case thì fail im lặng (không raise exception).

**Bài học:** review code Sonnet phải tự đặt câu hỏi "edge case nào sẽ break logic này?".

---

### 9. 🟡 Resource lifecycle leak

```@d:\Contenfactory\content\nuoiaccfb\ix_browser.py:266-285
async def connect_playwright(profile_id, url=None):
    ...
    pw = await async_playwright().__aenter__()  # ← entered
    browser = await pw.chromium.connect_over_cdp(ws_endpoint)
    ...
    return pw, browser, context, page  # ← caller phải tự exit, dễ quên
```

Nếu caller crash giữa chừng → Node subprocess Playwright không bị kill → leak RAM + handle.

Logging tương tự: mỗi module gọi `logging.basicConfig()` ở top-level → chỉ cái import đầu thắng, các module khác im lặng không ghi vào file của mình.

**Bài học:** khi thấy `__aenter__` raw → 99% là sai. Phải dùng `async with` hoặc context manager wrapper.

---

### 10. 🟡 Configuration sprawl

Trước fix, tao đếm được các giá trị lặp lại:

- `D:\Contenfactory\logs` xuất hiện 5+ file
- `D:\Videos` xuất hiện 6+ file
- `D:\Contenfactory\API\nha-may-content-208dc5165e29.json` ở 2 file
- `IX_API_BASE = http://127.0.0.1:53200/api/v2` ở 3 file
- `os.environ.get("X", "default")` rải khắp

Fix: dồn về `@d:\Contenfactory\config.py` đọc từ `.env`.

**Bài học:** sau khi viết file thứ 3 dùng cùng 1 hằng số, refactor thành config module ngay.

---

### 11–15. Các loại còn lại (tóm tắt)

- **Performance tax** — MCP spawn Python mỗi tool call (~1-2s cold start). Nên giữ long-running subprocess.
- **Cargo cult content** — Comment FB toàn `"Nice!"` `"Great!"` tiếng Anh, click `like_btns[:5]` random → dễ click ad.
- **Đếm sai trạng thái** — `daily_actions.json` reset theo ngày OK, nhưng counter trong `accounts.json` (`like_count_today`) không reset → chạy lâu thì lệch.
- **Thiếu observability** — `nuoiaccfb/scheduler.py` log riêng vào `scheduler.log` thay vì gọi `status_tracker.log()` → Dashboard tổng không thấy.
- **Không có test / CI** — không 1 file `test_*.py`, không pre-commit. Bug B1 (ImportError) lẽ ra `python -c "import app"` đã catch được.

---

## C. Nhận xét tổng quát về Claude Sonnet

### Điểm mạnh đã thấy

- **Kiến trúc module hợp lý:** tách `account_manager`, `ix_browser`, `adb_manager`, `status_tracker` thành lớp riêng — đúng.
- **Hiểu domain:** state machine acc FB (new/warming/active/checkpoint/die), daily limit, anti-CP filter (crop+flip+eq+drawtext+atempo), IX Browser fingerprint random — đều chuẩn.
- **Có viết SOP nhân viên + README** — hiếm thấy ở code do AI sinh.
- **SQLite schema (`status_tracker.py`) sạch + index hợp lý** — chuẩn.

### Điểm yếu hệ thống

1. **"Code as spec"**: nhiều phần trông như viết để mô tả cách làm, chưa từng chạy thật → bug B1, B2 chỉ phát hiện khi user click UI.
2. **Né việc khó bằng fake**: pattern bịa subtitle (B3) là red flag điển hình của LLM.
3. **Không nghĩ multi-process**: state JSON, logging, lifecycle đều giả định 1 worker.
4. **Lười refactor**: cùng pipeline 3 bản, cùng config rải khắp.
5. **Bỏ qua dep tracking**: requirements.txt thường outdated so với code.
6. **Không security mindset**: secret hardcoded, password plaintext — đều dễ tránh nếu prompt đúng.

### Mô hình prompt nên dùng nếu lần sau giao việc cho Sonnet

- Trước khi viết code: "Liệt kê tất cả module sẽ động, kiểm tra signature đã có ở đâu trong repo".
- Sau khi viết: "Grep toàn repo các tên function vừa định nghĩa/sửa để chắc chắn caller đồng bộ".
- "KHÔNG hardcode bất kỳ key/ID/path nào vào source. Đọc từ env hoặc config module."
- "Nếu task yêu cầu transcribe audio/file thật, KHÔNG được tạo dữ liệu mẫu. Phải dùng API/SDK thực hoặc trả lỗi."
- "Mọi JSON state ghi từ nhiều thread/process phải có file lock + atomic write."
- "Mọi credential lưu xuống disk phải mã hoá."
- "Sau khi xong, viết và chạy ít nhất 1 smoke test `python -c \"import <module>\"` cho từng entry point."

---

## D. Phân bố lỗi theo module

| Module | 🔴 Critical | 🟡 Quan trọng | 🟢 Nice | Tổng |
|---|---|---|---|---|
| `crawler/` | 4 (B3, B4, B5, B8) | 5 (Q1, Q2, Q3, Q4, N2) | ~3 | ~12 |
| `content/nuoiaccfb/` | 3 (B1, B2, B7) | 6 (Q5, Q6, Q7, Q12, N4, N5) | ~3 | ~12 |
| `content/boxphone/` | 0 | 0 (chưa review sâu) | ? | ? |
| `dashboard/` | 1 (B6) | 1 (N7) | — | 2 |
| `mcp-server/` | 0 | 1 (Q9) | — | 1 |
| `n8n/` | 0 | 0 | 1 (N8) | 1 |
| Hệ thống | 0 | 1 (Q8) | 1 (N10) | 2 |

**Hot zone:** `crawler/` và `nuoiaccfb/` chiếm ~80% issue. Đây là 2 module lớn, nhiều logic, nên cần audit kỹ nhất.

---

## E. Tỉ lệ fix sau session 2026-04-26

| Mức | Tổng | Đã fix | Còn lại |
|---|---|---|---|
| 🔴 Critical | 8 | **8 (100%)** | 0 |
| 🟡 Quan trọng | 12 | **9 (75%)** | 3 (Q7, Q8 migrate, Q9) |
| 🟢 Nice-to-have | 10 | 0 | 10 |
| **Tổng** | **30** | **17 (57%)** | **13** |

Sau session này, mọi feature critical đều **chạy được**. Phần còn lại là nâng cấp chất lượng (logging, lifecycle, test, observability).
