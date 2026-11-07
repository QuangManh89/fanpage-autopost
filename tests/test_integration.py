"""Comprehensive End-to-End Integration Tests for Facebook Fanpage Auto-Poster.

Tests the full user workflows tying together:
- DatabaseManager (SQLite)
- GeminiService (mocked Google Gemini AI with search grounding)
- FacebookService (mocked Meta Facebook Graph API)
- LocalSchedulerService (APScheduler background scheduler)
- Streamlit Web App interaction lifecycle
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest

from src.database import DatabaseManager
from src.facebook_service import (
    FacebookAPIError,
    FacebookService,
    FacebookTokenError,
)
from src.gemini_service import GeminiService
from src.openrouter_service import OpenRouterService
from src.scheduler_service import LocalSchedulerService
from src.ui_helpers import (
    validate_schedule_datetime_fb,
    validate_schedule_datetime_local,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provide a fresh SQLite DatabaseManager in a temporary directory."""
    db_file = tmp_path / "test_integration.db"
    return DatabaseManager(db_path=str(db_file))


@pytest.fixture
def mock_gemini_client():
    """Provide a mock Google genai client returning structured Facebook post content."""
    mock_client = MagicMock()

    sample_text = (
        "🔥 ĐỘT PHÁ CÔNG NGHỆ AI NĂM 2026: KỶ NGUYÊN TỰ ĐỘNG HÓA! 🚀\n\n"
        "Năm 2026 chứng kiến bước nhảy vọt của các mô hình đa tác vụ.\n\n"
        "📌 Điểm nhấn đáng chú ý:\n"
        "• AI Agent tự vận hành quy trình kinh doanh đa kênh\n"
        "• Tìm kiếm web thời gian thực tích hợp trực tiếp vào phân tích\n"
        "• Tối ưu tương tác mạng xã hội theo hành vi thời gian thực\n\n"
        "👉 Bạn đã sẵn sàng trang bị AI cho doanh nghiệp chưa? Bình luận ngay để nhận tài liệu nhé!\n\n"
        "#AI2026 #TuDongHoa #FanpageMarketing #TechTrends"
    )

    mock_response = MagicMock()
    mock_response.text = sample_text

    # Mock grounding metadata
    mock_candidate = MagicMock()
    mock_chunk1 = MagicMock()
    mock_chunk1.web.uri = "https://news.example.com/ai-trends-2026"
    mock_chunk2 = MagicMock()
    mock_chunk2.web.uri = "https://tech.example.com/automation"

    mock_candidate.grounding_metadata.grounding_chunks = [mock_chunk1, mock_chunk2]
    mock_response.candidates = [mock_candidate]

    mock_client.models.generate_content.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_fb_service():
    """Provide a mock FacebookService instance."""
    mock = MagicMock(spec=FacebookService)
    mock.page_id = "100200300400"
    mock.access_token = "mock_page_access_token_secret"
    mock.publish_text_post.return_value = {"id": "100200300400_post_text_111"}
    mock.publish_photo_post.return_value = {
        "id": "photo_asset_555",
        "post_id": "100200300400_post_photo_222",
    }
    mock.verify_token.return_value = {
        "valid": True,
        "page_name": "Test Tech Fanpage",
        "page_id": "100200300400",
        "avatar_url": "https://example.com/avatar.jpg",
        "expires_at": "Never (Page Token)",
        "permissions": ["pages_manage_posts", "pages_read_engagement"],
    }
    return mock


# ==============================================================================
# Workflow 1: AI Generation -> Draft in SQLite -> Immediate Text Post Publish
# ==============================================================================

