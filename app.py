"""Facebook Fanpage Auto-Poster - Streamlit Dashboard.

An automated Facebook Fanpage publishing and scheduling application powered by
Google Gemini 2.5 with Google Search Grounding and Meta Facebook Graph API.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, time as dtime
from typing import Any

import streamlit as st

from src.database import DatabaseManager
from src.facebook_service import (
    FacebookAPIError,
    FacebookPermissionError,
    FacebookService,
    FacebookTokenError,
)
from src.gemini_service import GeminiService
from src.openrouter_service import OpenRouterService
from src.scheduler_service import LocalSchedulerService
from src.ui_helpers import (
    format_facebook_url,
    get_status_badge,
    load_env_config,
    mask_token,
    render_status_badge_html,
    save_env_config,
    save_uploaded_file,
    validate_schedule_datetime_fb,
    validate_schedule_datetime_local,
)

logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Facebook Fanpage Auto-Poster",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished Facebook-like styling
st.markdown(
    """
    <style>
    /* Global enhancements */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1877F2;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #65676B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    /* Facebook Card Preview */
    .fb-card-wrapper {
        background-color: #ffffff;
        border: 1px solid #ced0d4;
        border-radius: 10px;
        padding: 16px;
        margin: 15px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    .fb-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }
    .fb-avatar {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background-color: #1877F2;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 20px;
    }
    .fb-name {
        font-weight: 600;
        font-size: 15px;
        color: #050505;
        line-height: 1.2;
    }
    .fb-time {
        font-size: 12px;
        color: #65676B;
    }
    .fb-content {
        font-size: 14.5px;
        color: #050505;
        white-space: pre-wrap;
        line-height: 1.5;
        margin-bottom: 12px;
    }
    .fb-footer {
        display: flex;
        justify-content: space-around;
        border-top: 1px solid #e4e6eb;
        padding-top: 10px;
        margin-top: 12px;
        color: #65676B;
        font-size: 13.5px;
        font-weight: 600;
    }
    /* Stat Metric Box */
    .stat-card {
        background-color: #f0f2f5;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
        border: 1px solid #e4e6eb;
    }
    .stat-number {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1877F2;
    }
    .stat-label {
        font-size: 0.88rem;
        color: #65676B;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_database_manager() -> DatabaseManager:
    """Singleton provider for DatabaseManager."""
    db_path = os.environ.get("DB_PATH", "data/fanpage.db")
    return DatabaseManager(db_path=db_path)


@st.cache_resource
def get_scheduler_service() -> LocalSchedulerService:
    """Singleton provider for LocalSchedulerService with APScheduler background worker."""
    db = get_database_manager()

    def get_fb_service() -> FacebookService:
        config = load_env_config()
        page_id = config.get("FB_PAGE_ID")
        access_token = config.get("FB_PAGE_ACCESS_TOKEN")
        if not page_id or not access_token:
            raise ValueError(
                "Chưa cấu hình Facebook Page ID hoặc Page Access Token trong .env."
            )
        return FacebookService(page_id=page_id, access_token=access_token)

    service = LocalSchedulerService(db=db, fb_service_provider=get_fb_service)
    service.start()
    try:
        service.load_and_reschedule_pending_jobs(execute_overdue=False)
    except Exception as exc:
        logger.warning(f"Error rescheduling pending jobs: {exc}")
    return service


# Initialize core services
db_manager = get_database_manager()
scheduler_service = get_scheduler_service()

# Initialize session state variables
if "post_topic" not in st.session_state:
    st.session_state.post_topic = ""
if "topic_input_area" not in st.session_state:
    st.session_state.topic_input_area = ""
if "post_content" not in st.session_state:
    st.session_state.post_content = ""
if "content_editor_area" not in st.session_state:
    st.session_state.content_editor_area = ""
if "post_image_path" not in st.session_state:
    st.session_state.post_image_path = None
if "last_uploaded_file_id" not in st.session_state:
    st.session_state.last_uploaded_file_id = None
if "post_sources" not in st.session_state:
    st.session_state.post_sources = []
if "fb_page_name" not in st.session_state:
    st.session_state.fb_page_name = "Facebook Fanpage"

# Load current credentials from .env
env_config = load_env_config()


# Sidebar Navigation & System Status
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/b/b9/2023_Facebook_icon.svg",
        width=50,
    )
    st.markdown("### **Fanpage Auto-Poster**")
    st.caption("Phiên bản v1.0.0 · AI Google Gemini 2.5")

    st.markdown("---")
    st.markdown("#### **Trạng thái hệ thống**")

    # Gemini Status Indicator
    has_gemini = bool(env_config.get("GEMINI_API_KEY"))
    if has_gemini:
        st.success("🟢 Gemini AI: Đã kết nối", icon="✅")
    else:
        st.warning("🟡 Gemini AI: Chưa có Key", icon="⚠️")

    # Facebook Status Indicator
    has_fb = bool(env_config.get("FB_PAGE_ID") and env_config.get("FB_PAGE_ACCESS_TOKEN"))
    if has_fb:
        st.success("🟢 Fanpage: Đã cấu hình", icon="✅")
    else:
        st.warning("🟡 Fanpage: Chưa cấu hình", icon="⚠️")

    # Scheduler Status Indicator
    if scheduler_service.is_running:
        st.info("🟢 Local Scheduler: Đang chạy ngầm", icon="💻")
    else:
        st.error("🔴 Local Scheduler: Tạm dừng", icon="🛑")

    st.markdown("---")
    st.caption("Hệ thống tự động hóa đăng bài chuyên nghiệp.")


# App Header
st.markdown('<div class="main-title">🚀 Facebook Fanpage Auto-Poster</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Sáng tạo nội dung với Google Gemini 2.5 Grounding, tải ảnh đính kèm và đăng bài / lên lịch tự động.</div>',
    unsafe_allow_html=True,
)

# Main Application Tabs
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📝 Tạo bài viết với AI",
        "🚀 Đăng bài & Lên lịch",
        "📊 Lịch sử & Quản lý bài đăng",
        "⚙️ Cài đặt & Hướng dẫn Token",
    ]
)


