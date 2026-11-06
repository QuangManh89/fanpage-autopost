import pytest
from src.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "subfolder" / "test_fanpage.db"
    manager = DatabaseManager(db_path=str(db_file))
    return manager


def test_init_db_creates_table_and_directory(tmp_path):
    db_file = tmp_path / "nested" / "dir" / "test.db"
    manager = DatabaseManager(db_path=str(db_file))
    manager.init_db()
    assert db_file.exists()

    # Verify we can query posts table without error
    posts = manager.get_all_posts()
    assert posts == []


def test_save_and_get_post_by_id(db):
    post_id = db.save_post(
        topic="Công nghệ AI",
        content="Nội dung bài viết về AI trong năm 2026",
        image_path="images/ai_news.png",
        status="draft",
        scheduled_time=None,
        fb_post_id=None,
    )
    assert isinstance(post_id, int)
    assert post_id > 0

    post = db.get_post_by_id(post_id)
    assert post is not None
    assert post["id"] == post_id
    assert post["topic"] == "Công nghệ AI"
    assert post["content"] == "Nội dung bài viết về AI trong năm 2026"
    assert post["image_path"] == "images/ai_news.png"
    assert post["status"] == "draft"
    assert post["scheduled_time"] is None
    assert post["fb_post_id"] is None
    assert post["created_at"] is not None
    assert post["updated_at"] is not None


def test_get_nonexistent_post(db):
    post = db.get_post_by_id(99999)
    assert post is None


def test_update_post_status(db):
    post_id = db.save_post(
        topic="Sự kiện",
        content="Chuẩn bị đăng bài",
        image_path=None,
        status="scheduled_fb",
        scheduled_time="2026-11-07 10:00:00",
        fb_post_id=None,
    )

    db.update_post_status(
        post_id=post_id,
        status="published",
        fb_post_id="123456_789012",
        error_message=None,
    )

    updated = db.get_post_by_id(post_id)
    assert updated["status"] == "published"
    assert updated["fb_post_id"] == "123456_789012"
    assert updated["error_message"] is None

    # Test error update
    db.update_post_status(
        post_id=post_id,
        status="failed",
        error_message="OAuthException: Invalid token",
    )
    failed_post = db.get_post_by_id(post_id)
    assert failed_post["status"] == "failed"
    assert failed_post["error_message"] == "OAuthException: Invalid token"


def test_get_all_posts(db):
    for i in range(5):
        db.save_post(
            topic=f"Topic {i}",
            content=f"Content {i}",
            image_path=None,
            status="draft",
            scheduled_time=None,
            fb_post_id=None,
        )

    all_posts = db.get_all_posts(limit=3)
    assert len(all_posts) == 3

    all_posts_unlimited = db.get_all_posts(limit=50)
    assert len(all_posts_unlimited) == 5
    # Check descending order by id/created_at
    assert all_posts_unlimited[0]["id"] > all_posts_unlimited[1]["id"]


def test_get_pending_local_scheduled_posts(db):
    db.save_post("Topic 1", "Draft post", None, "draft", None, None)
    id_local_1 = db.save_post(
        "Topic 2", "Local scheduled 1", None, "scheduled_local", "2026-11-06 12:00:00", None
    )
    id_local_2 = db.save_post(
        "Topic 3", "Local scheduled 2", None, "scheduled_local", "2026-11-06 14:00:00", None
    )
    db.save_post("Topic 4", "FB scheduled", None, "scheduled_fb", "2026-11-06 15:00:00", "fb_id_1")
    db.save_post("Topic 5", "Published", None, "published", None, "fb_id_2")

    pending = db.get_pending_local_scheduled_posts()
    assert len(pending) == 2
    pending_ids = [p["id"] for p in pending]
    assert id_local_1 in pending_ids
    assert id_local_2 in pending_ids


def test_delete_post(db):
    post_id = db.save_post("Test delete", "Content", None, "draft")
    assert db.get_post_by_id(post_id) is not None

    deleted = db.delete_post(post_id)
    assert deleted is True
    assert db.get_post_by_id(post_id) is None

    # Deleting non-existent post returns False
    assert db.delete_post(post_id) is False

