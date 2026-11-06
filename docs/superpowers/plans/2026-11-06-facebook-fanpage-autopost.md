# Facebook Fanpage Auto-Poster & Content Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng ứng dụng Streamlit hỗ trợ người dùng nhập chủ đề, tự động tìm kiếm và tổng hợp thông tin qua Google Gemini với Google Search Grounding để viết bài chuẩn Fanpage, cho phép đính kèm ảnh và đăng ngay hoặc lên lịch đăng tự động lên Facebook Fanpage qua Facebook Graph API (hỗ trợ cả FB Native Schedule và Local APScheduler) với cơ sở dữ liệu SQLite cục bộ.

**Architecture:** Ứng dụng kiến trúc dạng module hóa (Modular Monolith) với giao diện người dùng bằng Streamlit. Tầng dịch vụ gồm `GeminiService` (tìm kiếm và sinh nội dung qua Gemini API Grounding), `FacebookService` (gọi Facebook Graph API v20.0 để kiểm tra token, tải ảnh lên và đăng/lên lịch bài viết), `SchedulerService` (APScheduler xử lý hẹn giờ local), và `DatabaseManager` (SQLite lưu trữ thông tin bài viết, trạng thái, đường dẫn ảnh và Facebook Post ID). Cấu hình lưu trữ an toàn trong file `.env` hoặc cập nhật trực tiếp trên UI.

**Tech Stack:** Python 3.10+, Streamlit, google-genai / google-generativeai, requests, APScheduler, SQLite3, pytest, python-dotenv, Pillow.

**Spec:** Thiết kế dựa trên yêu cầu người dùng thống nhất qua quá trình phỏng vấn:
- Tự động hóa: Người dùng gửi chủ đề -> AI tìm kiếm Google, tổng hợp thông tin và viết bài kèm hashtag, emoji chuẩn Fanpage.
- Hình ảnh: Người dùng chuẩn bị ảnh (upload qua Web UI hoặc chọn từ thư mục chỉ định `data/images`).
- Đăng bài: Đăng ngay lập tức hoặc lên lịch đăng (FB Native Schedule hoặc APScheduler local).
- Lưu trữ: SQLite cục bộ ghi nhận lịch sử bài viết, trạng thái, post ID.
- Giao diện: Streamlit chia tab trực quan (Tạo bài viết, Lịch trình & Lịch sử, Cài đặt kết nối).

## Global Constraints

- Mọi tương tác Facebook API phải bắt lỗi rõ ràng (lỗi token hết hạn code 190, lỗi quyền publish `pages_manage_posts`, lỗi giới hạn kích thước ảnh).
- Gemini API sử dụng tính năng Search Grounding để đảm bảo tin tức cập nhật chính xác theo chủ đề thời sự.
- Cơ sở dữ liệu SQLite tự khởi tạo schema nếu chưa tồn tại; không làm crash ứng dụng khi file DB mới.
- Không để lộ secret/access tokens ra log hoặc giao diện văn bản thô (mask token trên UI).
- Tất cả các module core services (`FacebookService`, `GeminiService`, `DatabaseManager`, `SchedulerService`) phải có unit tests độc lập giả lập API (mocking).

## Review Focus

1. Token Facebook hết hạn hoặc không đủ quyền `pages_manage_posts` / `pages_read_engagement` -> Ứng dụng phải thông báo lỗi chi tiết, gợi ý cách gia hạn token thay vì crash.
2. Người dùng đăng bài hẹn giờ trước thời điểm hiện tại hoặc hẹn giờ FB ngoài khoảng cho phép (Graph API yêu cầu tối thiểu sau 10 phút và tối đa 75 ngày) -> Validate và cảnh báo sớm trên UI.
3. Bài viết đính kèm file ảnh không hợp lệ (định dạng sai, file hỏng, dung lượng > 10MB) -> Xử lý ngoại lệ, thông báo rõ ràng trước khi gọi API Facebook.
4. Gemini API bị lỗi kết nối hoặc quota limit -> Fallback thông báo cho người dùng, lưu bài nháp với trạng thái draft.
5. Local APScheduler khởi động lại -> Tự động khôi phục các tác vụ hẹn giờ local chưa hoàn thành từ SQLite database.