def test_integration_text_post_ai_generate_save_draft_and_publish_now(
    temp_db, mock_gemini_client, mock_fb_service
):
    """E2E Workflow: User generates post via Gemini, saves draft, then immediately publishes."""
    # 1. Initialize GeminiService with mock client
    gemini_svc = GeminiService(api_key="mock_gemini_key", client=mock_gemini_client)

    topic = "Xu hướng công nghệ AI 2026"
    tone = "Chuyên gia"
    gen_result = gemini_svc.generate_fanpage_post(
        topic=topic,
        tone=tone,
        include_hashtags=True,
        use_search=True,
    )

    assert "ĐỘT PHÁ CÔNG NGHỆ" in gen_result["content"]
    assert len(gen_result["sources"]) == 2
    assert "https://news.example.com/ai-trends-2026" in gen_result["sources"]
    assert len(gen_result["suggested_hashtags"]) >= 3

    # 2. Save generated content as draft in SQLite database
    post_id = temp_db.save_post(
        topic=topic,
        content=gen_result["content"],
        image_path=None,
        status="draft",
    )
    assert post_id > 0

    draft_record = temp_db.get_post_by_id(post_id)
    assert draft_record is not None
    assert draft_record["status"] == "draft"
    assert draft_record["fb_post_id"] is None
    assert draft_record["content"] == gen_result["content"]

    # 3. User reviews post and clicks "Đăng ngay lên Fanpage"
    fb_response = mock_fb_service.publish_text_post(message=draft_record["content"])
    assert fb_response["id"] == "100200300400_post_text_111"

    # 4. Update database record with published status and Facebook post ID
    temp_db.update_post_status(
        post_id=post_id,
        status="published",
        fb_post_id=fb_response["id"],
    )

    # 5. Verify post in database
    published_record = temp_db.get_post_by_id(post_id)
    assert published_record["status"] == "published"
    assert published_record["fb_post_id"] == "100200300400_post_text_111"
    assert published_record["error_message"] is None
    mock_fb_service.publish_text_post.assert_called_once_with(
        message=draft_record["content"]
    )


# ==============================================================================
# Workflow 2: AI Generation -> Photo Upload -> Immediate Photo Post Publish
# ==============================================================================

def test_integration_photo_post_ai_generate_and_publish_now(
    temp_db, mock_gemini_client, mock_fb_service, tmp_path
):
    """E2E Workflow: User generates post, attaches photo, and publishes photo post."""
    # 1. Create a dummy test image
    test_image = tmp_path / "test_banner.jpg"
    test_image.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"A" * 1024)

    # 2. Generate content
    gemini_svc = GeminiService(api_key="mock_gemini_key", client=mock_gemini_client)
    gen_result = gemini_svc.generate_fanpage_post(
        topic="Sản phẩm công nghệ mới",
        tone="Hài hước",
        include_hashtags=True,
        use_search=False,
    )

    # 3. Save as draft with image_path
    post_id = temp_db.save_post(
        topic="Sản phẩm công nghệ mới",
        content=gen_result["content"],
        image_path=str(test_image),
        status="draft",
    )

    # 4. Publish photo post
    post_record = temp_db.get_post_by_id(post_id)
    fb_response = mock_fb_service.publish_photo_post(
        photo_path=post_record["image_path"],
        caption=post_record["content"],
    )
    published_fb_id = fb_response.get("post_id") or fb_response.get("id")
    assert published_fb_id == "100200300400_post_photo_222"

    # 5. Update database status
    temp_db.update_post_status(
        post_id=post_id,
        status="published",
        fb_post_id=published_fb_id,
    )

    # 6. Verify database record
    final_record = temp_db.get_post_by_id(post_id)
    assert final_record["status"] == "published"
    assert final_record["fb_post_id"] == "100200300400_post_photo_222"
    assert final_record["image_path"] == str(test_image)
    mock_fb_service.publish_photo_post.assert_called_once_with(
        photo_path=str(test_image),
        caption=post_record["content"],
    )


# ==============================================================================
# Workflow 3: Native Meta Facebook Graph API Scheduling Flow
# ==============================================================================

def test_integration_native_facebook_scheduled_post(
    temp_db, mock_fb_service
):
    """E2E Workflow: User schedules a post using Facebook Graph API native scheduling."""
    # Setup scheduled time 2 hours in the future
    now = datetime.now(timezone.utc)
    future_time = now + timedelta(hours=2)

    # Validate timing using ui_helpers
    is_valid, err_msg, timestamp = validate_schedule_datetime_fb(future_time, now=now)
    assert is_valid is True
    assert err_msg is None
    assert timestamp == int(future_time.timestamp())

    # Configure mock FB response for scheduled post
    mock_fb_service.publish_text_post.return_value = {
        "id": "100200300400_scheduled_post_777"
    }

    content = "Bài viết hẹn giờ tự động qua Facebook API native! #FanpageSchedule"
    topic = "Hẹn giờ Graph API"

    # Save to database as scheduled_fb
    post_id = temp_db.save_post(
        topic=topic,
        content=content,
        status="scheduled_fb",
        scheduled_time=future_time.isoformat(),
    )

    # Call Facebook service with scheduled_publish_time
    fb_response = mock_fb_service.publish_text_post(
        message=content,
        scheduled_publish_time=timestamp,
    )

    temp_db.update_post_status(
        post_id=post_id,
        status="scheduled_fb",
        fb_post_id=fb_response["id"],
    )

    # Verify database state
    record = temp_db.get_post_by_id(post_id)
    assert record["status"] == "scheduled_fb"
    assert record["fb_post_id"] == "100200300400_scheduled_post_777"
    assert record["scheduled_time"] == future_time.isoformat()
    mock_fb_service.publish_text_post.assert_called_once_with(
        message=content,
        scheduled_publish_time=timestamp,
    )


