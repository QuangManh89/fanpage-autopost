"""Smoke and UI interaction tests for app.py using Streamlit AppTest framework."""

import os
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




def test_tab5_fb_token_tool_exchange_and_add_to_db(monkeypatch, tmp_path):
    """Verify FB Token Tool in Tab 5 exchanges token, displays pages, and adds to SQLite."""
    import streamlit as st
    from unittest.mock import patch
    st.cache_resource.clear()
    test_db_path = str(tmp_path / "test_fb_tool.db")
    monkeypatch.setenv("DB_PATH", test_db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_token")
    monkeypatch.setenv("FB_APP_ID", "3711376692339694")
    monkeypatch.setenv("FB_APP_SECRET", "test_secret_32chars")

    mock_long_res = {"access_token": "EAAB_mock_long_user_token", "expires_in": 5184000}
    mock_accounts = [
        {
            "id": "619960427857965",
            "name": "Sửa Máy Tính Tại Nhà BMT",
            "access_token": "EAAB_mock_permanent_page_token",
            "category": "Computer Repair",
        }
    ]

    with patch("src.facebook_service.FacebookService.exchange_token_to_long_lived", return_value=mock_long_res), \
         patch("src.facebook_service.FacebookService.get_user_accounts", return_value=mock_accounts):

        app_path = os.path.abspath("app.py")
        at = AppTest.from_file(app_path, default_timeout=15)
        at.run()
        assert not at.exception

        at.text_area(key="fb_tool_short_token").input("EAA_short_lived_user_tok").run()
        assert not at.exception

        at.button(key="fb_tool_btn_exchange_all").click().run()
        assert not at.exception

        assert at.session_state["tool_long_token"] == "EAAB_mock_long_user_token"
        assert len(at.session_state["tool_found_pages"]) == 1
        assert at.session_state["tool_found_pages"][0]["id"] == "619960427857965"

        at.button(key="add_db_p_619960427857965_0").click().run()
        assert not at.exception

        db = DatabaseManager(db_path=test_db_path)
        fps = db.get_fanpages()
        target_fp = next((fp for fp in fps if fp["page_id"] == "619960427857965"), None)
        assert target_fp is not None
        assert target_fp["page_name"] == "Sửa Máy Tính Tại Nhà BMT"
        assert target_fp["access_token"] == "EAAB_mock_permanent_page_token"



def test_app_password_gate_and_unlock(monkeypatch, tmp_path):
    """Verify that setting APP_PASSWORD displays the login gate and unlocking reveals the dashboard."""
    import streamlit as st
    st.cache_resource.clear()
    test_db_path = str(tmp_path / "test_auth_gate.db")
    monkeypatch.setenv("DB_PATH", test_db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")
    monkeypatch.setenv("APP_PASSWORD", "SecretPass2026")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()
    assert not at.exception

    # Gate is active, tabs are not rendered
    assert len(at.tabs) == 0

    # Wrong password attempt
    at.text_input(key="pwd_login_input").input("WrongPassword").run()
    # Find submit button in login form
    login_btn = next(b for b in at.button if "Mở khóa bảng điều khiển" in b.label)
    login_btn.click().run()
    assert not at.exception
    assert at.session_state.get("authenticated") is not True
    assert len(at.tabs) == 0

    # Correct password attempt
    at.text_input(key="pwd_login_input").input("SecretPass2026").run()
    login_btn = next(b for b in at.button if "Mở khóa bảng điều khiển" in b.label)
    login_btn.click().run()
    assert not at.exception
    assert at.session_state.get("authenticated") is True
    assert len(at.tabs) == 5



def test_app_humanize_rewrite_and_undo(monkeypatch, tmp_path):
    """Verify Humanize AI rewrite button updates content and undo button restores previous content."""
    import streamlit as st
    from unittest.mock import patch
    st.cache_resource.clear()
    test_db_path = str(tmp_path / "test_humanize.db")
    monkeypatch.setenv("DB_PATH", test_db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    with patch("src.gemini_service.GeminiService.rewrite_content", return_value="Nội dung đã được biên tập mượt mà như người thật."):
        app_path = os.path.abspath("app.py")
        at = AppTest.from_file(app_path, default_timeout=15)
        at.run()
        assert not at.exception

        # Input initial content
        original_text = "Nội dung ban đầu hơi máy móc và đều câu."
        at.text_area(key="content_editor_area").input(original_text).run()
        assert not at.exception

        # Click rewrite button
        at.button(key="btn_do_rewrite").click().run()
        assert not at.exception

        # Verify content was updated and previous content stored
        assert at.session_state["post_content"] == "Nội dung đã được biên tập mượt mà như người thật."
        assert at.session_state["previous_post_content"] == original_text

        # Click undo button
        at.button(key="btn_undo_rewrite").click().run()
        assert not at.exception

        # Verify previous content was restored
        assert at.session_state["post_content"] == original_text
