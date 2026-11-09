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
    parse_image_paths,
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
if "post_image_paths" not in st.session_state:
    st.session_state.post_image_paths = []
if "processed_file_signatures" not in st.session_state:
    st.session_state.processed_file_signatures = set()
if "last_uploaded_file_id" not in st.session_state:
    st.session_state.last_uploaded_file_id = None
if "post_sources" not in st.session_state:
    st.session_state.post_sources = []
if "fb_page_name" not in st.session_state:
    st.session_state.fb_page_name = "Facebook Fanpage"

# Load current credentials from .env
env_config = load_env_config()

# Auto-migrate credentials from .env to SQLite fanpages table if available
if env_config.get("FB_PAGE_ID") and env_config.get("FB_PAGE_ACCESS_TOKEN"):
    try:
        env_pid = str(env_config["FB_PAGE_ID"]).strip()
        env_tok = str(env_config["FB_PAGE_ACCESS_TOKEN"]).strip()
        default_name = "Sửa Máy Tính Tại Nhà BMT" if env_pid == "619960427857965" else f"Fanpage {env_pid}"
        db_manager.migrate_from_env(page_id=env_pid, access_token=env_tok, page_name=default_name)
    except Exception as exc:
        logger.warning(f"Auto-migration from env warning: {exc}")


# Sidebar Navigation & System Status
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/b/b9/2023_Facebook_icon.svg",
        width=50,
    )
    st.markdown("### **Fanpage Auto-Poster**")
    st.caption("Phiên bản v1.2.0 · Đa Fanpage & Đa AI (Gemini + OpenRouter)")

    st.markdown("---")
    st.markdown("#### **Trạng thái hệ thống**")

    # AI Status Indicators
    has_gemini = bool(env_config.get("GEMINI_API_KEY"))
    if has_gemini:
        st.success("🟢 Gemini AI: Đã kết nối", icon="✅")
    else:
        st.warning("🟡 Gemini AI: Chưa có Key", icon="⚠️")

    has_openrouter = bool(env_config.get("OPENROUTER_API_KEY"))
    if has_openrouter:
        st.success("🟢 OpenRouter: Đã kết nối", icon="🤖")

    # Facebook Fanpages Status Indicator
    active_fanpages_sidebar = db_manager.get_fanpages(only_active=True)
    all_fanpages_sidebar = db_manager.get_fanpages(only_active=False)
    if active_fanpages_sidebar:
        st.success(f"🟢 Fanpages: {len(active_fanpages_sidebar)} trang kích hoạt", icon="📄")
    elif all_fanpages_sidebar:
        st.warning(f"🟡 Fanpages: {len(all_fanpages_sidebar)} trang (đang tắt)", icon="⏸️")
    else:
        st.warning("🟡 Fanpage: Chưa thêm trang nào", icon="⚠️")

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
    '<div class="subtitle">Sáng tạo nội dung với Google Gemini / OpenRouter, quản lý đa Fanpage và lên lịch tự động.</div>',
    unsafe_allow_html=True,
)

