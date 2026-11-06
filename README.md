# 🚀 Facebook Fanpage Auto-Poster & AI Content Generator

Ứng dụng tự động hóa sáng tạo nội dung và đăng bài / lên lịch chuyên nghiệp cho Facebook Fanpage, được vận hành bởi mô hình **Google Gemini 2.5 Flash** tích hợp khả năng tìm kiếm web thời gian thực (**Google Search Grounding**) và giao tiếp qua **Meta Facebook Graph API**.

![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.43%2B-FF4B4B?logo=streamlit)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?logo=google)
![Meta Graph API](https://img.shields.io/badge/Meta%20Graph%20API-v20.0-1877F2?logo=facebook)
![Tests](https://img.shields.io/badge/Tests-87%20Passed%20(100%25)-success?logo=pytest)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📌 Mục Lục

1. [Tính Năng Nổi Bật](#-tính-năng-nổi-bật)
2. [Cấu Trúc Thư Mục Dự Án](#-cấu-trúc-thư-mục-dự-án)
3. [Yêu Cầu Hệ Thống & Cài Đặt](#-yêu-cầu-hệ-thống--cài-đặt)
4. [Hướng Dẫn Cấu Hình API Key & Token](#-hướng-dẫn-cấu-hình-api-key--token)
   - [4.1. Lấy Google Gemini API Key (Miễn phí)](#41-lấy-google-gemini-api-key-miễn-phí)
   - [4.2. Lấy Facebook Page ID & Long-Lived Page Access Token (Vĩnh viễn)](#42-lấy-facebook-page-id--long-lived-page-access-token-vĩnh-viễn)
5. [Khởi Chạy Ứng Dụng](#-khởi-chạy-ứng-dụng)
   - [Cách 1: Khởi chạy 1-click trên Windows (Khuyên dùng)](#cách-1-khởi-chạy-1-click-trên-windows-khuyên-dùng)
   - [Cách 2: Chạy thủ công qua dòng lệnh Terminal](#cách-2-chạy-thủ-công-qua-dòng-lệnh-terminal)
6. [Hướng Dẫn Sử Dụng Các Tab Giao Diện](#-hướng-dẫn-sử-dụng-các-tab-giao-diện)
   - [Tab 1: 📝 Tạo bài viết với AI](#tab-1--tạo-bài-viết-với-ai)
   - [Tab 2: 🚀 Đăng bài & Lên lịch](#tab-2--đăng-bài--lên-lịch)
   - [Tab 3: 📊 Lịch sử & Quản lý bài đăng](#tab-3--lịch-sử--quản-lý-bài-đăng)
   - [Tab 4: ⚙️ Cài đặt & Hướng dẫn Token](#tab-4-️-cài-đặt--hướng-dẫn-token)
7. [So Sánh Cơ Chế Hẹn Giờ (Native FB vs Local APScheduler)](#-so-sánh-cơ-chế-hẹn-giờ)
8. [Kiểm Thử Toàn Diện (Testing)](#-kiểm-thử-toàn-diện-testing)
9. [Bảo Mật & Lưu Ý](#-bảo-mật--lưu-ý)

---

## ✨ Tính Năng Nổi Bật

- ✍️ **Sáng tạo bài viết tự động với Google Gemini 2.5**: Tự động sinh nội dung bài viết theo cấu trúc chuẩn viral của mạng xã hội (Hook giật gân, Intro thu hút, Thân bài chia gạch đầu dòng trực quan với Emoji, Call To Action kích thích tương tác).
- 🌐 **Google Search Grounding (Tìm kiếm web thời gian thực)**: Tự động tra cứu Google Search trước khi viết để cập nhật số liệu, tin tức mới nhất vào bài viết, hiển thị rõ ràng danh sách nguồn link tham khảo.
- 🎭 **Tùy biến phong cách viết (Tone of Voice)**: Lựa chọn linh hoạt giữa *Chuyên nghiệp*, *Hài hước*, *Kể chuyện (Storytelling)*, *Tin tức nóng hổi*, *Tips & Tricks* hoặc nhập phong cách riêng tùy thích.
- #️⃣ **Tự động đề xuất Hashtags**: Tự động gợi ý 3–7 hashtag thịnh hành và liên quan mật thiết đến chủ đề.
- 🖼️ **Đính kèm hình ảnh chất lượng cao**: Hỗ trợ tải ảnh từ máy tính (PNG, JPG, JPEG, WEBP tối đa 10MB) kèm preview trực tiếp.
- 📱 **Xem trước bài đăng (Facebook Live Card Preview)**: Giả lập thẻ bài viết như hiển thị thực tế trên Facebook Fanpage (Tên trang, Avatar, Thời gian, Nội dung định dạng, Hình ảnh, Nút Thích/Bình luận/Chia sẻ).
- ⏰ **Đa dạng chế độ xuất bản**:
  1. **Đăng ngay lập tức**: Xuất bản trực tiếp lên Fanpage trong 1–2 giây.
  2. **Hẹn giờ qua Meta Facebook Graph API**: Lên lịch trên server của Meta (tối thiểu 10 phút, tối đa 75 ngày), hoàn toàn không cần bật máy tính.
  3. **Hẹn giờ Local máy tính (APScheduler)**: Lên lịch ngầm trên máy cá nhân, linh hoạt mọi thời điểm trong tương lai, tự động phục hồi lịch hẹn khi ứng dụng khởi động lại.
- 📊 **Quản lý lịch sử bài đăng & Phục hồi lỗi**: Lưu trữ toàn bộ bài viết trong SQLite nội bộ (`data/fanpage.db`), lọc theo trạng thái (`published`, `scheduled_fb`, `scheduled_local`, `draft`, `failed`, `cancelled`), xem link bài đăng trực tiếp trên Facebook, chép lại nội dung sang Tab 1 để chỉnh sửa hoặc thử lại các bài viết bị lỗi.
- 🔒 **Bảo mật tuyệt đối**: Khóa bí mật API Key và Page Token được mã hóa ẩn hiển thị trên giao diện và lưu trữ an toàn trong file `.env`.

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
DangbaiFanpage/
├── app.py                      # Ứng dụng Web Streamlit chính (Dashboard 4 Tabs)
├── run.bat                     # Script 1-click khởi chạy nhanh trên Windows
├── requirements.txt            # Danh sách thư viện Python phụ thuộc
├── .env.example                # File mẫu cấu hình biến môi trường
├── .env                        # File cấu hình bí mật thực tế (được tự động tạo)
├── data/                       # Thư mục lưu trữ dữ liệu
│   ├── fanpage.db              # Cơ sở dữ liệu SQLite lưu bài viết & lịch đăng
│   └── uploads/                # Thư mục chứa hình ảnh người dùng tải lên
├── src/                        # Mã nguồn các module dịch vụ chính
│   ├── __init__.py
│   ├── database.py             # DatabaseManager quản lý SQLite CRUD
│   ├── gemini_service.py       # GeminiService gọi Google Gemini AI & Google Search
│   ├── facebook_service.py     # FacebookService tương tác Meta Graph API
│   ├── scheduler_service.py    # LocalSchedulerService điều phối lịch hẹn ngầm APScheduler
│   └── ui_helpers.py           # Tiện ích UI (badge, format URL, validate ngày giờ, upload)
└── tests/                      # Bộ kiểm thử tự động toàn diện (87 tests)
    ├── __init__.py
    ├── test_database.py        # Kiểm thử CRUD database SQLite
    ├── test_gemini_service.py  # Kiểm thử Gemini AI & Grounding
    ├── test_facebook_service.py# Kiểm thử Facebook Graph API & mã lỗi Token
    ├── test_scheduler_service.py# Kiểm thử APScheduler & khôi phục bài viết
    ├── test_ui_helpers.py      # Kiểm thử các hàm tiện ích UI
    ├── test_app_smoke.py       # Smoke test Streamlit AppTest
    └── test_integration.py     # Kiểm thử tích hợp toàn bộ luồng E2E
```

---

## 💻 Yêu Cầu Hệ Thống & Cài Đặt

### 1. Yêu cầu tiên quyết
- **Hệ điều hành**: Windows 10/11, macOS, hoặc Linux.
- **Python**: Phiên bản **3.10 trở lên** (Đã kiểm thử tối ưu trên Python 3.12).
- Kết nối Internet ổn định.

### 2. Các bước cài đặt chi tiết

**Bước 1: Mở Terminal / PowerShell và di chuyển vào thư mục dự án:**
```bash
cd D:/1.Project/DangbaiFanpage
```

**Bước 2: Tạo môi trường ảo Python (Virtual Environment):**
```bash
python -m venv venv
```

**Bước 3: Kích hoạt môi trường ảo:**
- **Trên Windows (PowerShell / Command Prompt):**
  ```powershell
  venv\Scripts\activate
  ```
- **Trên macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

**Bước 4: Cài đặt toàn bộ thư viện cần thiết:**
```bash
pip install -r requirements.txt
```

---

## 🔑 Hướng Dẫn Cấu Hình API Key & Token

### 4.1. Lấy Google Gemini API Key (Miễn phí)

1. Truy cập vào trang quản lý của Google AI Studio: [https://aistudio.google.com/](https://aistudio.google.com/).
2. Đăng nhập bằng tài khoản Google cá nhân.
3. Nhấn vào nút **"Get API Key"** ở thanh điều hướng bên trái.
4. Chọn **"Create API Key in new project"** (hoặc chọn project Google Cloud sẵn có).
5. Sao chép chuỗi ký tự API Key vừa tạo (có dạng `AIzaSy...`).

---

### 4.2. Lấy Facebook Page ID & Long-Lived Page Access Token (Vĩnh viễn)

> [!IMPORTANT]
> Để Fanpage có thể đăng bài tự động mà không bao giờ bị hết hạn token giữa chừng, bạn cần lấy **Page Access Token vĩnh viễn (Never Expire)** theo 6 bước chuẩn Meta dưới đây.

#### Bước 1: Tạo Meta Developer App
1. Truy cập [Meta for Developers](https://developers.facebook.com/) và đăng nhập tài khoản Facebook quản trị Fanpage.
2. Nhấn vào **My Apps** (Ứng dụng của tôi) -> **Create App** (Tạo ứng dụng).
3. Chọn loại ứng dụng: **Other** (Khác) hoặc **Business** (Doanh nghiệp) -> Nhấn **Next**.
4. Chọn loại là **Business** -> Điền tên ứng dụng (ví dụ: `Fanpage Auto-Poster`) -> Nhấn **Create App**.

#### Bước 2: Lấy Fanpage ID
1. Mở trang Fanpage của bạn trên Facebook bằng trình duyệt máy tính.
2. Vào mục **Giới thiệu** (About) -> kéo xuống phần **Tính minh bạch của Trang** (Page Transparency) -> Sao chép dãy số **ID Trang** (Page ID, ví dụ: `102938475610293`).
3. Hoặc vào Cài đặt Trang -> xem trên URL thanh địa chỉ.

#### Bước 3: Mở Graph API Explorer & Cấp quyền
1. Truy cập công cụ [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Tại mục **Meta App**, chọn đúng ứng dụng bạn vừa tạo ở Bước 1.
3. Tại ô **User or Page**, chọn **User Token**.
4. Tại mục **Permissions** (Quyền), bấm **Add a Permission** và tìm chọn chính xác 3 quyền sau:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
5. Nhấn nút **Generate Access Token** màu xanh -> Một cửa sổ Facebook hiện ra, bạn nhấn **Tiếp tục dưới tên...** và tích chọn đúng Fanpage muốn quản lý -> Nhấn **Lưu** -> Nhấn **Xong**.

#### Bước 4: Chuyển đổi thành Long-Lived User Access Token (Hạn 60 ngày)
Token ở Bước 3 là User Token ngắn hạn (chỉ dùng được khoảng 1–2 giờ). Ta chuyển nó thành token dài hạn 60 ngày:
1. Vào mục **App Settings** (Cài đặt ứng dụng) -> **Basic** (Thông tin cơ bản) trong trang quản trị Meta App để lấy:
   - **App ID** (ID ứng dụng)
   - **App Secret** (Khóa bí mật của ứng dụng)
2. Mở tab mới trên trình duyệt hoặc gửi request GET đến URL sau (thay thế các giá trị trong ngoặc nhọn `{...}`):
```http
https://graph.facebook.com/v20.0/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={USER_ACCESS_TOKEN_Ở_BƯỚC_3}
```
3. Kết quả trả về JSON chứa trường `access_token` mới — đây là **Long-Lived User Access Token (hạn 60 ngày)**.

#### Bước 5: Lấy Long-Lived Page Access Token Vĩnh Viễn (Never Expire)
Từ Long-Lived User Access Token, bạn gửi request để trích xuất Page Token của Fanpage:
1. Gửi request GET tới endpoint:
```http
https://graph.facebook.com/v20.0/{PAGE_ID}?fields=access_token&access_token={LONG_LIVED_USER_TOKEN_Ở_BƯỚC_4}
```
2. Phản hồi JSON trả về có dạng:
```json
{
  "access_token": "EAAX...chuỗi_page_token_dài...",
  "id": "102938475610293"
}
```
3. Chuỗi `access_token` ở đây chính là **Long-Lived Page Access Token VĨNH VIỄN**!

#### Bước 6: Kiểm tra xác nhận Token bằng Access Token Debugger
1. Truy cập [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/).
2. Dán chuỗi Page Access Token vừa lấy được vào và bấm **Debug**.
3. Kiểm tra các dòng thông tin sau:
   - **Type**: `Page`
   - **Expires**: `Never` (Không bao giờ hết hạn)
   - **Scopes**: Có đủ `pages_manage_posts` và `pages_read_engagement`.

---

### 4.3. Cấu hình file `.env`

Bạn có thể cấu hình trực tiếp từ giao diện **Tab 4 (Cài đặt)** trên ứng dụng web, hoặc tạo file `.env` trong thư mục gốc dự án theo mẫu sau:

```ini
# Google Gemini API Key
GEMINI_API_KEY=AIzaSyBxxxxxx...

# Facebook Fanpage Configuration
FB_PAGE_ID=102938475610293
FB_PAGE_ACCESS_TOKEN=EAABxxxxxx...

# Database Configuration (Mặc định)
DB_PATH=data/fanpage.db
```

---

## 🚀 Khởi Chạy Ứng Dụng

### Cách 1: Khởi chạy 1-click trên Windows (Khuyên dùng)
Chỉ cần nhấp đúp chuột vào file:
```
run.bat
```
Script sẽ tự động:
1. Phát hiện phiên bản Python trên máy tính.
2. Kích hoạt môi trường ảo `venv` (nếu có).
3. Tự động kiểm tra và cài đặt các thư viện cần thiết.
4. Mở trình duyệt web truy cập thẳng vào giao diện: `http://localhost:8501`.

### Cách 2: Chạy thủ công qua dòng lệnh Terminal
```bash
# Kích hoạt môi trường ảo
venv\Scripts\activate

# Khởi chạy Streamlit
streamlit run app.py
```

---

## 🖥️ Hướng Dẫn Sử Dụng Các Tab Giao Diện

### Tab 1: 📝 Tạo bài viết với AI
1. **Nhập chủ đề**: Nhập từ khóa, tiêu đề tin tức, hoặc liên kết bài viết bạn quan tâm.
2. **Chọn Tone giọng**: Chọn phong cách phù hợp (Chuyên nghiệp, Hài hước, Storytelling, Tin tức...).
3. **Tùy chọn nâng cao**:
   - Tích chọn **🌐 Google Search Grounding**: AI tự động tìm kiếm thông tin mới nhất trên Google.
   - Tích chọn **Đề xuất Hashtags**: AI tự thêm cụm hashtags cuối bài.
4. **Nhấn "✨ Tìm kiếm & Viết bài ngay"**: Quá trình diễn ra trong vài giây, bài viết hoàn thiện hiển thị kèm danh sách nguồn trích dẫn từ Google.
5. **Đính kèm ảnh minh họa**: Tải ảnh từ máy tính (PNG, JPG, WEBP).
6. **Chỉnh sửa & Lưu nháp**: Người dùng có thể sửa đổi nội dung trực tiếp tại khung soạn thảo, sau đó bấm **"💾 Lưu làm Bản nháp"** hoặc chuyển sang Tab 2.

### Tab 2: 🚀 Đăng bài & Lên lịch
1. **Facebook Live Preview**: Thẻ mô phỏng bài đăng hiển thị trực quan giống 100% giao diện thực tế trên Facebook.
2. **Lựa chọn 1 trong 3 hình thức xuất bản**:
   - **Đăng ngay lên Fanpage**: Bấm **"🚀 Xuất bản ngay bây giờ"**, bài đăng được đẩy lên Facebook trong vài giây kèm đường link truy cập trực tiếp.
   - **Hẹn giờ qua Facebook Graph API (Server Meta)**: Chọn ngày giờ mong muốn (cách hiện tại từ 10 phút đến 75 ngày). Meta tự động đăng bài theo lịch mà bạn không cần mở máy tính.
   - **Hẹn giờ Local máy tính (APScheduler)**: Chọn ngày giờ bất kỳ trong tương lai. Máy tính cá nhân sẽ tự động đăng bài khi đến giờ hẹn.

### Tab 3: 📊 Lịch sử & Quản lý bài đăng
1. **Thẻ thống kê số liệu**: Tổng số bài viết, số bài đã đăng, đang lên lịch, bản nháp, và bài bị lỗi.
2. **Bộ lọc trạng thái**: Lọc nhanh các bài viết theo tiêu chí mong muốn.
3. **Danh sách chi tiết**:
   - Hiển thị ID, chủ đề, huy hiệu trạng thái (màu sắc trực quan), ảnh thu nhỏ, thời gian đăng.
   - Link Facebook bấm vào để xem bài viết thực tế trên mạng xã hội.
4. **Hành động quản lý**:
   - **🔁 Đăng ngay lại**: Dành cho bài viết bị lỗi hoặc bản nháp cần đăng gấp.
   - **📝 Chép vào Tab 1 để sửa**: Sao chép nội dung bài viết về Tab 1 để biên tập lại.
   - **🚫 Hủy lịch Local**: Dừng tiến trình hẹn giờ ngầm APScheduler.
   - **🗑️ Xóa bài viết**: Xóa bản ghi khỏi cơ sở dữ liệu.

### Tab 4: ⚙️ Cài đặt & Hướng dẫn Token
- Nhập và lưu `GEMINI_API_KEY`, `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN` an toàn.
- **Nút "Kiểm tra Fanpage"**: Gọi hàm `verify_token()` để kiểm tra tình trạng token, quyền đăng bài (`can_post`), tên Fanpage và avatar thực tế.
- **Nút "Kiểm tra Gemini AI"**: Gọi kiểm tra thử nghiệm khả năng kết nối Google AI.
- Tích hợp sẵn tài liệu hướng dẫn từng bước lấy token hiển thị trực quan ngay trong ứng dụng.

---

## ⚖️ So Sánh Cơ Chế Hẹn Giờ

| Tiêu Chí So Sánh | ⏰ Hẹn giờ Meta Facebook Graph API | 💻 Hẹn giờ Local máy tính (APScheduler) |
| :--- | :--- | :--- |
| **Nơi lưu trữ lịch đăng** | Máy chủ Meta Facebook | Cơ sở dữ liệu SQLite cục bộ (`fanpage.db`) |
| **Yêu cầu bật máy tính** | ❌ **Không cần** (Sau khi lên lịch, tắt máy Meta vẫn tự đăng) | ✔️ **Cần duy trì máy tính / server đang bật** |
| **Khoảng thời gian cho phép** | Giới hạn từ **10 phút** đến **75 ngày** | **Không giới hạn** (Bất kỳ lúc nào trong tương lai) |
| **Hỗ trợ bài viết đính kèm ảnh** | Có hỗ trợ | Có hỗ trợ |
| **Khả năng tự phục hồi khi khởi động lại** | Tự động hoàn toàn trên cloud của Facebook | Tự động đọc lại các bài `scheduled_local` từ SQLite khi khởi động ứng dụng |
| **Trường hợp khuyên dùng** | Lên lịch dài hạn, không có server cắm 24/7 | Hẹn giờ nhanh vài phút tới hoặc chạy trên máy chủ nội bộ |

---

## 🧪 Kiểm Thử Toàn Diện (Testing)

Dự án áp dụng phương pháp phát triển kiểm thử nghiêm ngặt (**Test-Driven Development - TDD**) với **87 test cases** bao phủ toàn bộ các module và kịch bản người dùng:

```bash
# Chạy toàn bộ test suite
pytest tests/ -v
```

Kết quả kiểm thử đạt **100% PASS**:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\1.Project\DangbaiFanpage
plugins: anyio-4.15.1
collected 87 items

tests/test_app_smoke.py ......................... PASSED [  6%]
tests/test_database.py .......................... PASSED [ 14%]
tests/test_facebook_service.py .................. PASSED [ 50%]
tests/test_gemini_service.py .................... PASSED [ 56%]
tests/test_integration.py ....................... PASSED [ 66%]
tests/test_scheduler_service.py ................. PASSED [ 89%]
tests/test_ui_helpers.py ........................ PASSED [100%]

============================= 87 passed in 11.53s =============================
```

---

## 🛡️ Bảo Mật & Lưu Ý

1. **Không bao giờ commit file `.env` lên GitHub hoặc kho mã nguồn công khai.** File `.gitignore` của dự án đã được thiết lập để loại trừ `.env`, dữ liệu `data/*.db` và ảnh `data/uploads/`.
2. **Quyền hạn Fanpage:** Người tạo token phải có vai trò **Quản trị viên (Admin)** hoặc **Người tạo nội dung (Editor)** của Fanpage để token có đủ quyền `pages_manage_posts`.
3. **Mã lỗi 190 Facebook:** Nếu hệ thống báo lỗi Token (Code 190), nghĩa là bạn vừa đổi mật khẩu Facebook cá nhân hoặc quyền của ứng dụng bị thu hồi. Hãy thực hiện lại Bước 4 & 5 ở mục [4.2](#42-lấy-facebook-page-id--long-lived-page-access-token-vĩnh-viễn) để cập nhật Page Token mới.

---

## 📄 Bản Quyền & Giấy Phép

Dự án được phân phối dưới giấy phép mã nguồn mở **MIT License**. Mọi cá nhân và doanh nghiệp đều có quyền sử dụng, sửa đổi và phân phối phục vụ mục đích học tập hoặc thương mại.