---

### Task 1: Thiết lập cấu trúc dự án và Database Manager (SQLite)

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/database.py`
- Create: `tests/__init__.py`
- Create: `tests/test_database.py`

**Interfaces:**
- Consumes: Standard `sqlite3`
- Produces: `DatabaseManager(db_path: str = "data/fanpage.db")` với các methods:
  - `init_db() -> None`
  - `save_post(topic: str, content: str, image_path: str | None, status: str, scheduled_time: str | None, fb_post_id: str | None) -> int`
  - `update_post_status(post_id: int, status: str, fb_post_id: str | None = None, error_message: str | None = None) -> None`
  - `get_post_by_id(post_id: int) -> dict | None`
  - `get_all_posts(limit: int = 50) -> list[dict]`
  - `get_pending_local_scheduled_posts() -> list[dict]`

- [ ] **Step 1: Viết test cho DatabaseManager**
  Tạo `tests/test_database.py` kiểm tra khởi tạo bảng, thêm bài viết, cập nhật trạng thái, và lấy danh sách bài viết hẹn giờ.
- [ ] **Step 2: Chạy test để xác nhận test thất bại**
  Chạy: `pytest tests/test_database.py -v` (kỳ vọng FAIL vì chưa có file `src/database.py`).
- [ ] **Step 3: Tạo `requirements.txt` và cài đặt dependencies**
  Thêm `streamlit`, `requests`, `google-genai`, `apscheduler`, `python-dotenv`, `pillow`, `pytest`.
- [ ] **Step 4: Hiện thực `DatabaseManager` trong `src/database.py`**
  Khởi tạo bảng `posts` với các trường: `id`, `topic`, `content`, `image_path`, `status` (draft/scheduled_fb/scheduled_local/published/failed), `scheduled_time`, `fb_post_id`, `error_message`, `created_at`, `updated_at`.
- [ ] **Step 5: Chạy test để xác nhận test vượt qua**
  Chạy: `pytest tests/test_database.py -v` (kỳ vọng PASS).
- [ ] **Step 6: Tạo file `.env.example`**
  Khai báo mẫu: `GEMINI_API_KEY=`, `FB_PAGE_ID=`, `FB_PAGE_ACCESS_TOKEN=`.

---

### Task 2: Hiện thực Gemini Service với Search Grounding

**Files:**
- Create: `src/gemini_service.py`
- Create: `tests/test_gemini_service.py`

**Interfaces:**
- Consumes: `GEMINI_API_KEY` từ môi trường hoặc tham số
- Produces: `GeminiService(api_key: str | None = None)` với các methods:
  - `generate_fanpage_post(topic: str, tone: str = "chuyên nghiệp, hấp dẫn", include_hashtags: bool = True, use_search: bool = True) -> dict`
    Trả về: `{"content": str, "sources": list[str], "suggested_hashtags": list[str]}`

- [ ] **Step 1: Viết test cho GeminiService với mock client**
  Tạo `tests/test_gemini_service.py` mock API response của Google Gemini để kiểm tra sinh nội dung từ topic và xử lý grounding links.
- [ ] **Step 2: Chạy test để xác nhận test thất bại**
  Chạy: `pytest tests/test_gemini_service.py -v` (kỳ vọng FAIL vì chưa có `src/gemini_service.py`).
- [ ] **Step 3: Hiện thực `GeminiService` trong `src/gemini_service.py`**
  Xây dựng prompt tối ưu cho Facebook Fanpage (tiêu đề giật gân, đoạn mở đầu lôi cuốn, các ý chính có emoji sinh động, lời kêu gọi hành động Call-To-Action, cụm hashtags thịnh hành). Bật Google Search Tool nếu `use_search=True`.
- [ ] **Step 4: Chạy test để xác nhận test vượt qua**
  Chạy: `pytest tests/test_gemini_service.py -v` (kỳ vọng PASS).

---

### Task 3: Hiện thực Facebook Graph API Service

**Files:**
- Create: `src/facebook_service.py`
- Create: `tests/test_facebook_service.py`

**Interfaces:**
- Consumes: `page_id: str`, `access_token: str`
- Produces: `FacebookService(page_id: str, access_token: str)` với các methods:
  - `verify_token() -> dict` (kiểm tra token còn hạn không, tên Fanpage, quyền hạn `CREATE_CONTENT`, `MODERATE_CONTENT`)
  - `publish_text_post(message: str, scheduled_publish_time: int | None = None) -> dict`
  - `publish_photo_post(message: str, photo_path: str, scheduled_publish_time: int | None = None) -> dict`
  - `get_post_info(post_id: str) -> dict`

- [ ] **Step 1: Viết test cho FacebookService với mock `requests`**
  Tạo `tests/test_facebook_service.py` giả lập các kịch bản thành công và lỗi (token hết hạn code 190, upload ảnh thành công, publish bài text có hẹn giờ).
- [ ] **Step 2: Chạy test để xác nhận test thất bại**
  Chạy: `pytest tests/test_facebook_service.py -v` (kỳ vọng FAIL).
- [ ] **Step 3: Hiện thực `FacebookService` trong `src/facebook_service.py`**
  Gọi Graph API endpoint `https://graph.facebook.com/v20.0/{page_id}/feed` và `https://graph.facebook.com/v20.0/{page_id}/photos`. Xử lý `published=False` và `scheduled_publish_time` khi hẹn giờ trên Facebook.
