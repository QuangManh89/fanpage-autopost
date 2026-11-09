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


def test_fanpage_crud_and_conflict(db):
    # Add fanpage
    fp_id = db.add_fanpage(
        page_id="123456789",
        page_name="Sửa Máy Tính BMT",
        access_token="EAAB1234",
        is_active=1,
    )
    assert fp_id > 0

    # Retrieve by page_id
    page = db.get_fanpage_by_page_id("123456789")
    assert page is not None
    assert page["page_name"] == "Sửa Máy Tính BMT"
    assert page["access_token"] == "EAAB1234"
    assert page["is_active"] == 1

    # Conflict / update on add_fanpage with same page_id
    db.add_fanpage(
        page_id="123456789",
        page_name="Sửa Máy Tính BMT Mới",
        access_token="EAAB9999",
        is_active=1,
    )
    updated = db.get_fanpage_by_page_id("123456789")
    assert updated["page_name"] == "Sửa Máy Tính BMT Mới"
    assert updated["access_token"] == "EAAB9999"

    # Explicit update_fanpage
    db.update_fanpage("123456789", page_name="Sửa Máy Tính Đắk Lắk", is_active=0)
    page_mod = db.get_fanpage_by_page_id("123456789")
    assert page_mod["page_name"] == "Sửa Máy Tính Đắk Lắk"
    assert page_mod["is_active"] == 0

    # Delete fanpage
    assert db.delete_fanpage("123456789") is True
    assert db.get_fanpage_by_page_id("123456789") is None
    assert db.delete_fanpage("123456789") is False


def test_fanpage_toggle_and_filter_active(db):
    db.add_fanpage("p1", "Page 1", "tok1", is_active=1)
    db.add_fanpage("p2", "Page 2", "tok2", is_active=0)

    # All pages
    all_pages = db.get_fanpages(only_active=False)
    assert len(all_pages) == 2

    # Only active
    active_pages = db.get_fanpages(only_active=True)
    assert len(active_pages) == 1
    assert active_pages[0]["page_id"] == "p1"

    # Toggle p1 to inactive
    assert db.toggle_fanpage_status("p1") is True
    active_now = db.get_fanpages(only_active=True)
    assert len(active_now) == 0

    # Toggle p2 to active
    assert db.toggle_fanpage_status("p2") is True
    active_now2 = db.get_fanpages(only_active=True)
    assert len(active_now2) == 1
    assert active_now2[0]["page_id"] == "p2"


def test_migrate_from_env(db):
    # Empty db, migration succeeds
    success = db.migrate_from_env("env_pid_1", "env_tok_1", "Env Page")
    assert success is True
    page = db.get_fanpage_by_page_id("env_pid_1")
    assert page is not None
    assert page["page_name"] == "Env Page"

    # Second migration with same id does not duplicate
    success2 = db.migrate_from_env("env_pid_1", "env_tok_1", "Env Page")
    assert success2 is False

    # Empty inputs return False
    assert db.migrate_from_env("", "tok") is False
    assert db.migrate_from_env("pid", "") is False


def test_save_post_with_page_info_and_filter(db):
    id1 = db.save_post(
        topic="Post 1",
        content="Content 1",
        page_id="page_a",
        page_name="Page Alpha",
    )
    id2 = db.save_post(
        topic="Post 2",
        content="Content 2",
        page_id="page_b",
        page_name="Page Beta",
    )

    p1 = db.get_post_by_id(id1)
    assert p1["page_id"] == "page_a"
    assert p1["page_name"] == "Page Alpha"

    # Filter get_all_posts by page_id
    posts_a = db.get_all_posts(page_id="page_a")
    assert len(posts_a) == 1
    assert posts_a[0]["id"] == id1

    posts_b = db.get_all_posts(page_id="page_b")
    assert len(posts_b) == 1
    assert posts_b[0]["id"] == id2

    all_posts = db.get_all_posts()
    assert len(all_posts) >= 2


def test_database_migration_from_legacy_schema(tmp_path):
    import sqlite3
    db_file = tmp_path / "legacy.db"

    # Create an old schema without page_id / page_name
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
    CREATE TABLE posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        content TEXT NOT NULL,
        image_path TEXT,
        status TEXT NOT NULL,
        scheduled_time TEXT,
        fb_post_id TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.execute("INSERT INTO posts (topic, content, status) VALUES ('Legacy', 'Legacy content', 'draft');")
    conn.commit()
    conn.close()

    # Now load with DatabaseManager which should trigger ALTER TABLE migration
    manager = DatabaseManager(db_path=str(db_file))
    posts = manager.get_all_posts()
    assert len(posts) == 1
    assert "page_id" in posts[0]
    assert "page_name" in posts[0]
    assert posts[0]["page_id"] is None