# ==============================================================================
# Workflow 4: Local APScheduler Scheduling & Automated Dispatch
# ==============================================================================

def test_integration_local_scheduler_service_full_workflow(
    temp_db, mock_fb_service
):
    """E2E Workflow: Post scheduled locally via APScheduler, executes job and updates SQLite."""
    scheduler_svc = LocalSchedulerService(
        db=temp_db,
        fb_service_provider=lambda: mock_fb_service,
    )

    content = "Bài đăng lên lịch ngầm bằng APScheduler máy tính cá nhân."
    topic = "Lên lịch Local"
    future_dt = datetime.now() + timedelta(seconds=10)

    # Save post as scheduled_local
    post_id = temp_db.save_post(
        topic=topic,
        content=content,
        status="scheduled_local",
        scheduled_time=future_dt.isoformat(),
    )

    with scheduler_svc:
        assert scheduler_svc.is_running

        # Schedule post
        job_id = scheduler_svc.schedule_post(post_id=post_id, run_date=future_dt)
        assert job_id == f"post_{post_id}"

        # Verify job is registered in APScheduler
        job = scheduler_svc.get_job(job_id)
        assert job is not None
        assert job.id == f"post_{post_id}"

        # Trigger execution directly via the service
        scheduler_svc.execute_post_job(post_id=post_id)

        # Verify post is published in DB
        updated_post = temp_db.get_post_by_id(post_id)
        assert updated_post["status"] == "published"
        assert updated_post["fb_post_id"] == "100200300400_post_text_111"
        assert updated_post["error_message"] is None

        mock_fb_service.publish_text_post.assert_called_once_with(message=content)


# ==============================================================================
# Workflow 5: Persistence Across App Restarts & Overdue Job Recovery
# ==============================================================================

def test_integration_local_scheduler_restart_and_recovery(
    temp_db, mock_fb_service
):
    """E2E Workflow: App restarts; pending local jobs are recovered from DB and rescheduled."""
    now = datetime.now()

    # Post 1: Future scheduled post (should be re-registered in APScheduler)
    future_time = now + timedelta(hours=3)
    p1_id = temp_db.save_post(
        topic="Bài tương lai",
        content="Nội dung bài tương lai",
        status="scheduled_local",
        scheduled_time=future_time.isoformat(),
    )

    # Post 2: Overdue post (scheduled in the past, e.g. PC was shut down)
    past_time = now - timedelta(hours=1)
    p2_id = temp_db.save_post(
        topic="Bài quá hạn",
        content="Nội dung bài quá hạn cần bù",
        status="scheduled_local",
        scheduled_time=past_time.isoformat(),
    )

    # Post 3: Already published post (should be completely untouched)
    p3_id = temp_db.save_post(
        topic="Bài đã xong",
        content="Nội dung đã đăng trước đó",
        status="published",
        fb_post_id="post_already_published",
    )

    # Simulate app startup with a brand new scheduler instance
    new_scheduler_svc = LocalSchedulerService(
        db=temp_db,
        fb_service_provider=lambda: mock_fb_service,
    )

    with new_scheduler_svc:
        # Load and reschedule pending jobs, executing overdue jobs
        rescheduled_count = new_scheduler_svc.load_and_reschedule_pending_jobs(
            execute_overdue=True
        )
        assert rescheduled_count == 2

        # Verify Post 1 is now active in APScheduler
        job1 = new_scheduler_svc.get_job(f"post_{p1_id}")
        assert job1 is not None

        # Verify Post 2 was executed immediately and updated to published
        post2 = temp_db.get_post_by_id(p2_id)
        assert post2["status"] == "published"
        assert post2["fb_post_id"] == "100200300400_post_text_111"

        # Verify Post 3 remained untouched
        post3 = temp_db.get_post_by_id(p3_id)
        assert post3["status"] == "published"
        assert post3["fb_post_id"] == "post_already_published"