- [ ] **Step 4: Chạy test để xác nhận test vượt qua**
  Chạy: `pytest tests/test_facebook_service.py -v` (kỳ vọng PASS).

---

### Task 4: Hiện thực Scheduler Service (Hẹn giờ Local qua APScheduler)

**Files:**
- Create: `src/scheduler_service.py`
- Create: `tests/test_scheduler_service.py`

**Interfaces:**
- Consumes: `DatabaseManager`, `FacebookService`
- Produces: `LocalSchedulerService(db: DatabaseManager, fb_service_provider: Callable[[], FacebookService])` với các methods:
  - `start() -> None`
  - `shutdown() -> None`
  - `schedule_post(post_id: int, run_date: datetime) -> str`
  - `cancel_scheduled_post(job_id: str) -> bool`
  - `load_and_reschedule_pending_jobs() -> int`

- [ ] **Step 1: Viết test cho LocalSchedulerService**
  Tạo `tests/test_scheduler_service.py` kiểm tra việc thêm job, kích hoạt callback đăng bài và cập nhật database.
- [ ] **Step 2: Chạy test để xác nhận test thất bại**
  Chạy: `pytest tests/test_scheduler_service.py -v` (kỳ vọng FAIL).
- [ ] **Step 3: Hiện thực `LocalSchedulerService` trong `src/scheduler_service.py`**
  Sử dụng `BackgroundScheduler` của `apscheduler`. Khi job chạy, đọc post từ database, gọi `FacebookService.publish_*`, cập nhật trạng thái `published` hoặc `failed`.
- [ ] **Step 4: Chạy test để xác nhận test vượt qua**
  Chạy: `pytest tests/test_scheduler_service.py -v` (kỳ vọng PASS).

---

### Task 5: Xây dựng Giao diện Web Streamlit (UI Dashboard)

**Files:**
- Create: `app.py`
- Create: `src/ui_helpers.py`

**Interfaces:**
- Tích hợp toàn bộ `GeminiService`, `FacebookService`, `DatabaseManager`, `LocalSchedulerService` vào giao diện Streamlit trực quan.

- [ ] **Step 1: Xây dựng Module Tab 1 - "Tạo bài viết với AI"**
  - Ô nhập chủ đề / từ khóa / link tham khảo.
  - Tùy chọn Tone giọng (Hài hước, Chuyên gia, Kể chuyện, Tin tức...), độ dài bài viết, bật/tắt Google Search.
  - Nút "Tìm kiếm & Viết bài": hiển thị trạng thái đang tìm kiếm web, tổng hợp nguồn tham khảo và xuất ra nội dung bài viết.
  - Khu vực tải lên / chọn ảnh đính kèm từ máy tính (kèm preview ảnh).
  - Trình soạn thảo Markdown/Text cho phép người dùng chỉnh sửa bài viết trực tiếp trước khi duyệt đăng.