# Main Application Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📝 Tạo bài viết với AI",
        "🚀 Đăng bài & Lên lịch",
        "📊 Lịch sử & Quản lý bài đăng",
        "📑 Quản trị Fanpages",
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
            topic_clean = str(topic_input or "").strip()
            if not topic_clean:
                st.warning("⚠️ Vui lòng nhập chủ đề trước khi yêu cầu viết bài.")
            else:
                gemini_key = str(env_config.get("GEMINI_API_KEY") or "").strip()
                openrouter_key = str(env_config.get("OPENROUTER_API_KEY") or "").strip()

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
                    draft_img_val = ",".join(st.session_state.post_image_paths) if st.session_state.post_image_paths else st.session_state.post_image_path
                    draft_id = db_manager.save_post(
                        topic=st.session_state.post_topic or "Chủ đề nháp",
                        content=st.session_state.post_content,
                        image_path=draft_img_val,
                        status="draft",
                    )
                    st.success(f"✅ Đã lưu bản nháp thành công! (Mã ID: #{draft_id})")

        with action_col2:
            st.info("💡 Chuyển sang **Tab 2: Đăng bài & Lên lịch** để xem trước và xuất bản.")

    with col2:
        st.markdown("#### **🖼️ Hình ảnh đính kèm bài viết**")
        st.caption("Đính kèm một hoặc nhiều ảnh minh họa (PNG, JPG, JPEG, WEBP). Giới hạn tối đa 10MB mỗi ảnh.")

        uploaded_imgs = st.file_uploader(
            "Tải ảnh từ máy tính lên (có thể chọn nhiều ảnh):",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            help="Chọn một hoặc nhiều ảnh. Ảnh sẽ được lưu an toàn tại data/uploads/",
        )

        if uploaded_imgs:
            for uploaded_img in uploaded_imgs:
                file_sig = (
                    getattr(uploaded_img, "file_id", None)
                    or f"{uploaded_img.name}_{getattr(uploaded_img, 'size', 0)}"
                )
                uploaded_sigs = st.session_state.setdefault("processed_file_signatures", set())
                if file_sig not in uploaded_sigs:
                    try:
                        saved_path = save_uploaded_file(uploaded_img, upload_dir="data/uploads")
                        if saved_path not in st.session_state.post_image_paths:
                            st.session_state.post_image_paths.append(saved_path)
                        uploaded_sigs.add(file_sig)
                    except Exception as exc:
                        st.error(f"❌ Không thể lưu file `{uploaded_img.name}`: {exc}")

        # Sync single post_image_path with first item
        st.session_state.post_image_path = (
            st.session_state.post_image_paths[0] if st.session_state.post_image_paths else None
        )

        # Show current images preview
        valid_paths = [p for p in st.session_state.post_image_paths if os.path.exists(p)]
        st.session_state.post_image_paths = valid_paths

        if valid_paths:
            st.markdown(f"📸 **Đã chọn {len(valid_paths)} ảnh:**")
            num_cols = min(3, len(valid_paths))
            cols = st.columns(num_cols)
            for idx, img_p in enumerate(valid_paths):
                c = cols[idx % num_cols]
                with c:
                    st.image(img_p, caption=f"Ảnh #{idx+1}: {os.path.basename(img_p)}", use_container_width=True)
                    if st.button("🗑️ Xóa", key=f"del_img_t1_{idx}", use_container_width=True):
                        st.session_state.post_image_paths.pop(idx)
                        st.session_state.post_image_path = (
                            st.session_state.post_image_paths[0] if st.session_state.post_image_paths else None
                        )
                        st.rerun()

            if st.button("🗑️ Xóa tất cả ảnh", key="del_all_imgs_btn", use_container_width=True):
                st.session_state.post_image_paths = []
                st.session_state.post_image_path = None
                st.session_state.processed_file_signatures = set()
                st.rerun()
        else:
            st.info("Chưa có ảnh nào được chọn. Bài viết sẽ được đăng ở định dạng văn bản (Text post).")