# ==============================================================================
# TAB 1: TẠO BÀI VIẾT VỚI AI
# ==============================================================================
with tab1:
    st.subheader("📝 Tạo nội dung bài viết với Google Gemini AI")
    st.caption(
        "Nhập chủ đề hoặc từ khóa để Gemini 2.5 tìm kiếm thông tin thời gian thực qua Google Search và soạn bài đăng hoàn chỉnh."
    )

    col1, col2 = st.columns([3, 2], gap="medium")

    with col1:
        topic_input = st.text_area(
            "Chủ đề / Từ khóa / Ý tưởng bài viết:",
            key="topic_input_area",
            placeholder="Ví dụ: Xu hướng trí tuệ nhân tạo Agentic Coding trong năm 2026 và tác động đến lập trình viên",
            height=90,
            help="Nhập chủ đề bạn muốn Fanpage đăng tải. Càng chi tiết, bài viết sẽ càng chất lượng.",
        )
        st.session_state.post_topic = topic_input

        # AI Provider & Model Selection
        provider_col1, provider_col2 = st.columns([1, 1])
        with provider_col1:
            ai_provider = st.radio(
                "🤖 Nguồn AI tạo nội dung:",
                ["Google Gemini", "OpenRouter"],
                horizontal=True,
                help="Chọn giữa Google Gemini hoặc OpenRouter (hỗ trợ nhiều model miễn phí).",
            )

        with provider_col2:
            if ai_provider == "OpenRouter":
                cached_or = [m["id"] for m in st.session_state.get("openrouter_models_cache", [])]
                openrouter_models = [
                    "deepseek/deepseek-chat:free",
                    "deepseek/deepseek-r1:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "qwen/qwen-2.5-72b-instruct:free",
                    "google/gemini-2.0-flash-exp:free",
                ]
                for m_id in cached_or:
                    if m_id not in openrouter_models:
                        openrouter_models.append(m_id)
                openrouter_models.append("Tùy chỉnh model ID...")

                chosen_or_model = st.selectbox("Chọn Model OpenRouter:", openrouter_models)
                if chosen_or_model == "Tùy chỉnh model ID...":
                    selected_ai_model = st.text_input("Nhập Model ID OpenRouter:", value="deepseek/deepseek-chat:free")
                else:
                    selected_ai_model = chosen_or_model
            else:
                gemini_models = [
                    "gemini-3.5-flash-lite",
                    "gemini-3.8-flash",
                    "gemini-3.1-flash-lite",
                ]
                selected_ai_model = st.selectbox("Chọn Model Gemini:", gemini_models)

        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            tone_options = [
                "Chuyên nghiệp, hấp dẫn",
                "Hài hước, hóm hỉnh",
                "Kể chuyện, sâu sắc (Storytelling)",
                "Tin tức, thời sự nóng hổi",
                "Chia sẻ kinh nghiệm, Tips & Tricks",
                "Tùy chỉnh...",
            ]
            selected_tone = st.selectbox("Phong cách giọng văn (Tone):", tone_options)
            if selected_tone == "Tùy chỉnh...":
                tone_text = st.text_input("Nhập giọng văn tùy chỉnh:", value="Nhiệt huyết, truyền cảm hứng")
            else:
                tone_text = selected_tone

        with sub_col2:
            include_hashtags = st.checkbox(
                "Đề xuất Hashtags phù hợp ở cuối bài",
                value=True,
                help="AI sẽ tạo các hashtag liên quan trực tiếp đến chủ đề bài viết.",
            )
            use_search = st.toggle(
                "🌐 Tìm kiếm Web thời gian thực (Web Search)",
                value=True,
                help="Bật để AI tìm kiếm thông tin mới nhất trên mạng trước khi viết bài.",
            )

        auto_fallback = st.checkbox(
            "🛡️ Tự động chuyển đổi dự phòng (Auto-fallback) sang nguồn AI khác nếu nguồn chính gặp lỗi/hết quota",
            value=True,
        )

        generate_btn = st.button("✨ Tìm kiếm & Viết bài ngay", type="primary", use_container_width=True)

        if generate_btn:
            if not topic_input.strip():
                st.warning("⚠️ Vui lòng nhập chủ đề trước khi yêu cầu viết bài.")
            else:
                gemini_key = env_config.get("GEMINI_API_KEY", "").strip()
                openrouter_key = env_config.get("OPENROUTER_API_KEY", "").strip()

                active_key = openrouter_key if ai_provider == "OpenRouter" else gemini_key
                active_key_name = "OPENROUTER_API_KEY" if ai_provider == "OpenRouter" else "GEMINI_API_KEY"

                if not active_key:
                    st.error(f"❌ Chưa tìm thấy {active_key_name}! Vui lòng chuyển sang Tab ⚙️ Cài đặt để cấu hình API Key.")
                else:
                    success = False
                    result = None
                    primary_error = None

                    with st.spinner(f"🔍 Đang gọi {ai_provider} ({selected_ai_model}) sáng tạo nội dung bài viết..."):
                        try:
                            if ai_provider == "OpenRouter":
                                or_svc = OpenRouterService(api_key=openrouter_key, model=selected_ai_model)
                                result = or_svc.generate_fanpage_post(
                                    topic=topic_input,
                                    tone=tone_text,
                                    include_hashtags=include_hashtags,
                                    use_search=use_search,
                                )
                            else:
                                gemini_svc = GeminiService(api_key=gemini_key, model=selected_ai_model)
                                result = gemini_svc.generate_fanpage_post(
                                    topic=topic_input,
                                    tone=tone_text,
                                    include_hashtags=include_hashtags,
                                    use_search=use_search,
                                )
                            success = True
                        except Exception as exc:
                            primary_error = exc

                    # Attempt auto-fallback if primary failed and auto_fallback enabled
                    if not success and auto_fallback:
                        fallback_provider = "Google Gemini" if ai_provider == "OpenRouter" else "OpenRouter"
                        fallback_key = gemini_key if fallback_provider == "Google Gemini" else openrouter_key

                        if fallback_key:
                            st.warning(f"⚠️ {ai_provider} gặp sự cố: {primary_error}. Đang tự động chuyển sang {fallback_provider}...")
                            with st.spinner(f"🔄 Đang kích hoạt dự phòng qua {fallback_provider}..."):
                                try:
                                    if fallback_provider == "OpenRouter":
                                        or_fallback_svc = OpenRouterService(api_key=openrouter_key)
                                        result = or_fallback_svc.generate_fanpage_post(
                                            topic=topic_input,
                                            tone=tone_text,
                                            include_hashtags=include_hashtags,
                                            use_search=use_search,
                                        )
                                    else:
                                        gemini_fallback_svc = GeminiService(api_key=gemini_key)
                                        result = gemini_fallback_svc.generate_fanpage_post(
                                            topic=topic_input,
                                            tone=tone_text,
                                            include_hashtags=include_hashtags,
                                            use_search=use_search,
                                        )
                                    success = True
                                    st.info(f"✅ Đã tạo nội dung thành công thông qua nguồn dự phòng: **{fallback_provider}**!")
                                except Exception as fb_exc:
                                    st.error(f"❌ Nguồn dự phòng {fallback_provider} cũng gặp lỗi: {fb_exc}")
                        else:
                            st.error(f"❌ Lỗi từ {ai_provider}: {primary_error}")
                    elif not success:
                        st.error(f"❌ Lỗi từ {ai_provider}: {primary_error}")

                    if success and result:
                        st.session_state.post_topic = topic_input
                        st.session_state.post_content = result.get("content", "")
                        st.session_state.content_editor_area = st.session_state.post_content
                        st.session_state.post_sources = result.get("sources", [])
                        st.success(f"🎉 Bài viết đã được tạo thành công bởi {ai_provider}! Bạn có thể chỉnh sửa ở khung bên dưới.")

        # Display Search sources if available
        if st.session_state.post_sources:
            with st.expander(f"🌐 Nguồn tham khảo từ Web Search ({len(st.session_state.post_sources)})"):
                for src in st.session_state.post_sources:
                    st.markdown(f"- [{src}]({src})")

        st.markdown("---")
        st.markdown("#### **Soạn thảo & Chỉnh sửa nội dung trước khi đăng**")
        edited_content = st.text_area(
            "Nội dung bài viết (Hỗ trợ Markdown / Emoji):",
            key="content_editor_area",
            height=280,
            placeholder="Nội dung bài viết sẽ xuất hiện ở đây sau khi AI viết, hoặc bạn có thể tự nhập trực tiếp...",
        )
        # Update session state content
        st.session_state.post_content = edited_content

        action_col1, action_col2 = st.columns(2)
        with action_col1:
            if st.button("💾 Lưu làm Bản nháp (Draft)", use_container_width=True):
                if not st.session_state.post_content.strip():
                    st.warning("⚠️ Nội dung bài viết đang trống, không thể lưu.")
                else:
                    draft_id = db_manager.save_post(
                        topic=st.session_state.post_topic or "Chủ đề nháp",
                        content=st.session_state.post_content,
                        image_path=st.session_state.post_image_path,
                        status="draft",
                    )
                    st.success(f"✅ Đã lưu bản nháp thành công! (Mã ID: #{draft_id})")

        with action_col2:
            st.info("💡 Chuyển sang **Tab 2: Đăng bài & Lên lịch** để xem trước và xuất bản.")

    with col2:
        st.markdown("#### **🖼️ Hình ảnh đính kèm bài viết**")
        st.caption("Đính kèm 1 ảnh minh họa từ máy tính (PNG, JPG, JPEG, WEBP). Giới hạn tối đa 10MB.")

        uploaded_img = st.file_uploader(
            "Tải ảnh từ máy tính lên:",
            type=["png", "jpg", "jpeg", "webp"],
            help="Ảnh sẽ được lưu an toàn tại thư mục data/uploads/",
        )

        if uploaded_img is not None:
            file_signature = (
                getattr(uploaded_img, "file_id", None)
                or f"{uploaded_img.name}_{getattr(uploaded_img, 'size', 0)}"
            )
            if st.session_state.get("last_uploaded_file_id") != file_signature:
                try:
                    saved_path = save_uploaded_file(uploaded_img, upload_dir="data/uploads")
                    st.session_state.post_image_path = saved_path
                    st.session_state.last_uploaded_file_id = file_signature
                    st.success(f"✅ Đã tải ảnh lên: `{os.path.basename(saved_path)}`")
                except Exception as exc:
                    st.error(f"❌ Không thể lưu file ảnh: {exc}")

        # Show current image preview
        if st.session_state.post_image_path:
            if os.path.exists(st.session_state.post_image_path):
                st.image(
                    st.session_state.post_image_path,
                    caption=f"Ảnh đính kèm: {os.path.basename(st.session_state.post_image_path)}",
                    use_container_width=True,
                )
                if st.button("🗑️ Xóa ảnh này", use_container_width=True):
                    st.session_state.post_image_path = None
                    st.session_state.last_uploaded_file_id = None
                    st.rerun()
            else:
                st.warning("⚠️ File ảnh trước đó không còn tồn tại trên ổ đĩa.")
                st.session_state.post_image_path = None
        else:
            st.info("Chưa có ảnh nào được chọn. Bài viết sẽ được đăng ở định dạng văn bản (Text post).")


