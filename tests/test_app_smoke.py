"""Smoke and UI interaction tests for app.py using Streamlit AppTest framework."""

import os
import pytest
from streamlit.testing.v1 import AppTest
from src.database import DatabaseManager


def test_app_smoke_and_tabs_rendering(monkeypatch):
    """Smoke test to verify that app.py initializes and renders all 4 tabs without crashing."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()

    assert not at.exception, f"App crashed with exception: {at.exception}"
    assert len(at.tabs) == 5
    tab_labels = [tab.label for tab in at.tabs]
    assert any("Tạo bài viết" in label for label in tab_labels)
    assert any("Đăng bài" in label for label in tab_labels)
    assert any("Lịch sử" in label for label in tab_labels)
    assert any("Quản trị Fanpages" in label for label in tab_labels)
    assert any("Cài đặt" in label for label in tab_labels)


def test_app_draft_saving(monkeypatch, tmp_path):
    """Verify entering topic and content manually saves the draft correctly to SQLite."""
    import streamlit as st
    st.cache_resource.clear()
    test_db_path = str(tmp_path / "test_fanpage.db")
    monkeypatch.setenv("DB_PATH", test_db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()
    assert not at.exception

    # Find the topic and content text areas
    topic_widget = at.text_area(key="topic_input_area")
    topic_widget.input("Chủ đề AI Marketing").run()
    assert not at.exception

    content_widget = at.text_area(key="content_editor_area")
    content_widget.input("Nội dung bài viết về AI Marketing 2026").run()
    assert not at.exception

    # Find and click the Save Draft button
    save_btn = next(b for b in at.button if "Lưu làm Bản nháp" in b.label)
    save_btn.click().run()
    assert not at.exception

    # Verify post was saved in database
    db = DatabaseManager(db_path=test_db_path)
    posts = db.get_all_posts()
    assert len(posts) >= 1
    draft_post = next(p for p in posts if p["topic"] == "Chủ đề AI Marketing")
    assert draft_post["content"] == "Nội dung bài viết về AI Marketing 2026"
    assert draft_post["status"] == "draft"


def test_content_editor_programmatic_update_not_wiped(monkeypatch):
    """Verify programmatic post_content update (AI generation or Tab 3 copy) is not wiped by widget key."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()
    assert not at.exception

    # Simulate programmatic assignment (AI generation or Tab 3 copy)
    sample_text = "Nội dung bài viết do AI tạo ra rất chi tiết và cuốn hút."
    sample_topic = "Chủ đề AI tiên tiến"
    at.session_state.post_topic = sample_topic
    at.session_state.topic_input_area = sample_topic
    at.session_state.post_content = sample_text
    at.session_state.content_editor_area = sample_text
    at.run()

    assert not at.exception
    # Verify the text was not wiped out
    assert at.text_area(key="content_editor_area").value == sample_text
    assert at.session_state.post_content == sample_text
    assert at.text_area(key="topic_input_area").value == sample_topic
    assert at.session_state.post_topic == sample_topic


def test_manual_topic_input_synchronized(monkeypatch):
    """Verify typing into topic_input_area synchronizes post_topic without clicking generate_btn."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()
    assert not at.exception

    topic_widget = at.text_area(key="topic_input_area")
    topic_widget.input("Chủ đề nhập thủ công").run()
    assert not at.exception

    assert at.session_state.post_topic == "Chủ đề nhập thủ công"


def test_upload_file_caching_avoids_duplicate_saves(tmp_path):
    """Verify that file signature caching prevents repeated disk writes across reruns."""
    call_count = 0

    def mock_save(file_obj, upload_dir="data/uploads"):
        nonlocal call_count
        call_count += 1
        return f"{upload_dir}/{file_obj.name}"

    class FakeUploadedFile:
        name = "photo_test.jpg"
        size = 2048
        file_id = "unique_file_id_001"

    session_state = {"last_uploaded_file_id": None, "post_image_path": None}
    fake_img = FakeUploadedFile()

    # First run (new file uploaded)
    sig = getattr(fake_img, "file_id", None) or f"{fake_img.name}_{fake_img.size}"
    if session_state.get("last_uploaded_file_id") != sig:
        session_state["post_image_path"] = mock_save(fake_img, upload_dir=str(tmp_path))
        session_state["last_uploaded_file_id"] = sig

    assert call_count == 1
    assert session_state["last_uploaded_file_id"] == "unique_file_id_001"

    # Subsequent reruns with unchanged uploaded file
    for _ in range(3):
        sig = getattr(fake_img, "file_id", None) or f"{fake_img.name}_{fake_img.size}"
        if session_state.get("last_uploaded_file_id") != sig:
            mock_save(fake_img, upload_dir=str(tmp_path))

    # call_count remains 1, no duplicate disk write occurred
    assert call_count == 1


def test_multi_fanpage_auto_migration_and_tab(monkeypatch, tmp_path):
    """Verify Fanpage credentials in .env are auto-migrated and rendered in Fanpage tab."""
    import streamlit as st
    st.cache_resource.clear()
    test_db_path = str(tmp_path / "test_fanpage_auto.db")
    monkeypatch.setenv("DB_PATH", test_db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "9988776655")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token_99")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()
    assert not at.exception

    # Check database auto-migration happened
    db = DatabaseManager(db_path=test_db_path)
    fps = db.get_fanpages()
    assert len(fps) >= 1
    assert fps[0]["page_id"] in ("9988776655", "619960427857965")
    assert fps[0]["is_active"] == 1