# ==============================================================================
# TAB 2: ĐĂNG BÀI & LÊN LỊCH
# ==============================================================================
with tab2:
    st.subheader("🚀 Đăng bài & Lên lịch xuất bản")
    st.caption("Xem trước trực quan mô phỏng giao diện Facebook, chọn một hoặc nhiều Fanpage và lên lịch xuất bản.")

    active_fps = db_manager.get_fanpages(only_active=True)

    preview_col, schedule_col = st.columns([1, 1], gap="large")

    with preview_col:
        st.markdown("#### **📱 Xem trước giao diện Facebook (Card Preview)**")

        current_text = str(st.session_state.post_content or "").strip()
        display_text = current_text if current_text else "*(Chưa có nội dung bài viết. Hãy soạn thảo ở Tab 1)*"

        # Determine preview Fanpage title
        card_page_name = st.session_state.get("fb_page_name") or "Facebook Fanpage"
        if active_fps and card_page_name == "Facebook Fanpage":
            card_page_name = active_fps[0]["page_name"]

        # Render Facebook Post Card
        st.markdown(
            f"""
            <div class="fb-card-wrapper">
                <div class="fb-header">
                    <div class="fb-avatar">f</div>
                    <div>
                        <div class="fb-name">{card_page_name}</div>
                        <div class="fb-time">Vừa xong · 🌐 Công khai</div>
                    </div>
                </div>
                <div class="fb-content">{display_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        current_preview_imgs = [p for p in st.session_state.post_image_paths if os.path.exists(p)]
        if not current_preview_imgs and st.session_state.post_image_path and os.path.exists(st.session_state.post_image_path):
            current_preview_imgs = [st.session_state.post_image_path]

        if len(current_preview_imgs) == 1:
            st.image(current_preview_imgs[0], use_container_width=True)
        elif len(current_preview_imgs) > 1:
            st.caption(f"🖼️ Album đính kèm ({len(current_preview_imgs)} ảnh):")
            card_img_cols = st.columns(min(2, len(current_preview_imgs)))
            for ci, cp in enumerate(current_preview_imgs[:4]):
                with card_img_cols[ci % 2]:
                    st.image(cp, use_container_width=True)
            if len(current_preview_imgs) > 4:
                st.caption(f"... và {len(current_preview_imgs) - 4} ảnh khác")

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
        st.markdown("#### **⚙️ Tùy chọn Fanpage & Xuất bản**")

        if not current_text:
            st.warning("⚠️ Bạn chưa có nội dung bài viết. Vui lòng quay lại **Tab 1: Tạo bài viết với AI** để soạn bài.")

        if not active_fps:
            st.error("❌ Chưa có Fanpage nào được kích hoạt. Vui lòng vào Tab **📑 Quản trị Fanpages** để thêm hoặc bật Fanpage trước khi đăng!")
            target_fps = []
        else:
            col_target1, col_target2 = st.columns([2, 1])
            with col_target2:
                is_broadcast = st.checkbox("📢 Đăng nhiều Page", value=False, help="Cho phép chọn đồng thời nhiều Fanpage để đăng cùng lúc")
            with col_target1:
                if is_broadcast:
                    chosen_pids = st.multiselect(
                        "Chọn các Fanpage đăng bài:",
                        options=[fp["page_id"] for fp in active_fps],
                        default=[fp["page_id"] for fp in active_fps],
                        format_func=lambda pid: next((f"{fp['page_name']} ({fp['page_id']})" for fp in active_fps if fp["page_id"] == pid), pid),
                    )
                    target_fps = [fp for fp in active_fps if fp["page_id"] in chosen_pids]
                else:
                    chosen_pid = st.selectbox(
                        "Chọn Fanpage đăng bài:",
                        options=[fp["page_id"] for fp in active_fps],
                        format_func=lambda pid: next((f"{fp['page_name']} ({fp['page_id']})" for fp in active_fps if fp["page_id"] == pid), pid),
                    )
                    target_fps = [fp for fp in active_fps if fp["page_id"] == chosen_pid] if chosen_pid else []

            if target_fps:
                first_name = target_fps[0]["page_name"]
                st.session_state.fb_page_name = f"{first_name} (+{len(target_fps)-1} trang khác)" if len(target_fps) > 1 else first_name

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
            st.info("Bài viết sẽ được đăng trực tiếp lên Fanpage ngay khi bạn bấm nút bên dưới.")

            if st.button("🚀 Xuất bản ngay bây giờ", type="primary", use_container_width=True):
                if not current_text:
                    st.error("❌ Nội dung bài viết không được để trống.")
                elif not target_fps:
                    st.error("❌ Vui lòng chọn ít nhất một Fanpage để đăng bài.")
                else:
                    active_imgs = [p for p in st.session_state.post_image_paths if os.path.exists(p)]
                    if not active_imgs and st.session_state.post_image_path and os.path.exists(st.session_state.post_image_path):
                        active_imgs = [st.session_state.post_image_path]
                    img_db_val = ",".join(active_imgs) if active_imgs else None

                    for fp in target_fps:
                        fp_name = fp.get("page_name", fp["page_id"])
                        try:
                            with st.spinner(f"Đang gửi bài viết đến '{fp_name}'..."):
                                fb_svc = FacebookService(page_id=fp["page_id"], access_token=fp["access_token"])
                                if len(active_imgs) == 1:
                                    res = fb_svc.publish_photo_post(message=current_text, photo_path=active_imgs[0])
                                elif len(active_imgs) > 1:
                                    res = fb_svc.publish_multi_photo_post(message=current_text, photo_paths=active_imgs)
                                else:
                                    res = fb_svc.publish_text_post(message=current_text)

                                fb_post_id = str(res.get("post_id") or res.get("id"))
                                saved_id = db_manager.save_post(
                                    topic=st.session_state.post_topic or "Đăng ngay",
                                    content=current_text,
                                    image_path=img_db_val,
                                    status="published",
                                    fb_post_id=fb_post_id,
                                    page_id=fp["page_id"],
                                    page_name=fp_name,
                                )
                                post_url = format_facebook_url(fb_post_id)
                                st.success(f"🎉 Đã đăng bài thành công lên **{fp_name}**! (ID lưu: #{saved_id})")
                                if post_url:
                                    st.markdown(f"🔗 **Xem bài viết:** [{post_url}]({post_url})")
                        except FacebookAPIError as api_err:
                            st.error(f"❌ '{fp_name}': Lỗi Graph API: {api_err.user_message}")
                        except Exception as exc:
                            st.error(f"❌ '{fp_name}': Lỗi bất ngờ: {exc}")

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
                elif not target_fps:
                    st.error("❌ Vui lòng chọn ít nhất một Fanpage để lên lịch.")
                else:
                    active_imgs = [p for p in st.session_state.post_image_paths if os.path.exists(p)]
                    if not active_imgs and st.session_state.post_image_path and os.path.exists(st.session_state.post_image_path):
                        active_imgs = [st.session_state.post_image_path]
                    img_db_val = ",".join(active_imgs) if active_imgs else None

                    for fp in target_fps:
                        fp_name = fp.get("page_name", fp["page_id"])
                        try:
                            with st.spinner(f"Đang lên lịch trên máy chủ Facebook cho '{fp_name}'..."):
                                fb_svc = FacebookService(page_id=fp["page_id"], access_token=fp["access_token"])
                                if len(active_imgs) == 1:
                                    res = fb_svc.publish_photo_post(
                                        message=current_text,
                                        photo_path=active_imgs[0],
                                        scheduled_publish_time=unix_ts,
                                    )
                                elif len(active_imgs) > 1:
                                    res = fb_svc.publish_multi_photo_post(
                                        message=current_text,
                                        photo_paths=active_imgs,
                                        scheduled_publish_time=unix_ts,
                                    )
                                else:
                                    res = fb_svc.publish_text_post(
                                        message=current_text,
                                        scheduled_publish_time=unix_ts,
                                    )

                                fb_post_id = str(res.get("post_id") or res.get("id"))
                                saved_id = db_manager.save_post(
                                    topic=st.session_state.post_topic or "Hẹn giờ Facebook",
                                    content=current_text,
                                    image_path=img_db_val,
                                    status="scheduled_fb",
                                    scheduled_time=scheduled_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                    fb_post_id=fb_post_id,
                                    page_id=fp["page_id"],
                                    page_name=fp_name,
                                )
                                st.success(
                                    f"🎉 Đã lên lịch thành công cho **{fp_name}**! (Mã: {fb_post_id}, ID: #{saved_id}) | "
                                    f"Thời gian: {scheduled_dt.strftime('%d/%m/%Y %H:%M')}"
                                )
                        except FacebookAPIError as api_err:
                            st.error(f"❌ '{fp_name}': Lỗi Graph API: {api_err.user_message}")
                        except Exception as exc:
                            st.error(f"❌ '{fp_name}': Có lỗi xảy ra: {exc}")

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
                elif not target_fps:
                    st.error("❌ Vui lòng chọn ít nhất một Fanpage để lên lịch.")
                else:
                    active_imgs = [p for p in st.session_state.post_image_paths if os.path.exists(p)]
                    if not active_imgs and st.session_state.post_image_path and os.path.exists(st.session_state.post_image_path):
                        active_imgs = [st.session_state.post_image_path]
                    img_db_val = ",".join(active_imgs) if active_imgs else None

                    for fp in target_fps:
                        fp_name = fp.get("page_name", fp["page_id"])
                        try:
                            post_id = db_manager.save_post(
                                topic=st.session_state.post_topic or "Hẹn giờ Local",
                                content=current_text,
                                image_path=img_db_val,
                                status="scheduled_local",
                                scheduled_time=scheduled_local_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                page_id=fp["page_id"],
                                page_name=fp_name,
                            )
                            job_id = scheduler_service.schedule_post(post_id=post_id, run_date=scheduled_local_dt)
                            st.success(
                                f"🎉 Đã thêm công việc hẹn giờ Local cho **{fp_name}**! | Mã: #{post_id} | Job: {job_id} | "
                                f"Thời gian: {scheduled_local_dt.strftime('%d/%m/%Y %H:%M:%S')}"
                            )
                        except Exception as exc:
                            st.error(f"❌ '{fp_name}': Có lỗi khi lên lịch Local: {exc}")


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

    # Fanpage and Status Filters
    col_filter_status, col_filter_fp = st.columns([1, 1])
    with col_filter_fp:
        all_fanpages_filter = db_manager.get_fanpages(only_active=False)
        fp_filter_options = ["Tất cả Fanpages"] + [f"{f['page_name']} ({f['page_id']})" for f in all_fanpages_filter]
        selected_fp_label = st.selectbox("Lọc theo Fanpage:", fp_filter_options, index=0)

    selected_fp_id = None
    if selected_fp_label != "Tất cả Fanpages":
        selected_fp_id = next((f["page_id"] for f in all_fanpages_filter if f"{f['page_name']} ({f['page_id']})" == selected_fp_label), None)

    # Fetch posts
    all_posts = db_manager.get_all_posts(limit=100, page_id=selected_fp_id)

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

    with col_filter_status:
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
            page_name_val = post.get("page_name") or "Chưa gắn Page"

            badge_html = render_status_badge_html(status)
            fb_link = format_facebook_url(fb_post_id)

            time_info = f"🕒 Tạo lúc: {created_at}"
            if scheduled_time:
                time_info += f" | Hẹn giờ: {scheduled_time}"

            expander_title = f"#{pid} · [{page_name_val}] [{get_status_badge(status)['label']}] {topic[:50]}... ({time_info})"

            with st.expander(expander_title, expanded=False):
                header_c1, header_c2 = st.columns([3, 1])
                with header_c1:
                    st.markdown(f"**Trạng thái:** {badge_html} &nbsp;|&nbsp; 🏷️ **Fanpage:** `{page_name_val}`", unsafe_allow_html=True)
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

                parsed_post_imgs = parse_image_paths(image_path)
                valid_post_imgs = [p for p in parsed_post_imgs if os.path.exists(p)]

                if valid_post_imgs:
                    st.caption(f"📸 Ảnh đính kèm ({len(valid_post_imgs)}):")
                    hist_cols = st.columns(min(4, len(valid_post_imgs)))
                    for hi, hp in enumerate(valid_post_imgs):
                        with hist_cols[hi % min(4, len(valid_post_imgs))]:
                            st.image(hp, caption=f"#{hi+1}: {os.path.basename(hp)}", use_container_width=True)
                elif image_path:
                    st.caption(f"Ảnh không tồn tại: {image_path}")

                st.markdown("---")
                btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)

                with btn_c1:
                    if status in ("failed", "draft"):
                        if st.button("🔁 Đăng ngay lại", key=f"retry_{pid}", use_container_width=True):
                            try:
                                post_target_pid = post.get("page_id")
                                post_target_tok = None
                                if post_target_pid:
                                    rec = db_manager.get_fanpage_by_page_id(str(post_target_pid))
                                    if rec:
                                        post_target_tok = rec.get("access_token")
                                if not post_target_tok:
                                    post_target_pid = env_config.get("FB_PAGE_ID")
                                    post_target_tok = env_config.get("FB_PAGE_ACCESS_TOKEN")

                                if not post_target_pid or not post_target_tok:
                                    raise ValueError("Không tìm thấy thông tin xác thực Fanpage để xuất bản lại.")

                                fb_svc = FacebookService(page_id=post_target_pid, access_token=post_target_tok)
                                if len(valid_post_imgs) == 1:
                                    res = fb_svc.publish_photo_post(message=content, photo_path=valid_post_imgs[0])
                                elif len(valid_post_imgs) > 1:
                                    res = fb_svc.publish_multi_photo_post(message=content, photo_paths=valid_post_imgs)
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
                        st.session_state.post_image_paths = valid_post_imgs
                        st.session_state.post_image_path = valid_post_imgs[0] if valid_post_imgs else None
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
# TAB 4: QUẢN TRỊ FANPAGES
# ==============================================================================
with tab4:
    st.subheader("📑 Quản trị danh sách Facebook Fanpages")
    st.caption("Quản lý nhiều Fanpage, kiểm tra quyền đăng bài, kích hoạt / tạm ẩn và thêm Fanpage mới qua Graph API.")

    add_fp_col, list_fp_col = st.columns([1, 1], gap="large")

    with add_fp_col:
        st.markdown("#### **➕ Thêm Fanpage mới**")
        st.caption("Nhập Page ID và Page Access Token. Hệ thống sẽ tự động gọi Meta Graph API để lấy Tên Fanpage và kiểm tra quyền.")

        with st.form("add_fanpage_form"):
            new_pid = st.text_input(
                "Facebook Page ID:",
                placeholder="Ví dụ: 619960427857965",
                help="ID trang Fanpage (dãy số định danh duy nhất của Fanpage)",
            )
            new_token = st.text_input(
                "Facebook Page Access Token (Long-Lived):",
                type="password",
                placeholder="EAAB...",
                help="Mã Page Access Token dài hạn của Fanpage này",
            )
            add_fp_submit = st.form_submit_button("🔍 Xác thực & Thêm Fanpage", type="primary", use_container_width=True)

            if add_fp_submit:
                clean_pid = str(new_pid or "").strip()
                clean_tok = str(new_token or "").strip()
                if not clean_pid or not clean_tok:
                    st.error("❌ Vui lòng nhập đầy đủ Page ID và Page Access Token.")
                else:
                    try:
                        with st.spinner(f"Đang kiểm tra quyền hạn cho Page ID {clean_pid}..."):
                            verifier_svc = FacebookService(page_id=clean_pid, access_token=clean_tok)
                            token_info = verifier_svc.verify_token()
                            p_name = token_info.get("page_name") or f"Fanpage {clean_pid}"
                            db_manager.add_fanpage(
                                page_id=clean_pid,
                                page_name=p_name,
                                access_token=clean_tok,
                                is_active=1,
                            )
                            st.success(f"🎉 Xác thực thành công! Đã thêm Fanpage: **{p_name}** (ID: `{clean_pid}`)")
                            st.rerun()
                    except FacebookTokenError as tok_err:
                        st.error(f"❌ Token không hợp lệ hoặc đã hết hạn: {tok_err.user_message}")
                    except FacebookPermissionError as perm_err:
                        st.error(f"❌ Token không đủ quyền đăng bài: {perm_err.user_message}")
                    except FacebookAPIError as api_err:
                        st.error(f"❌ Lỗi Facebook Graph API: {api_err.user_message}")
                    except Exception as exc:
                        st.error(f"❌ Có lỗi bất ngờ khi xác thực: {exc}")

    with list_fp_col:
        st.markdown("#### **📋 Danh sách Fanpages đã lưu**")
        all_fps = db_manager.get_fanpages(only_active=False)

        if not all_fps:
            st.info("ℹ️ Hiện tại chưa có Fanpage nào được thêm. Hãy sử dụng form bên trái để thêm Fanpage đầu tiên.")
        else:
            st.caption(f"Tổng số: **{len(all_fps)}** Fanpage ({sum(1 for f in all_fps if f.get('is_active'))} đang hoạt động)")

            for idx, fp in enumerate(all_fps):
                f_pid = fp["page_id"]
                f_name = fp.get("page_name", f_pid)
                f_tok = fp.get("access_token", "")
                f_active = bool(fp.get("is_active", 1))
                masked_tok = f"{f_tok[:10]}...{f_tok[-4:]}" if len(f_tok) > 14 else "***"

                status_pill = "🟢 Hoạt động" if f_active else "🔴 Tạm tắt"
                card_title = f"{f_name} · [{status_pill}]"

                with st.expander(card_title, expanded=f_active):
                    st.markdown(f"**Tên Fanpage:** {f_name}")
                    st.markdown(f"**Page ID:** `{f_pid}`")
                    st.markdown(f"**Token:** `{masked_tok}`")
                    st.markdown(f"**Trạng thái:** **{status_pill}**")

                    btn_c1, btn_c2, btn_c3 = st.columns(3)
                    with btn_c1:
                        if st.button("🔄 Test kết nối", key=f"test_fp_{f_pid}", use_container_width=True):
                            try:
                                with st.spinner("Đang kiểm tra kết nối..."):
                                    test_svc = FacebookService(page_id=f_pid, access_token=f_tok)
                                    v_res = test_svc.verify_token()
                                    live_name = v_res.get("page_name") or f_name
                                    if live_name != f_name:
                                        db_manager.update_fanpage(f_pid, page_name=live_name)
                                    st.success(f"✅ Kết nối tốt! Tên: **{live_name}** | Quyền đăng: {'Có' if v_res.get('can_post') else 'Không'}")
                            except Exception as ex:
                                user_msg = getattr(ex, "user_message", str(ex))
                                st.error(f"❌ Lỗi kết nối: {user_msg}")

                    with btn_c2:
                        toggle_label = "⏸️ Tắt" if f_active else "▶️ Bật"
                        if st.button(toggle_label, key=f"toggle_fp_{f_pid}", use_container_width=True):
                            db_manager.toggle_fanpage_status(f_pid)
                            st.rerun()

                    with btn_c3:
                        if st.button("🗑️ Xóa", key=f"del_fp_{f_pid}", use_container_width=True):
                            db_manager.delete_fanpage(f_pid)
                            st.success(f"✅ Đã xóa Fanpage {f_name}.")
                            st.rerun()


# ==============================================================================
# TAB 5: CÀI ĐẶT & HƯỚNG DẪN TOKEN
# ==============================================================================
with tab5:
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

            fb_app_id_input = st.text_input(
                "Facebook App ID (n8nauto):",
                value=env_config.get("FB_APP_ID", "3711376692339694"),
                help="App ID từ Meta Developer App của bạn (Mặc định: 3711376692339694)",
            )

            fb_app_secret_input = st.text_input(
                "Facebook App Secret:",
                value=env_config.get("FB_APP_SECRET", ""),
                type="password",
                help="App Secret lấy từ developers.facebook.com/apps/.../settings/basic/ (bấm nút Copy)",
            )

            fb_page_id_input = st.text_input(
                "Facebook Fanpage ID (Mặc định):",
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
                    "GEMINI_API_KEY": str(gemini_key_input or "").strip(),
                    "OPENROUTER_API_KEY": str(openrouter_key_input or "").strip(),
                    "FB_APP_ID": str(fb_app_id_input or "").strip(),
                    "FB_APP_SECRET": str(fb_app_secret_input or "").strip(),
                    "FB_PAGE_ID": str(fb_page_id_input or "").strip(),
                    "FB_PAGE_ACCESS_TOKEN": str(fb_token_input or "").strip(),
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

        cur_or_key_scan = str(env_config.get("OPENROUTER_API_KEY") or "").strip()
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
            kw_clean = str(model_search_keyword or "").strip().lower()
            filtered = [
                m for m in cached_models
                if not kw_clean
                or kw_clean in str(m.get("id") or "").lower()
                or kw_clean in str(m.get("name") or "").lower()
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


    # --------------------------------------------------------------------------
    # KHU VỰC CÔNG CỤ FB TOKEN VĨNH VIỄN TOOL (Fb-Token-Tool.html)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("🔑 FB Token Vĩnh Viễn Tool (Tự động đổi & Lấy Token Page)")
    st.caption("Công cụ tự động chuyển đổi User Token ngắn hạn (1h) thành Token dài hạn (60 ngày) và trích xuất Page Access Token vĩnh viễn (Never Expire). Chạy trực tiếp từ server Python tránh hoàn toàn lỗi CORS.")

    st.warning("⚠️ **Bảo mật:** Token tương đương mật khẩu Fanpage. Hệ thống lưu trữ an toàn nội bộ trong máy của bạn, không gửi dữ liệu ra bên ngoài.")

    tool_col1, tool_col2 = st.columns([1, 1], gap="large")

    with tool_col1:
        st.markdown("##### **1️⃣ Nhập thông số đổi Token**")
        tool_app_id = st.text_input(
            "Meta App ID:",
            value=env_config.get("FB_APP_ID", "3711376692339694"),
            key="fb_tool_app_id",
            help="Mặc định lấy từ App ID đã lưu hoặc App n8nauto (3711376692339694)",
        )
        tool_app_secret = st.text_input(
            "Meta App Secret:",
            value=env_config.get("FB_APP_SECRET", ""),
            type="password",
            key="fb_tool_app_secret",
            help="Lấy tại developers.facebook.com/apps/.../settings/basic/ -> Bấm nút Copy kế bên App Secret",
        )
        tool_short_token = st.text_area(
            "Token ngắn hạn (Bắt đầu bằng EAA... tạo ở Graph API Explorer):",
            value="",
            height=90,
            key="fb_tool_short_token",
            placeholder="Dán User Token ngắn hạn vừa tạo ở Graph Explorer...",
        )

        btn_auto_all = st.button(
            "🚀 1-Click: Đổi Token & Lấy tất cả Fanpages",
            type="primary",
            use_container_width=True,
            key="fb_tool_btn_exchange_all",
        )

        if btn_auto_all:
            clean_app_id = str(tool_app_id or "").strip()
            clean_app_secret = str(tool_app_secret or "").strip()
            clean_short_token = str(tool_short_token or "").strip()

            if not clean_app_id or not clean_app_secret or not clean_short_token:
                st.error("❌ Vui lòng điền đầy đủ App ID, App Secret và Token ngắn hạn!")
            else:
                try:
                    with st.spinner("Đang gọi Facebook Graph API để đổi User Token dài hạn..."):
                        long_lived_res = FacebookService.exchange_token_to_long_lived(
                            app_id=clean_app_id,
                            app_secret=clean_app_secret,
                            short_token=clean_short_token,
                        )
                        long_user_token = long_lived_res.get("access_token", "")
                        st.session_state["tool_long_token"] = long_user_token
                        st.session_state["tool_long_expires"] = long_lived_res.get("expires_in")

                    with st.spinner("Đang lấy danh sách Fanpage và Page Access Token vĩnh viễn..."):
                        accounts = FacebookService.get_user_accounts(user_access_token=long_user_token)
                        st.session_state["tool_found_pages"] = accounts
                        st.success(f"🎉 Thành công! Tìm thấy {len(accounts)} Fanpage với Token vĩnh viễn!")
                        st.rerun()
                except FacebookTokenError as fte:
                    st.error(f"❌ Lỗi Token: {fte.user_message}\n\n💡 Lưu ý: Nếu lỗi 'Error validating client secret', hãy copy lại App Secret bằng nút Copy trong Meta Developer (đừng bôi đen bằng tay).")
                except FacebookAPIError as fae:
                    st.error(f"❌ Lỗi Facebook Graph API: {fae.user_message}")
                except Exception as ex:
                    st.error(f"❌ Lỗi không xác định: {ex}")

        with st.expander("🛠️ Đổi từng bước hoặc dán User Token dài hạn có sẵn"):
            manual_long_token_input = st.text_input(
                "User Token dài hạn (60 ngày):",
                value=st.session_state.get("tool_long_token", ""),
                key="manual_long_token_input",
                type="password",
            )
            if st.button("📄 Lấy danh sách Fanpage từ Token trên", key="btn_get_accounts_manual"):
                clean_lt = str(manual_long_token_input or "").strip()
                if not clean_lt:
                    st.warning("⚠️ Vui lòng dán User Token dài hạn!")
                else:
                    try:
                        with st.spinner("Đang tải danh sách Fanpage..."):
                            accs = FacebookService.get_user_accounts(user_access_token=clean_lt)
                            st.session_state["tool_found_pages"] = accs
                            st.success(f"✅ Tìm thấy {len(accs)} Fanpage!")
                            st.rerun()
                    except Exception as ex:
                        st.error(f"❌ Lỗi: {ex}")

        with st.expander("🔑 Bước 3: Đổi trực tiếp Page Token ngắn → vĩnh viễn"):
            short_page_tok_input = st.text_input(
                "Page Token ngắn hạn:",
                value="",
                type="password",
                key="short_page_tok_input",
                placeholder="Dán Page Token ngắn hạn...",
            )
            if st.button("🔄 Đổi Page Token sang vĩnh viễn", key="btn_exchange_page_token_direct"):
                clean_app_id = str(tool_app_id or "").strip()
                clean_app_secret = str(tool_app_secret or "").strip()
                clean_p_tok = str(short_page_tok_input or "").strip()
                if not clean_app_id or not clean_app_secret or not clean_p_tok:
                    st.error("❌ Vui lòng điền đủ App ID, App Secret và Page Token ngắn!")
                else:
                    try:
                        with st.spinner("Đang đổi Page Token..."):
                            res_pt = FacebookService.exchange_page_token_to_never_expire(
                                app_id=clean_app_id,
                                app_secret=clean_app_secret,
                                short_page_token=clean_p_tok,
                            )
                            perm_tok = res_pt.get("access_token")
                            st.session_state["tool_direct_perm_token"] = perm_tok
                            st.success("✅ Đã đổi sang Page Token vĩnh viễn thành công!")
                    except Exception as ex:
                        st.error(f"❌ Lỗi: {ex}")

            if st.session_state.get("tool_direct_perm_token"):
                st.markdown("**Page Token vĩnh viễn của bạn:**")
                st.code(st.session_state["tool_direct_perm_token"], language="text")

    with tool_col2:
        st.markdown("##### **2️⃣ Kết quả & Danh sách Fanpage tìm được**")

        long_tok = st.session_state.get("tool_long_token")
        if long_tok:
            exp_sec = st.session_state.get("tool_long_expires", 5184000)
            exp_days = round(exp_sec / 86400, 1) if exp_sec else 60
            st.info(f"⏳ **User Token 60 ngày:** Đã tạo thành công (hiệu lực ~{exp_days} ngày).")
            with st.expander("👁️ Xem chuỗi User Token 60 ngày"):
                st.code(long_tok, language="text")

        found_pages = st.session_state.get("tool_found_pages", [])
        if found_pages:
            st.markdown(f"**Danh sách Fanpages có quyền quản lý ({len(found_pages)}):**")
            for p_idx, page in enumerate(found_pages):
                pid = page.get("id", "")
                pname = page.get("name", "Không rõ")
                ptok = page.get("access_token", "")
                category = page.get("category", "")
                is_target = (pid == "619960427857965")

                border_color = "#10b981" if is_target else "#334155"
                badge = " 🎯 [Sửa Máy Tính BMT]" if is_target else ""

                st.markdown(f"**{pname}**{badge}  \n`ID: {pid}` {f'| Danh mục: {category}' if category else ''}")

                with st.expander(f"🔑 Xem Page Token vĩnh viễn của `{pname}`"):
                    st.code(ptok, language="text")

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.button(f"➕ Thêm vào Quản trị Fanpage", key=f"add_db_p_{pid}_{p_idx}", use_container_width=True):
                        try:
                            db_manager.add_fanpage(page_id=pid, page_name=pname, access_token=ptok, is_active=1)
                            st.success(f"✅ Đã thêm '{pname}' vào Quản trị Fanpages thành công!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ Lỗi lưu Fanpage vào DB: {ex}")

                with btn_c2:
                    if st.button(f"📌 Đặt làm Page chính (.env)", key=f"set_env_p_{pid}_{p_idx}", use_container_width=True):
                        try:
                            save_env_config({"FB_PAGE_ID": pid, "FB_PAGE_ACCESS_TOKEN": ptok}, env_path=".env")
                            st.session_state.fb_page_name = pname
                            st.success(f"✅ Đã đặt '{pname}' làm Fanpage chính trong `.env`!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ Lỗi lưu vào .env: {ex}")
                st.markdown("---")
        else:
            st.info("Chưa có danh sách Fanpage. Hãy nhập App ID, App Secret và Token ngắn hạn ở bên trái rồi bấm **'🚀 1-Click: Đổi Token & Lấy tất cả Fanpages'**.")