- [ ] **Step 2: Xây dựng Module Tab 2 - "Đăng bài & Lên lịch"**
  - Xem trước giao diện bài viết như trên Facebook Fanpage (mô phỏng giao diện bài đăng FB).
  - 3 lựa chọn hành động:
    1. "Đăng ngay lên Fanpage".
    2. "Hẹn giờ qua Facebook Graph API" (chọn ngày giờ, tối thiểu 10 phút đến 75 ngày).
    3. "Hẹn giờ Local máy tính" (APScheduler).
  - Phản hồi kết quả kèm link bài viết vừa đăng lên Facebook.
- [ ] **Step 3: Xây dựng Module Tab 3 - "Lịch sử & Quản lý bài đăng"**
  - Bảng danh sách bài viết từ SQLite: Thời gian, Chủ đề, Ảnh, Trạng thái (Đã đăng / Đang chờ / Thất bại / Nháp), Link Facebook.
  - Nút thử lại bài viết bị lỗi hoặc xóa bài nháp.
- [ ] **Step 4: Xây dựng Module Tab 4 - "Cài đặt & Hướng dẫn Token"**
  - Nhập Gemini API Key, Facebook Page ID, Page Access Token (hỗ trợ lưu vào `.env` hoặc session).
  - Nút "Kiểm tra kết nối Fanpage": gọi `verify_token` hiển thị tên Page, avatar, tình trạng token còn hạn hay không.
  - Hướng dẫn chi tiết từng bước lấy Long-Lived Token (vĩnh viễn hoặc 60 ngày) từ Meta Developer Portal.

---

### Task 6: Kiểm thử tích hợp toàn diện và hoàn thiện tài liệu hướng dẫn

**Files:**
- Create: `tests/test_integration.py`
- Create: `README.md`
- Create: `run.bat` (Script 1-click để khởi chạy nhanh trên Windows)

- [ ] **Step 1: Viết test tích hợp toàn diện (`test_integration.py`)**
  Kiểm tra luồng từ tạo bài viết trong Database -> sinh nội dung mock -> lên lịch -> xuất kết quả.
- [ ] **Step 2: Chạy toàn bộ test suite**
  Chạy: `pytest tests/ -v` xác nhận 100% tests PASS.
- [ ] **Step 3: Viết tài liệu `README.md` chi tiết bằng tiếng Việt**
  - Hướng dẫn cài đặt môi trường Python.
  - Hướng dẫn tạo Meta App, lấy Page ID và Long-Lived Page Access Token (kèm các quyền cần thiết: `pages_manage_posts`, `pages_read_engagement`).
  - Hướng dẫn lấy Google Gemini API Key miễn phí từ Google AI Studio.
  - Hướng dẫn chạy `streamlit run app.py` hoặc click file `run.bat`.
- [ ] **Step 4: Tạo file script `run.bat` tiện lợi cho người dùng Windows**

---

## Self-Review Checklist

1. **Spec coverage:** Kế hoạch đáp ứng đầy đủ: Gửi chủ đề -> AI tìm kiếm Google & tổng hợp -> Đính kèm ảnh người dùng -> Đăng ngay / Hẹn giờ (FB API & Local) -> Giao diện Web Streamlit -> SQLite lưu trữ.
2. **Step scan:** Mỗi bước đều rõ ràng, kèm lệnh test và file cụ thể.
3. **Type consistency:** Các tên hàm và class nhất quán giữa các task (`DatabaseManager`, `GeminiService`, `FacebookService`, `LocalSchedulerService`).
4. **Review Focus:** Đã bao gồm test xử lý lỗi token, validate thời gian hẹn giờ, xử lý lỗi file ảnh và fallback khi mất mạng.
5. **Proportion:** Kế hoạch súc tích, phân chia 6 tasks rõ ràng, bám sát phương pháp TDD.