# ==============================================================================
# Workflow 6: Local Scheduler Cancellation
# ==============================================================================

def test_integration_local_scheduler_cancellation(
    temp_db, mock_fb_service
):
    """E2E Workflow: User cancels a scheduled local post."""
    scheduler_svc = LocalSchedulerService(
        db=temp_db,
        fb_service_provider=lambda: mock_fb_service,
    )

    future_dt = datetime.now() + timedelta(hours=1)
    post_id = temp_db.save_post(
        topic="Bài sẽ bị hủy",
        content="Nội dung không muốn đăng nữa",
        status="scheduled_local",
        scheduled_time=future_dt.isoformat(),
    )

    with scheduler_svc:
        job_id = scheduler_svc.schedule_post(post_id=post_id, run_date=future_dt)
        assert scheduler_svc.get_job(job_id) is not None

        # User cancels post using job_id
        cancelled = scheduler_svc.cancel_scheduled_post(job_id=job_id)
        assert cancelled is True

        # Job is removed from APScheduler
        assert scheduler_svc.get_job(job_id) is None

        # Database record status is marked as 'cancelled'
        post = temp_db.get_post_by_id(post_id)
        assert post["status"] == "cancelled"


# ==============================================================================
# Workflow 7: Error Recovery - Facebook API Token Expiry & Subsequent Retry
# ==============================================================================

def test_integration_error_recovery_facebook_failure_then_retry(
    temp_db
):
    """E2E Workflow: Facebook publish fails with Token Error, post marked failed, then succeeds on retry."""
    # 1. Initialize DB and save draft
    post_id = temp_db.save_post(
        topic="Xử lý lỗi Token",
        content="Nội dung thử nghiệm phục hồi sự cố kết nối Facebook API",
        status="draft",
    )

    # 2. First publish attempt fails with FacebookTokenError (e.g. Code 190)
    failing_fb = MagicMock(spec=FacebookService)
    failing_fb.publish_text_post.side_effect = FacebookTokenError(
        message="Error validating access token: Session has expired",
        code=190,
    )

    try:
        failing_fb.publish_text_post(message="Nội dung thử nghiệm...")
    except FacebookAPIError as exc:
        temp_db.update_post_status(
            post_id=post_id,
            status="failed",
            error_message=str(exc),
        )

    # Verify status is failed with error message
    failed_record = temp_db.get_post_by_id(post_id)
    assert failed_record["status"] == "failed"
    assert "Code: 190" in failed_record["error_message"]

    # 3. User refreshes / renews access token and retries
    recovered_fb = MagicMock(spec=FacebookService)
    recovered_fb.publish_text_post.return_value = {"id": "recovered_fb_post_888"}

    res = recovered_fb.publish_text_post(message=failed_record["content"])
    temp_db.update_post_status(
        post_id=post_id,
        status="published",
        fb_post_id=res["id"],
    )

    # 4. Verify post is now successfully published with error cleared
    recovered_record = temp_db.get_post_by_id(post_id)
    assert recovered_record["status"] == "published"
    assert recovered_record["fb_post_id"] == "recovered_fb_post_888"
    assert recovered_record["error_message"] is None


# ==============================================================================
# Workflow 8: Error Handling - Gemini API Failure
# ==============================================================================

def test_integration_error_handling_gemini_api_failure():
    """E2E Workflow: Gemini API raises quota/network exception, handled without corruption."""
    failing_client = MagicMock()
    failing_client.models.generate_content.side_effect = RuntimeError(
        "ResourceExhausted: 429 Quota exceeded for gemini-2.5-flash"
    )

    service = GeminiService(api_key="mock_key", client=failing_client)

    with pytest.raises(RuntimeError, match="Quota exceeded"):
        service.generate_fanpage_post(topic="Bùng nổ công nghệ AI")


# ==============================================================================
# Workflow 9: Streamlit App UI End-to-End Test (AppTest)
# ==============================================================================

