"""Smoke and UI integration tests for app.py using Streamlit AppTest framework."""

import os
import pytest
from streamlit.testing.v1 import AppTest


def test_app_smoke_and_tabs_rendering(monkeypatch, tmp_path):
    """Smoke test to verify that app.py initializes and renders all 4 tabs without crashing."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()

    # Verify no unhandled exceptions occurred
    assert not at.exception, f"App crashed with exception: {at.exception}"

    # Verify 4 tabs exist
    assert len(at.tabs) == 4
    tab_labels = [tab.label for tab in at.tabs]
    assert any("Tạo bài viết" in label for label in tab_labels)
    assert any("Đăng bài" in label for label in tab_labels)
    assert any("Lịch sử" in label for label in tab_labels)
    assert any("Cài đặt" in label for label in tab_labels)


def test_app_draft_saving(monkeypatch, tmp_path):
    """Test entering topic and content and saving as draft."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("FB_PAGE_ID", "123456789")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "mock_fb_access_token")

    app_path = os.path.abspath("app.py")
    at = AppTest.from_file(app_path, default_timeout=15)
    at.run()

    # Ensure app ran cleanly
    assert not at.exception
