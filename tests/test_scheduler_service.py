"""Unit tests for LocalSchedulerService (APScheduler local post scheduling)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from src.database import DatabaseManager
from src.facebook_service import FacebookAPIError, FacebookService, FacebookTokenError
from src.scheduler_service import LocalSchedulerService


@pytest.fixture
def temp_db(tmp_path):
    """Provide a temporary SQLite DatabaseManager."""
    db_file = tmp_path / "test_scheduler.db"
    return DatabaseManager(db_path=str(db_file))


@pytest.fixture
def mock_fb_service():
    """Provide a mock FacebookService."""
    mock = create_autospec(FacebookService, instance=True)
    mock.publish_text_post.return_value = {"id": "123456_text_post_id"}
    mock.publish_photo_post.return_value = {
        "id": "photo_id_789",
        "post_id": "123456_photo_post_id",
    }
    return mock


@pytest.fixture
def scheduler_service(temp_db, mock_fb_service):
    """Provide a LocalSchedulerService instance and ensure shutdown on teardown."""
    service = LocalSchedulerService(
        db=temp_db,
        fb_service_provider=lambda: mock_fb_service,
    )
    yield service
    if service.is_running:
        service.shutdown(wait=False)


def test_scheduler_init(temp_db, mock_fb_service):
    """Test LocalSchedulerService initialization and default states."""
    service = LocalSchedulerService(
        db=temp_db,
        fb_service_provider=lambda: mock_fb_service,
    )
    assert not service.is_running
    assert service.db is temp_db


def test_scheduler_start_and_shutdown(scheduler_service):
    """Test starting and stopping the background scheduler."""
    assert not scheduler_service.is_running
    scheduler_service.start()
    assert scheduler_service.is_running

    scheduler_service.shutdown(wait=False)
    assert not scheduler_service.is_running


def test_context_manager_lifecycle(temp_db, mock_fb_service):
    """Test LocalSchedulerService with-statement context manager support."""
    with LocalSchedulerService(temp_db, lambda: mock_fb_service) as service:
        assert service.is_running
    assert not service.is_running


def test_schedule_text_post_success(scheduler_service, temp_db, mock_fb_service):
    """Test scheduling a text-only post and executing the job."""
    post_id = temp_db.save_post(
        topic="Công nghệ AI",
        content="Nội dung bài viết AI ngày mai",
        status="draft",
    )

    run_date = datetime.now() + timedelta(hours=2)
    job_id = scheduler_service.schedule_post(post_id=post_id, run_date=run_date)

    assert job_id == f"post_{post_id}"
    job = scheduler_service.get_job(job_id)
    assert job is not None

    # Check database status was updated to scheduled_local
    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "scheduled_local"

    # Manually execute the job to verify publishing logic
    success = scheduler_service.execute_post_job(post_id)
    assert success is True

    mock_fb_service.publish_text_post.assert_called_once_with(
        message="Nội dung bài viết AI ngày mai"
    )
    mock_fb_service.publish_photo_post.assert_not_called()

    # Verify DB updated to published with fb_post_id
    updated_post = temp_db.get_post_by_id(post_id)
    assert updated_post["status"] == "published"
    assert updated_post["fb_post_id"] == "123456_text_post_id"
    assert updated_post["error_message"] is None


def test_schedule_photo_post_success(
    scheduler_service, temp_db, mock_fb_service, tmp_path
):
    """Test scheduling a post with an image and executing the job."""
    img_file = tmp_path / "test_banner.jpg"
    img_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 200)

    post_id = temp_db.save_post(
        topic="Sự kiện ra mắt",
        content="Ảnh thực tế sản phẩm",
        image_path=str(img_file),
        status="draft",
    )

    run_date = datetime.now() + timedelta(days=1)
    job_id = scheduler_service.schedule_post(post_id=post_id, run_date=run_date)

    assert job_id == f"post_{post_id}"

    # Execute post job
    success = scheduler_service.execute_post_job(post_id)
    assert success is True

    mock_fb_service.publish_photo_post.assert_called_once_with(
        message="Ảnh thực tế sản phẩm",
        photo_path=str(img_file),
    )
    mock_fb_service.publish_text_post.assert_not_called()

    updated_post = temp_db.get_post_by_id(post_id)
    assert updated_post["status"] == "published"
    assert updated_post["fb_post_id"] == "123456_photo_post_id"


def test_schedule_nonexistent_post_raises_error(scheduler_service):
    """Scheduling a post_id not found in DB should raise ValueError."""
    future_date = datetime.now() + timedelta(hours=1)
    with pytest.raises(ValueError, match="Không tìm thấy bài viết"):
        scheduler_service.schedule_post(post_id=99999, run_date=future_date)


def test_cancel_scheduled_post_success(scheduler_service, temp_db):
    """Test cancelling an existing scheduled job."""
    post_id = temp_db.save_post(
        topic="Hủy đăng",
        content="Bài viết cần hủy lịch",
        status="draft",
    )
    run_date = datetime.now() + timedelta(hours=3)
    job_id = scheduler_service.schedule_post(post_id=post_id, run_date=run_date)

    assert scheduler_service.get_job(job_id) is not None

    # Cancel by job_id
    cancelled = scheduler_service.cancel_scheduled_post(job_id)
    assert cancelled is True
    assert scheduler_service.get_job(job_id) is None

    # DB post status should be cancelled
    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "cancelled"


def test_cancel_nonexistent_job_returns_false(scheduler_service):
    """Cancelling a job that does not exist should return False."""
    assert scheduler_service.cancel_scheduled_post("non_existent_job_id") is False


def test_execute_post_job_skips_if_already_published(
    scheduler_service, temp_db, mock_fb_service
):
    """Job execution must not republish if post is already marked published."""
    post_id = temp_db.save_post(
        topic="Đã đăng rồi",
        content="Nội dung đã đăng",
        status="published",
        fb_post_id="existing_id_111",
    )

    success = scheduler_service.execute_post_job(post_id)
    assert success is False
    mock_fb_service.publish_text_post.assert_not_called()
    mock_fb_service.publish_photo_post.assert_not_called()


def test_execute_post_job_skips_if_cancelled(
    scheduler_service, temp_db, mock_fb_service
):
    """Job execution must not publish if post was cancelled."""
    post_id = temp_db.save_post(
        topic="Đã hủy",
        content="Nội dung hủy",
        status="cancelled",
    )

    success = scheduler_service.execute_post_job(post_id)
    assert success is False
    mock_fb_service.publish_text_post.assert_not_called()


def test_execute_post_job_handles_facebook_api_error(
    scheduler_service, temp_db, mock_fb_service
):
    """When Facebook API fails, DB status is updated to failed without crashing."""
    mock_fb_service.publish_text_post.side_effect = FacebookTokenError(
        message="Token expired",
        code=190,
        user_message="Token Fanpage đã hết hạn.",
    )

    post_id = temp_db.save_post(
        topic="Lỗi token",
        content="Nội dung thử nghiệm lỗi",
        status="scheduled_local",
    )

    success = scheduler_service.execute_post_job(post_id)
    assert success is False

    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "failed"
    assert "Token Fanpage đã hết hạn" in post["error_message"]


def test_execute_post_job_missing_photo_file_fails(
    scheduler_service, temp_db, mock_fb_service
):
    """When image_path does not exist on disk, job fails safely."""
    mock_fb_service.publish_photo_post.side_effect = FileNotFoundError(
        "Không tìm thấy file ảnh: missing_file.jpg"
    )

    post_id = temp_db.save_post(
        topic="Mất ảnh",
        content="Bài viết bị mất file ảnh",
        image_path="missing_file.jpg",
        status="scheduled_local",
    )

    success = scheduler_service.execute_post_job(post_id)
    assert success is False

    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "failed"
    assert "Không tìm thấy file ảnh" in post["error_message"]


def test_load_and_reschedule_pending_jobs(scheduler_service, temp_db):
    """Test restoring pending scheduled posts from DB on service restart."""
    now = datetime.now()
    future_time_1 = (now + timedelta(hours=2)).isoformat()
    future_time_2 = (now + timedelta(days=2)).isoformat()
    past_time = (now - timedelta(hours=1)).isoformat()

    # 1. Post in future 1
    p1 = temp_db.save_post(
        topic="Tương lai 1",
        content="Post 1",
        status="scheduled_local",
        scheduled_time=future_time_1,
    )
    # 2. Post in future 2
    p2 = temp_db.save_post(
        topic="Tương lai 2",
        content="Post 2",
        status="scheduled_local",
        scheduled_time=future_time_2,
    )
    # 3. Post in past (overdue)
    p3 = temp_db.save_post(
        topic="Quá hạn",
        content="Post 3 quá hạn",
        status="scheduled_local",
        scheduled_time=past_time,
    )
    # 4. Normal draft post (should not be touched)
    p4 = temp_db.save_post(
        topic="Bản nháp",
        content="Post draft",
        status="draft",
    )

    rescheduled = scheduler_service.load_and_reschedule_pending_jobs()

    # Future posts (p1, p2) should be rescheduled -> count 2
    assert rescheduled == 2
    assert scheduler_service.get_job(f"post_{p1}") is not None
    assert scheduler_service.get_job(f"post_{p2}") is not None

    # Overdue post (p3) should NOT be scheduled, but marked failed
    assert scheduler_service.get_job(f"post_{p3}") is None
    post3 = temp_db.get_post_by_id(p3)
    assert post3["status"] == "failed"
    assert "quá hạn" in post3["error_message"].lower() or "đã qua" in post3["error_message"].lower()

    # Draft post remains untouched
    post4 = temp_db.get_post_by_id(p4)
    assert post4["status"] == "draft"


def test_load_and_reschedule_invalid_scheduled_time(scheduler_service, temp_db):
    """Post with unparseable scheduled_time should be marked failed gracefully."""
    post_id = temp_db.save_post(
        topic="Lỗi ngày giờ",
        content="Thời gian sai định dạng",
        status="scheduled_local",
        scheduled_time="invalid-date-format",
    )

    rescheduled = scheduler_service.load_and_reschedule_pending_jobs()
    assert rescheduled == 0

    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "failed"
    assert "định dạng" in post["error_message"].lower() or "invalid" in post["error_message"].lower()


def test_direct_facebook_service_instance_provider(temp_db, mock_fb_service):
    """Support passing FacebookService directly instead of a factory function."""
    service = LocalSchedulerService(
        db=temp_db,
        fb_service_provider=mock_fb_service,
    )
    post_id = temp_db.save_post(topic="Direct", content="Direct service provider", status="draft")
    success = service.execute_post_job(post_id)
    assert success is True
    mock_fb_service.publish_text_post.assert_called_once()

def test_load_and_reschedule_with_execute_overdue(scheduler_service, temp_db, mock_fb_service):
    """Test load_and_reschedule_pending_jobs with execute_overdue=True."""
    past_time = (datetime.now() - timedelta(minutes=15)).isoformat()
    post_id = temp_db.save_post(
        topic="Đăng bù",
        content="Nội dung đăng bù",
        status="scheduled_local",
        scheduled_time=past_time,
    )

    rescheduled = scheduler_service.load_and_reschedule_pending_jobs(execute_overdue=True)
    assert rescheduled == 1

    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "published"
    mock_fb_service.publish_text_post.assert_called_once_with(message="Nội dung đăng bù")


def test_schedule_post_with_iso_string(scheduler_service, temp_db):
    """Test scheduling with an ISO datetime string."""
    post_id = temp_db.save_post(topic="ISO String", content="ISO format test", status="draft")
    iso_time = (datetime.now() + timedelta(hours=5)).isoformat()
    job_id = scheduler_service.schedule_post(post_id=post_id, run_date=iso_time)

    assert job_id == f"post_{post_id}"
    assert scheduler_service.get_job(job_id) is not None


def test_idempotent_start_and_shutdown(scheduler_service):
    """Calling start() or shutdown() multiple times should be idempotent."""
    scheduler_service.start()
    scheduler_service.start()  # should not raise
    assert scheduler_service.is_running

    scheduler_service.shutdown(wait=False)
    scheduler_service.shutdown(wait=False)  # should not raise
    assert not scheduler_service.is_running


def test_execute_post_job_provider_exception(temp_db):
    """Test handling when fb_service_provider raises an exception."""
    def failing_provider():
        raise RuntimeError("Không thể kết nối cấu hình FB")

    service = LocalSchedulerService(db=temp_db, fb_service_provider=failing_provider)
    post_id = temp_db.save_post(topic="Fail Provider", content="Fail content", status="scheduled_local")

    success = service.execute_post_job(post_id)
    assert success is False

    post = temp_db.get_post_by_id(post_id)
    assert post["status"] == "failed"
    assert "Không thể lấy FacebookService" in post["error_message"]


def test_background_scheduler_real_trigger(temp_db, mock_fb_service):
    """End-to-end test verifying APScheduler background thread fires and completes."""
    import time

    service = LocalSchedulerService(db=temp_db, fb_service_provider=mock_fb_service)
    service.start()
    try:
        post_id = temp_db.save_post(
            topic="Real trigger",
            content="Nội dung real trigger",
            status="draft",
        )
        # Schedule 0.5s into the future
        run_date = datetime.now() + timedelta(seconds=0.5)
        service.schedule_post(post_id=post_id, run_date=run_date)

        # Wait up to 3 seconds for background execution
        for _ in range(30):
            post = temp_db.get_post_by_id(post_id)
            if post["status"] == "published":
                break
            time.sleep(0.1)

        post = temp_db.get_post_by_id(post_id)
        assert post["status"] == "published"
        assert post["fb_post_id"] is not None
    finally:
        service.shutdown(wait=False)