def test_integration_streamlit_apptest_full_ui_flow(monkeypatch, tmp_path):
    """E2E Streamlit App test: User interacts with Tab 1 to draft and Tab 2 to publish."""
    import streamlit as st
    st.cache_resource.clear()

    test_db_path = str(tmp_path / "test_app_e2e.db")
    monkeypatch.setenv("DB_PATH", test_db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "100200300400")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    mock_gen_result = {
        "content": "🚀 SIÊU TỰ ĐỘNG HÓA FANPAGE VỚI AI!\n\nNội dung được tạo tự động.",
        "sources": ["https://tech.example.com"],
        "suggested_hashtags": ["#AI", "#Automation"],
    }

    # Patch at the service module level so app.py is never imported directly by patch()
    with patch.object(GeminiService, "generate_fanpage_post", return_value=mock_gen_result), \
         patch.object(FacebookService, "publish_text_post", return_value={"id": "100200300400_ui_post_999"}):

        app_path = os.path.abspath("app.py")
        at = AppTest.from_file(app_path, default_timeout=15)
        at.run()
        assert not at.exception

        # Input topic
        at.text_area(key="topic_input_area").input("AI Marketing Tương Lai").run()
        assert not at.exception

        # Click generate button
        gen_btn = next(b for b in at.button if "Tìm kiếm & Viết bài ngay" in b.label)
        gen_btn.click().run()
        assert not at.exception

        # Verify content populated
        assert "SIÊU TỰ ĐỘNG HÓA FANPAGE" in at.session_state.post_content

        # Save as draft
        save_draft_btn = next(b for b in at.button if "Lưu làm Bản nháp" in b.label)
        save_draft_btn.click().run()
        assert not at.exception

        # Verify draft saved in DB
        db = DatabaseManager(db_path=test_db_path)
        posts = db.get_all_posts()
        assert len(posts) >= 1
        assert posts[0]["status"] == "draft"

        # Now click Publish Now in Tab 2
        publish_btn = next(b for b in at.button if "Xuất bản ngay bây giờ" in b.label)
        publish_btn.click().run()
        assert not at.exception

        # Verify post is published in DB
        updated_posts = db.get_all_posts()
        assert any(p["status"] == "published" for p in updated_posts)


def test_integration_openrouter_full_workflow(temp_db):
    """Test full workflow using OpenRouterService: Generate -> Save Draft -> Publish to Facebook."""
    openrouter_response = {
        "id": "gen-openrouter-test",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "🚀 TOP 3 CÁCH BẢO VỆ MÁY TÍNH KHỎI VIRUS ĐỘC HẠI! 🛡️\n\n"
                        "Bạn có biết mỗi ngày có hàng ngàn mã độc tấn công máy tính cá nhân?\n\n"
                        "📌 Cần lưu ý:\n"
                        "• Không bấm vào link lạ trong email\n"
                        "• Cập nhật Windows Defender thường xuyên\n\n"
                        "👉 Liên hệ Sửa Máy Tính BMT để được hỗ trợ tận nơi!\n\n"
                        "#BaoVeMayTinh #AnNinhMang #SuaMayTinhBMT"
                    ),
                }
            }
        ],
        "citations": ["https://security.googleblog.com"],
    }

    mock_fb_response = {"id": "619960427857965_9876543210"}

    with patch("requests.post") as mock_post:
        # First post call is OpenRouter generate
        # Second post call is Facebook publish
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: openrouter_response),
            MagicMock(status_code=200, json=lambda: mock_fb_response),
        ]

        # 1. Generate post with OpenRouterService
        or_svc = OpenRouterService(api_key="sk-or-v1-mock-key", model="deepseek/deepseek-chat:free")
        generated = or_svc.generate_fanpage_post(
            topic="Cách bảo vệ máy tính khỏi virus",
            tone="chuyên gia",
            include_hashtags=True,
            use_search=True,
        )

        assert "TOP 3 CÁCH BẢO VỆ MÁY TÍNH" in generated["content"]
        assert len(generated["sources"]) == 1
        assert "#SuaMayTinhBMT" in generated["suggested_hashtags"]

        # 2. Save as draft in SQLite Database
        post_id = temp_db.save_post(
            topic="Cách bảo vệ máy tính khỏi virus",
            content=generated["content"],
            image_path=None,
            status="draft",
        )
        assert post_id > 0
        saved_post = temp_db.get_post_by_id(post_id)
        assert saved_post["status"] == "draft"

        # 3. Publish to Facebook Fanpage
        fb_svc = FacebookService(page_id="619960427857965", access_token="mock_valid_token")
        pub_res = fb_svc.publish_text_post(message=saved_post["content"])
        assert pub_res["id"] == "619960427857965_9876543210"

        # 4. Update status in Database
        temp_db.update_post_status(post_id=post_id, status="published", fb_post_id=pub_res["id"])
        final_post = temp_db.get_post_by_id(post_id)
        assert final_post["status"] == "published"
        assert final_post["fb_post_id"] == "619960427857965_9876543210"

