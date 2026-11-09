# Hướng Dẫn Chi Tiết Triển Khai Lên Render.com (Render Deployment Guide)

Tài liệu này hướng dẫn bạn cách đưa ứng dụng **Facebook Fanpage Auto-Poster** lên nền tảng đám mây **Render.com** (hoàn toàn miễn phí trên gói Free Tier), tạo địa chỉ Web công khai để bạn có thể truy cập và đăng bài từ mọi thiết bị (máy tính, điện thoại, máy tính bảng).

---

## 📋 Mục Lục
1. [Điều kiện chuẩn bị](#1-điều-kiện-chuẩn-bị)
2. [Bước 1: Đẩy mã nguồn lên GitHub](#bước-1-đẩy-mã-nguồn-lên-github)
3. [Bước 2: Tạo dịch vụ Web trên Render.com](#bước-2-tạo-dịch-vụ-web-trên-rendercom)
4. [Bước 3: Cấu hình Biến Môi Trường (Environment Variables)](#bước-3-cấu-hình-biến-môi-trường-environment-variables)
5. [Bước 4: Kiểm tra & Mở khóa Ứng dụng](#bước-4-kiểm-tra--mở-khóa-ứng-dụng)
6. [Bước 5: Thiết lập UptimeRobot chống ngủ máy chủ (Tùy chọn)](#bước-5-thiết-lập-uptimerobot-chống-ngủ-máy-chủ-tùy-chọn)
7. [Các lưu ý quan trọng khi dùng Render Free Tier](#các-lưu-ý-quan-trọng-khi-dùng-render-free-tier)

---

## 1. Điều kiện chuẩn bị
1. **Tài khoản GitHub**: Đăng ký miễn phí tại [github.com](https://github.com/).
2. **Tài khoản Render**: Đăng ký miễn phí tại [render.com](https://render.com/) (Nên chọn **Sign in with GitHub** để tự động liên kết).

---

## Bước 1: Đẩy mã nguồn lên GitHub

1. Mở PowerShell hoặc Terminal tại thư mục dự án `DangbaiFanpage`.
2. Khởi tạo Git và liên kết với kho lưu trữ mới trên GitHub:
   ```bash
   # Nếu chưa liên kết remote origin:
   git remote add origin https://github.com/<tai-khoan-cua-ban>/<ten-repo>.git
   git branch -M main
   git push -u origin main
   ```
   *(Lưu ý: File `.env` chứa mật khẩu đã được tự động bỏ qua trong `.gitignore` nên tuyệt đối an toàn, không bị lộ lên GitHub).*

---

## Bước 2: Tạo dịch vụ Web trên Render.com

### Cách A: Triển khai tự động bằng Blueprint (Khuyên Dùng - Nhanh nhất)
1. Đăng nhập vào trang quản trị Render: [dashboard.render.com](https://dashboard.render.com/).
2. Nhấp vào nút **New +** ở góc trên cùng bên phải -> Chọn **Blueprint**.
3. Chọn kho lưu trữ GitHub của dự án `DangbaiFanpage`.
4. Render sẽ tự động đọc file [`render.yaml`](../render.yaml) đã chuẩn bị sẵn:
   - Tên dịch vụ: `fanpage-autoposter`
   - Vùng: `Singapore` (độ trễ thấp nhất về Việt Nam)
   - Runtime: `Python 3.12`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false`
5. Nhấp **Apply** để khởi tạo dịch vụ.

### Cách B: Tạo thủ công Web Service (Manual)
1. Nhấp **New +** -> Chọn **Web Service**.
2. Chọn repo GitHub dự án của bạn.
3. Điền các thông số:
   - **Name**: `fanpage-autoposter` (hoặc tên bạn thích).
   - **Region**: `Singapore`.
   - **Branch**: `main`.
   - **Runtime**: `Python 3`.
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**:
     ```bash
     streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
     ```
   - **Instance Type**: `Free`.

---

## Bước 3: Cấu hình Biến Môi Trường (Environment Variables)

Tại trang quản lý dịch vụ trên Render:
1. Nhấp vào menu **Environment** ở thanh bên trái.
2. Thêm các biến sau (nhấp **Add Environment Variable**):

| Key (Tên biến) | Value (Giá trị ví dụ) | Mô tả |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.0` | Chỉ định Render dùng Python 3.12 |
| `GEMINI_API_KEY` | `AIzaSy...` | Khóa Google Gemini API của bạn |
| `OPENROUTER_API_KEY`| `sk-or-v1-...` | Khóa OpenRouter (tùy chọn) |
| `FB_PAGE_ID` | `619960427857965` | ID Fanpage của bạn |
| `FB_PAGE_ACCESS_TOKEN` | `EAAB...` | Token Fanpage vĩnh viễn (Never Expire) |
| `FB_APP_ID` | `3711376692339694` | App ID Meta Developer |
| `FB_APP_SECRET` | `d41d8cd98f00b204...`| App Secret của Meta Developer |
| `APP_PASSWORD` | `MatKhauCuaBan123` | **Mật khẩu bảo vệ app khỏi người lạ** |

3. Nhấp **Save Changes**. Render sẽ tự động build lại ứng dụng trong 1 - 2 phút.

---

## Bước 4: Kiểm tra & Mở khóa Ứng dụng

1. Khi Render báo trạng thái **Live** (màu xanh lá), nhấp vào đường dẫn công khai ở đầu trang:
   `https://fanpage-autoposter-xxxx.onrender.com`
2. Màn hình bảo mật **"🔒 Facebook Fanpage Auto-Poster"** sẽ hiện ra yêu cầu nhập mật khẩu.
3. Nhập mật khẩu bạn đã cài đặt ở biến `APP_PASSWORD` và nhấn **🔓 Mở khóa bảng điều khiển**.
4. Toàn bộ bảng điều khiển 5 Tabs sẽ hiển thị đầy đủ, sẵn sàng để bạn tạo bài và xuất bản lên Fanpage!

---

## Bước 5: Thiết lập UptimeRobot chống ngủ máy chủ (Tùy chọn)

Trên gói **Render Free Tier**, sau 15 phút không có người truy cập, máy chủ sẽ tạm thời rơi vào trạng thái ngủ (Sleep) để tiết kiệm tài nguyên. Lần truy cập tiếp theo sẽ mất khoảng 30-50 giây để khởi động lại.

Để máy chủ luôn thức và chạy mượt mà 24/7:
1. Đăng ký tài khoản miễn phí tại [uptimerobot.com](https://uptimerobot.com/).
2. Nhấp **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Fanpage Auto-Poster Render`
   - **URL (or IP)**: Dán link Render của bạn (ví dụ: `https://ten-app.onrender.com`)
   - **Monitoring Interval**: `5 minutes` (mỗi 5 phút ping 1 lần)
3. Nhấp **Create Monitor**. Từ giờ UptimeRobot sẽ tự động gửi tín hiệu giữ cho app Render của bạn luôn thức!

---

## Các lưu ý quan trọng khi dùng Render Free Tier

1. **Khuyên dùng Hẹn giờ Meta API**:
   - Khi lên lịch đăng bài cho các ngày tới, hãy ưu tiên chọn chế độ **"⏰ Hẹn giờ qua Facebook Graph API (Server Meta)"**. Máy chủ Facebook của Meta sẽ tự lưu và xuất bản đúng giờ mà hoàn toàn không phụ thuộc vào máy tính hay container Render.
2. **Tính chất đĩa tạm (Ephemeral Disk) trên Free Tier**:
   - Trên Render Free Tier, các tệp ghi nội bộ (như file `.db` SQLite và thư mục ảnh tải lên `data/uploads/`) sẽ bị reset về trạng thái ban đầu nếu bạn kích hoạt Deploy lại (Redeploy).
   - Vì vậy, các thông tin quan trọng nhất (API Keys, Page ID, Token) nên luôn được lưu trong mục **Environment Variables** của Render Dashboard như hướng dẫn ở Bước 3.