# ==============================================================================
# TAB 2: ĐĂNG BÀI & LÊN LỊCH
# ==============================================================================
with tab2:
    st.subheader("🚀 Đăng bài & Lên lịch xuất bản")
    st.caption("Xem trước trực quan mô phỏng giao diện Facebook và lựa chọn phương thức xuất bản phù hợp.")

    preview_col, schedule_col = st.columns([1, 1], gap="large")

    with preview_col:
        st.markdown("#### **📱 Xem trước giao diện Facebook (Card Preview)**")

        current_text = st.session_state.post_content.strip()
        display_text = current_text if current_text else "*(Chưa có nội dung bài viết. Hãy soạn thảo ở Tab 1)*"
        fanpage_title = st.session_state.fb_page_name or "Facebook Fanpage"

        # Render Facebook Post Card
        st.markdown(
            f"""
            <div class="fb-card-wrapper">
                <div class="fb-header">
                    <div class="fb-avatar">f</div>
                    <div>
                        <div class="fb-name">{fanpage_title}</div>
                        <div class="fb-time">Vừa xong · 🌐 Công khai</div>
                    </div>
                </div>
                <div class="fb-content">{display_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.post_image_path and os.path.exists(st.session_state.post_image_path):
            st.image(st.session_state.post_image_path, use_container_width=True)

        st.markdown(
            """
            <div style="background-color: #ffffff; border: 1px solid #ced0d4; border-top: none; border-radius: 0 0 10px 10px; margin-top: -15px; padding: 10px;">
                <div class="fb-footer">
                    <span>👍 Thích</span>
                    <span>💬 Bình luận</span>
                    <span>↗️ Chia sẻ</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with schedule_col:
        st.markdown("#### **⚙️ Tùy chọn xuất bản**")

        if not current_text:
            st.warning("⚠️ Bạn chưa có nội dung bài viết. Vui lòng quay lại **Tab 1: Tạo bài viết với AI** để soạn bài.")

        publish_mode = st.radio(
            "Chọn hình thức đăng:",
            [
                "🚀 Đăng ngay lên Fanpage",
                "⏰ Hẹn giờ qua Facebook Graph API (Server Meta)",
                "💻 Hẹn giờ Local máy tính (APScheduler)",
            ],
            index=0,
        )

        st.markdown("---")

        # Mode 1: Immediate Publish
        if publish_mode == "🚀 Đăng ngay lên Fanpage":
            st.info("Bài viết sẽ được đăng trực tiếp lên Facebook Fanpage ngay khi bạn bấm nút bên dưới.")

            if st.button("🚀 Xuất bản ngay bây giờ", type="primary", use_container_width=True):
                if not current_text:
                    st.error("❌ Nội dung bài viết không được để trống.")
                elif not env_config.get("FB_PAGE_ID") or not env_config.get("FB_PAGE_ACCESS_TOKEN"):
                    st.error("❌ Chưa cấu hình Facebook Page ID hoặc Page Access Token. Vui lòng qua Tab ⚙️ Cài đặt.")
                else:
                    try:
                        with st.spinner("Đang gửi bài viết đến Facebook Graph API..."):
                            fb_svc = FacebookService(
                                page_id=env_config["FB_PAGE_ID"],
                                access_token=env_config["FB_PAGE_ACCESS_TOKEN"],
                            )
                            img_path = st.session_state.post_image_path
                            if img_path and os.path.exists(img_path):
                                res = fb_svc.publish_photo_post(
                                    message=current_text,
                                    photo_path=img_path,
                                )
                            else:
                                res = fb_svc.publish_text_post(message=current_text)

                            fb_post_id = str(res.get("post_id") or res.get("id"))
                            # Save to SQLite database
                            saved_id = db_manager.save_post(
                                topic=st.session_state.post_topic or "Đăng ngay",
                                content=current_text,
                                image_path=img_path,
                                status="published",
                                fb_post_id=fb_post_id,
                            )
                            post_url = format_facebook_url(fb_post_id)
                            st.success(f"🎉 Đã đăng bài thành công lên Facebook Fanpage! (ID lưu: #{saved_id})")
                            if post_url:
                                st.markdown(f"🔗 **Xem bài viết trên Facebook:** [{post_url}]({post_url})")
                    except FacebookTokenError as tok_err:
                        st.error(f"❌ Lỗi Token Facebook (Code 190): {tok_err.user_message}")
                    except FacebookPermissionError as perm_err:
                        st.error(f"❌ Lỗi Quyền hạn Fanpage: {perm_err.user_message}")
                    except FacebookAPIError as api_err:
                        st.error(f"❌ Lỗi Facebook Graph API: {api_err.user_message}")
                    except Exception as exc:
                        st.error(f"❌ Có lỗi bất ngờ xảy ra: {exc}")

        # Mode 2: Facebook Graph API Scheduling
        elif publish_mode == "⏰ Hẹn giờ qua Facebook Graph API (Server Meta)":
            st.info(
                "Facebook Graph API hỗ trợ hẹn giờ trực tiếp trên máy chủ Meta: "
                "Thời gian phải từ **10 phút đến 75 ngày** kể từ thời điểm hiện tại. "
                "Máy tính của bạn không cần mở khi đến giờ đăng."
            )

            sched_date = st.date_input("Chọn ngày đăng:", value=datetime.now().date())
            sched_time = st.time_input(
                "Chọn giờ đăng:",
                value=(datetime.now() + timedelta(minutes=30)).time(),
            )
            scheduled_dt = datetime.combine(sched_date, sched_time)

            st.write(f"🕒 Thời gian đã chọn: **{scheduled_dt.strftime('%d/%m/%Y %H:%M:%S')}**")

            if st.button("⏰ Xác nhận hẹn giờ qua Facebook", type="primary", use_container_width=True):
                is_valid, err_msg, unix_ts = validate_schedule_datetime_fb(scheduled_dt)
                if not is_valid:
                    st.error(f"❌ {err_msg}")
                elif not current_text:
                    st.error("❌ Nội dung bài viết không được để trống.")
                elif not env_config.get("FB_PAGE_ID") or not env_config.get("FB_PAGE_ACCESS_TOKEN"):
                    st.error("❌ Chưa cấu hình Facebook Page ID hoặc Page Access Token trong Tab Cài đặt.")
                else:
                    try:
                        with st.spinner("Đang gửi lệnh hẹn giờ đến Facebook Graph API..."):
                            fb_svc = FacebookService(
                                page_id=env_config["FB_PAGE_ID"],
                                access_token=env_config["FB_PAGE_ACCESS_TOKEN"],
                            )
                            img_path = st.session_state.post_image_path
                            if img_path and os.path.exists(img_path):
                                res = fb_svc.publish_photo_post(
                                    message=current_text,
                                    photo_path=img_path,
                                    scheduled_publish_time=unix_ts,
                                )
                            else:
                                res = fb_svc.publish_text_post(
                                    message=current_text,
                                    scheduled_publish_time=unix_ts,
                                )

                            fb_post_id = str(res.get("post_id") or res.get("id"))
                            # Save in SQLite
                            saved_id = db_manager.save_post(
                                topic=st.session_state.post_topic or "Hẹn giờ Facebook",
                                content=current_text,
                                image_path=img_path,
                                status="scheduled_fb",
                                scheduled_time=scheduled_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                fb_post_id=fb_post_id,
                            )
                            st.success(
                                f"🎉 Đã lên lịch thành công trên máy chủ Facebook! (Mã bài viết: {fb_post_id}, ID: #{saved_id})\n"
                                f"Bài viết sẽ tự động xuất hiện vào lúc: {scheduled_dt.strftime('%d/%m/%Y %H:%M')}"
                            )
                    except FacebookAPIError as api_err:
                        st.error(f"❌ Lỗi Facebook Graph API: {api_err.user_message}")
                    except Exception as exc:
                        st.error(f"❌ Có lỗi xảy ra: {exc}")

        # Mode 3: Local APScheduler Scheduling
        elif publish_mode == "💻 Hẹn giờ Local máy tính (APScheduler)":
            st.info(
                "Hẹn giờ Local máy tính sử dụng thư viện APScheduler. "
                "Có thể đặt bất kỳ lúc nào trong tương lai (kể cả 1 phút sau). "
                "**Lưu ý:** Ứng dụng/máy tính của bạn cần được bật tại thời điểm hẹn giờ."
            )

            local_date = st.date_input("Chọn ngày đăng (Local):", value=datetime.now().date(), key="loc_date")
            local_time = st.time_input(
                "Chọn giờ đăng (Local):",
                value=(datetime.now() + timedelta(minutes=5)).time(),
                key="loc_time",
            )
            scheduled_local_dt = datetime.combine(local_date, local_time)

            st.write(f"🕒 Thời gian đã chọn: **{scheduled_local_dt.strftime('%d/%m/%Y %H:%M:%S')}**")

            if st.button("💻 Xác nhận hẹn giờ Local", type="primary", use_container_width=True):
                is_valid, err_msg = validate_schedule_datetime_local(scheduled_local_dt)
                if not is_valid:
                    st.error(f"❌ {err_msg}")
                elif not current_text:
                    st.error("❌ Nội dung bài viết không được để trống.")
                elif not env_config.get("FB_PAGE_ID") or not env_config.get("FB_PAGE_ACCESS_TOKEN"):
                    st.error("❌ Chưa cấu hình Facebook Page ID hoặc Page Access Token trong Tab Cài đặt.")
                else:
                    try:
                        # 1. Save in SQLite with scheduled_local status
                        img_path = st.session_state.post_image_path
                        post_id = db_manager.save_post(
                            topic=st.session_state.post_topic or "Hẹn giờ Local",
                            content=current_text,
                            image_path=img_path,
                            status="scheduled_local",
                            scheduled_time=scheduled_local_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                        # 2. Add job to APScheduler
                        job_id = scheduler_service.schedule_post(post_id=post_id, run_date=scheduled_local_dt)
                        st.success(
                            f"🎉 Đã thêm công việc hẹn giờ Local thành công!\n"
                            f"- Mã bài viết trong hệ thống: **#{post_id}**\n"
                            f"- Mã Job Scheduler: **{job_id}**\n"
                            f"- Thời gian chạy: **{scheduled_local_dt.strftime('%d/%m/%Y %H:%M:%S')}**"
                        )
                    except Exception as exc:
                        st.error(f"❌ Có lỗi khi lên lịch Local: {exc}")


# ==============================================================================
# TAB 3: LỊCH SỬ & QUẢN LÝ BÀI ĐĂNG
# ==============================================================================
with tab3:
    st.subheader("📊 Lịch sử & Quản lý bài đăng")
    st.caption("Quản lý toàn bộ bài viết đã tạo, đã đăng, đang hẹn giờ và bản nháp từ cơ sở dữ liệu SQLite.")

    # Refresh button
    top_col1, top_col2 = st.columns([1, 4])
    with top_col1:
        if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
            st.rerun()

    # Fetch posts
    all_posts = db_manager.get_all_posts(limit=100)

    # Statistics Cards
    count_total = len(all_posts)
    count_published = sum(1 for p in all_posts if p.get("status") == "published")
    count_scheduled = sum(
        1 for p in all_posts if p.get("status") in ("scheduled_fb", "scheduled_local")
    )
    count_failed = sum(1 for p in all_posts if p.get("status") == "failed")
    count_draft = sum(1 for p in all_posts if p.get("status") == "draft")

    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        st.markdown(
            f'<div class="stat-card"><div class="stat-number">{count_total}</div><div class="stat-label">Tổng bài viết</div></div>',
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            f'<div class="stat-card"><div class="stat-number" style="color:#28a745;">{count_published}</div><div class="stat-label">Đã đăng thành công</div></div>',
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            f'<div class="stat-card"><div class="stat-number" style="color:#007bff;">{count_scheduled}</div><div class="stat-label">Đang hẹn giờ</div></div>',
            unsafe_allow_html=True,
        )
    with s4:
        st.markdown(
            f'<div class="stat-card"><div class="stat-number" style="color:#fd7e14;">{count_draft}</div><div class="stat-label">Bản nháp</div></div>',
            unsafe_allow_html=True,
        )
    with s5:
        st.markdown(
            f'<div class="stat-card"><div class="stat-number" style="color:#dc3545;">{count_failed}</div><div class="stat-label">Thất bại / Lỗi</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Filter posts by status
    filter_status = st.selectbox(
        "Lọc bài viết theo trạng thái:",
        ["Tất cả", "published", "scheduled_fb", "scheduled_local", "draft", "failed", "cancelled"],
        index=0,
    )

    filtered_posts = all_posts
    if filter_status != "Tất cả":
        filtered_posts = [p for p in all_posts if p.get("status") == filter_status]

    if not filtered_posts:
        st.info("Chưa có bài viết nào phù hợp với bộ lọc đã chọn.")
    else:
        st.markdown(f"**Hiển thị {len(filtered_posts)} bài viết:**")

        for post in filtered_posts:
            pid = post["id"]
            topic = post.get("topic", "Không có tiêu đề")
            status = post.get("status", "draft")
            created_at = post.get("created_at", "")
            scheduled_time = post.get("scheduled_time")
            fb_post_id = post.get("fb_post_id")
            content = post.get("content", "")
            image_path = post.get("image_path")
            err_msg = post.get("error_message")

            badge_html = render_status_badge_html(status)
            fb_link = format_facebook_url(fb_post_id)

            time_info = f"🕒 Tạo lúc: {created_at}"
            if scheduled_time:
                time_info += f" | Hẹn giờ: {scheduled_time}"

            expander_title = f"#{pid} · [{get_status_badge(status)['label']}] {topic[:60]}... ({time_info})"

            with st.expander(expander_title, expanded=False):
                header_c1, header_c2 = st.columns([3, 1])
                with header_c1:
                    st.markdown(f"**Trạng thái:** {badge_html}", unsafe_allow_html=True)
                    if fb_post_id:
                        st.markdown(f"**Facebook Post ID:** `{fb_post_id}`")
                        if fb_link:
                            st.markdown(f"🔗 [Mở bài đăng trên Facebook]({fb_link})")
                    if scheduled_time:
                        st.markdown(f"⏰ **Thời gian hẹn giờ:** `{scheduled_time}`")
                with header_c2:
                    st.caption(f"Tạo lúc: {created_at}")

                if err_msg:
                    st.error(f"❌ Chi tiết lỗi: {err_msg}")

                st.markdown("**Nội dung:**")
                st.text_area(
                    "Content",
                    value=content,
                    height=120,
                    key=f"content_display_{pid}",
                    disabled=True,
                    label_visibility="collapsed",
                )

                if image_path:
                    if os.path.exists(image_path):
                        st.image(image_path, width=240, caption=f"Ảnh: {os.path.basename(image_path)}")
                    else:
                        st.caption(f"Ảnh không tồn tại: {image_path}")

                st.markdown("---")
                btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)

                with btn_c1:
                    if status in ("failed", "draft"):
                        if st.button("🔁 Đăng ngay lại", key=f"retry_{pid}", use_container_width=True):
                            try:
                                fb_svc = FacebookService(
                                    page_id=env_config["FB_PAGE_ID"],
                                    access_token=env_config["FB_PAGE_ACCESS_TOKEN"],
                                )
                                if image_path and os.path.exists(image_path):
                                    res = fb_svc.publish_photo_post(message=content, photo_path=image_path)
                                else:
                                    res = fb_svc.publish_text_post(message=content)
                                new_post_id = str(res.get("post_id") or res.get("id"))
                                db_manager.update_post_status(
                                    post_id=pid,
                                    status="published",
                                    fb_post_id=new_post_id,
                                )
                                st.success("✅ Đã xuất bản lại thành công!")
                                st.rerun()
                            except Exception as ex:
                                db_manager.update_post_status(
                                    post_id=pid,
                                    status="failed",
                                    error_message=str(ex),
                                )
                                st.error(f"❌ Thử lại thất bại: {ex}")

                with btn_c2:
                    if st.button("📝 Chép vào Tab 1 để sửa", key=f"copy_{pid}", use_container_width=True):
                        st.session_state.post_topic = topic
                        st.session_state.topic_input_area = topic
                        st.session_state.post_content = content
                        st.session_state.content_editor_area = content
                        st.session_state.post_image_path = image_path if (image_path and os.path.exists(image_path)) else None
                        st.success("✅ Đã nạp nội dung vào Tab 1! Vui lòng chuyển sang Tab 1 để chỉnh sửa.")

                with btn_c3:
                    if status == "scheduled_local":
                        if st.button("🚫 Hủy lịch Local", key=f"cancel_{pid}", use_container_width=True):
                            cancelled = scheduler_service.cancel_scheduled_post(f"post_{pid}")
                            if cancelled:
                                st.success("✅ Đã hủy lịch đăng thành công.")
                            else:
                                db_manager.update_post_status(post_id=pid, status="cancelled")
                                st.info("ℹ️ Đã cập nhật trạng thái hủy.")
                            st.rerun()

                with btn_c4:
                    if st.button("🗑️ Xóa bài viết", key=f"del_{pid}", use_container_width=True):
                        if status == "scheduled_local":
                            scheduler_service.cancel_scheduled_post(f"post_{pid}")
                        db_manager.delete_post(pid)
                        st.success(f"✅ Đã xóa bài viết #{pid}.")
                        st.rerun()


# ==============================================================================
# TAB 4: CÀI ĐẶT & HƯỚNG DẪN TOKEN
# ==============================================================================
with tab4:
    st.subheader("⚙️ Cấu hình API & Hướng dẫn lấy Token Fanpage")
    st.caption("Cấu hình kết nối Google Gemini API và Meta Facebook Graph API. Thông tin được lưu vào file `.env` an toàn.")

    conf_col, guide_col = st.columns([1, 1], gap="large")

    with conf_col:
        st.markdown("#### **🔑 Cấu hình Khóa API & Mã Fanpage**")

        with st.form("settings_form"):
            gemini_key_input = st.text_input(
                "Google Gemini API Key:",
                value=env_config.get("GEMINI_API_KEY", ""),
                type="password",
                help="Lấy khóa miễn phí từ Google AI Studio (https://aistudio.google.com/)",
            )

            openrouter_key_input = st.text_input(
                "OpenRouter API Key:",
                value=env_config.get("OPENROUTER_API_KEY", ""),
                type="password",
                help="Lấy khóa miễn phí từ OpenRouter (https://openrouter.ai/keys) để dùng DeepSeek, Llama 3, Qwen...",
            )

            fb_page_id_input = st.text_input(
                "Facebook Fanpage ID:",
                value=env_config.get("FB_PAGE_ID", ""),
                help="ID trang Fanpage của bạn (gồm dãy số, ví dụ: 102938475610293)",
            )

            fb_token_input = st.text_input(
                "Facebook Page Access Token (Long-Lived):",
                value=env_config.get("FB_PAGE_ACCESS_TOKEN", ""),
                type="password",
                help="Mã truy cập trang Fanpage có quyền pages_manage_posts và pages_read_engagement.",
            )

            save_settings_btn = st.form_submit_button("💾 Lưu cấu hình vào file .env", type="primary", use_container_width=True)

            if save_settings_btn:
                updates = {
                    "GEMINI_API_KEY": gemini_key_input.strip(),
                    "OPENROUTER_API_KEY": openrouter_key_input.strip(),
                    "FB_PAGE_ID": fb_page_id_input.strip(),
                    "FB_PAGE_ACCESS_TOKEN": fb_token_input.strip(),
                }
                success = save_env_config(updates, env_path=".env")
                if success:
                    st.success("✅ Đã lưu cấu hình thành công vào `.env`!")
                    st.rerun()
                else:
                    st.error("❌ Không thể lưu vào file .env.")

        st.markdown("---")
        st.markdown("#### **🔍 Kiểm tra kết nối API**")

        test_col1, test_col2, test_col3 = st.columns(3)

        with test_col1:
            if st.button("Kiểm tra Fanpage", use_container_width=True):
                cur_page_id = env_config.get("FB_PAGE_ID")
                cur_token = env_config.get("FB_PAGE_ACCESS_TOKEN")
                if not cur_page_id or not cur_token:
                    st.warning("⚠️ Vui lòng lưu Page ID và Page Access Token trước khi kiểm tra.")
                else:
                    try:
                        with st.spinner("Đang gọi Facebook Graph API verify_token..."):
                            fb_svc = FacebookService(page_id=cur_page_id, access_token=cur_token)
                            verify_res = fb_svc.verify_token()
                            page_name = verify_res.get("page_name", "Không rõ")
                            can_post = verify_res.get("can_post", False)
                            tasks = verify_res.get("tasks", [])

                            st.session_state.fb_page_name = page_name

                            st.success(f"✅ Kết nối Fanpage thành công!\n- **Tên Page:** {page_name}\n- **Page ID:** {cur_page_id}")
                            if can_post:
                                st.info(f"🟢 Quyền đăng bài: **Đầy đủ** (Tasks: {', '.join(tasks)})")
                            else:
                                st.warning(f"⚠️ Token thiếu quyền đăng bài: Tasks hiện tại: {tasks}")
                    except FacebookTokenError as tok_err:
                        st.error(f"❌ Token hết hạn hoặc không hợp lệ: {tok_err.user_message}")
                    except FacebookPermissionError as perm_err:
                        st.error(f"❌ Thiếu quyền quản lý bài viết: {perm_err.user_message}")
                    except Exception as ex:
                        st.error(f"❌ Lỗi kiểm tra kết nối Facebook: {ex}")

        with test_col2:
            if st.button("Kiểm tra Gemini AI", use_container_width=True):
                cur_gemini_key = env_config.get("GEMINI_API_KEY")
                if not cur_gemini_key:
                    st.warning("⚠️ Vui lòng lưu Gemini API Key trước khi kiểm tra.")
                else:
                    try:
                        with st.spinner("Đang gửi thử nghiệm đến Google Gemini API..."):
                            gemini_svc = GeminiService(api_key=cur_gemini_key)
                            test_res = gemini_svc.generate_fanpage_post(
                                topic="Xin chào Fanpage Auto-Poster",
                                tone="ngắn gọn",
                                include_hashtags=False,
                                use_search=False,
                            )
                            st.success("✅ Kết nối Gemini API thành công! Mô hình phản hồi tốt.")
                    except Exception as ex:
                        st.error(f"❌ Lỗi kết nối Gemini AI: {ex}")

        with test_col3:
            if st.button("Kiểm tra OpenRouter", use_container_width=True):
                cur_or_key = env_config.get("OPENROUTER_API_KEY")
                if not cur_or_key:
                    st.warning("⚠️ Vui lòng lưu OpenRouter API Key trước khi kiểm tra.")
                else:
                    try:
                        with st.spinner("Đang xác thực với OpenRouter..."):
                            or_svc = OpenRouterService(api_key=cur_or_key)
                            key_info = or_svc.verify_key()
                            if key_info.get("valid"):
                                tier_str = "Miễn phí (Free Tier)" if key_info.get("is_free_tier") else "Có phí"
                                st.success(f"✅ Kết nối OpenRouter thành công!\n- Nhãn: {key_info.get('label')}\n- Gói: {tier_str}")
                            else:
                                st.error(f"❌ OpenRouter từ chối khóa: {key_info.get('error')}")
                    except Exception as ex:
                        st.error(f"❌ Lỗi kết nối OpenRouter: {ex}")

        st.markdown("---")
        st.markdown("#### **🤖 Quét & Kiểm tra các Model OpenRouter**")
        st.caption("Tra cứu danh sách model thời gian thực từ OpenRouter, lọc model miễn phí và gửi ping kiểm tra kết nối.")

        cur_or_key_scan = env_config.get("OPENROUTER_API_KEY", "").strip()
        or_scan_col1, or_scan_col2 = st.columns([1, 1])
        with or_scan_col1:
            only_free_filter = st.checkbox("Chỉ hiển thị Model Miễn Phí (:free)", value=True, key="only_free_filter_cb")
        with or_scan_col2:
            model_search_keyword = st.text_input("Lọc theo tên hoặc ID:", placeholder="vd: deepseek, llama, qwen...", key="or_kw_filter")

        if st.button("🔄 Tải danh sách Model từ OpenRouter", use_container_width=True, key="fetch_or_models_btn"):
            if not cur_or_key_scan:
                st.warning("⚠️ Vui lòng lưu OPENROUTER_API_KEY trước khi quét danh sách.")
            else:
                try:
                    with st.spinner("Đang tải danh sách model thời gian thực từ OpenRouter..."):
                        or_svc = OpenRouterService(api_key=cur_or_key_scan)
                        models_list = or_svc.get_available_models(only_free=only_free_filter)
                        st.session_state.openrouter_models_cache = models_list
                        st.success(f"✅ Đã tìm thấy {len(models_list)} model!")
                except Exception as ex:
                    st.error(f"❌ Không thể tải danh sách model: {ex}")

        cached_models = st.session_state.get("openrouter_models_cache", [])
        if cached_models:
            filtered = [
                m for m in cached_models
                if not model_search_keyword.strip()
                or model_search_keyword.lower() in m.get("id", "").lower()
                or model_search_keyword.lower() in m.get("name", "").lower()
            ]
            st.info(f"📊 Tìm thấy **{len(filtered)}** / {len(cached_models)} model phù hợp")

            if filtered:
                test_m_col1, test_m_col2 = st.columns([2, 1])
                with test_m_col1:
                    selected_test_m = st.selectbox(
                        "Chọn model để kiểm tra kết nối trực tiếp:",
                        options=[m["id"] for m in filtered],
                        format_func=lambda mid: next((f"{m['name']} ({m['id']})" for m in filtered if m["id"] == mid), mid),
                        key="selected_test_m_box",
                    )
                with test_m_col2:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    test_ping_btn = st.button("⚡ Test kết nối model này", use_container_width=True, key="test_ping_m_btn")

                if test_ping_btn and selected_test_m:
                    with st.spinner(f"Đang gửi ping thử nghiệm tới model `{selected_test_m}`..."):
                        or_svc = OpenRouterService(api_key=cur_or_key_scan)
                        ping_res = or_svc.test_model_connection(selected_test_m)
                        if ping_res.get("success"):
                            st.success(f"🟢 **{selected_test_m}** phản hồi thành công!\n- Thời gian: `{ping_res.get('latency_ms')}ms`\n- Trả lời: `{ping_res.get('message')}`")
                        else:
                            st.error(f"🔴 **{selected_test_m}** lỗi: {ping_res.get('message')}")
            else:
                st.warning("Không tìm thấy model nào khớp với từ khóa tìm kiếm.")

    with guide_col:
        st.markdown("#### **📖 Hướng dẫn chi tiết lấy Long-Lived Token Fanpage**")

        with st.expander("📌 Bước 1: Tạo ứng dụng Meta Developer (5 phút)", expanded=True):
            st.markdown(
                """
                1. Truy cập cổng lập trình viên của Meta: [developers.facebook.com](https://developers.facebook.com/) và đăng nhập tài khoản Facebook quản trị Fanpage.
                2. Nhấp **My Apps (Ứng dụng của tôi)** -> **Create App (Tạo ứng dụng)**.
                3. Chọn loại ứng dụng: **Business (Doanh nghiệp)** hoặc **Other (Khác)**.
                4. Đặt tên ứng dụng (ví dụ: `AutoPoster Fanpage`) và bấm Tạo.
                """
            )

        with st.expander("📌 Bước 2: Lấy Token qua Graph API Explorer", expanded=True):
            st.markdown(
                """
                1. Mở công cụ [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
                2. Tại mục **Meta App**, chọn ứng dụng bạn vừa tạo ở Bước 1.
                3. Tại mục **User or Page**, chọn **User Token**.
                4. Tại ô **Add Permissions**, thêm 3 quyền bắt buộc:
                   - `pages_show_list`
                   - `pages_read_engagement`
                   - `pages_manage_posts`
                5. Nhấp **Generate Access Token** và bấm đồng ý cấp quyền trên giao diện Facebook.
                6. Sau đó, tại mục **User or Page**, chuyển chọn sang **Tên Fanpage của bạn**. Ô Token sẽ tự đổi thành **Page Access Token**.
                """
            )

        with st.expander("📌 Bước 3: Đổi sang Long-Lived Token (Vĩnh viễn cho Page)", expanded=True):
            st.markdown(
                """
                Page Access Token lấy từ Graph API Explorer mặc định hết hạn sau 1 giờ. Để lấy token **vĩnh viễn (Never Expire)**:
                1. Truy cập [Access Token Tool](https://developers.facebook.com/tools/accesstoken/).
                2. Tìm đến ứng dụng của bạn, nhấp **Debug** bên cạnh User Token.
                3. Nhấp nút **Extend Access Token** ở cuối bảng để lấy Long-Lived User Token (có hiệu lực 60 ngày).
                4. Dùng Long-Lived User Token đó gọi endpoint `me/accounts` trên Graph API Explorer để lấy Page Access Token vĩnh viễn (Never Expire).
                5. Sao chép Token đó dán vào ô **Facebook Page Access Token** bên trái và bấm Lưu.
                """
            )

        with st.expander("📌 Bước 4: Lấy Facebook Page ID"):
            st.markdown(
                """
                1. Vào trang Fanpage của bạn trên Facebook.
                2. Nhấp vào tab **Giới thiệu (About)** -> cuộn xuống mục **Thông tin trang**.
                3. Sao chép dãy số tại mục **ID Trang (Page ID)** (ví dụ: `102938475610293`).
                """
            )

        with st.expander("📌 Bước 5: Lấy Google Gemini API Key miễn phí"):
            st.markdown(
                """
                1. Truy cập [Google AI Studio](https://aistudio.google.com/).
                2. Đăng nhập bằng tài khoản Google.
                3. Nhấp **Get API key** -> **Create API key in new project**.
                4. Sao chép mã API Key dán vào ô **Google Gemini API Key** bên trái và bấm Lưu.
                """
            )

        with st.expander("📌 Bước 6: Lấy OpenRouter API Key (Dùng DeepSeek, Llama 3 miễn phí)"):
            st.markdown(
                """
                1. Truy cập [OpenRouter Keys](https://openrouter.ai/keys).
                2. Đăng nhập bằng tài khoản Google hoặc GitHub.
                3. Nhấp nút **Create Key** (Tạo khóa mới).
                4. Đặt tên gợi nhớ (ví dụ: `Fanpage-AutoPoster`) và nhấn Create.
                5. Sao chép mã (bắt đầu bằng `sk-or-v1-...`) dán vào ô **OpenRouter API Key** bên trái và bấm Lưu.
                6. Bạn có thể sử dụng các model đuôi `:free` (như `deepseek/deepseek-chat:free`, `deepseek/deepseek-r1:free`, `meta-llama/llama-3.3-70b-instruct:free`) hoàn toàn miễn phí!
                """
            )
