"""Unit tests for UI Helpers used in Streamlit Fanpage Dashboard."""

import os
from datetime import datetime, timedelta
import pytest

from src.ui_helpers import (
    format_facebook_url,
    validate_schedule_datetime_fb,
    validate_schedule_datetime_local,
    get_status_badge,
    render_status_badge_html,
    save_uploaded_file,
    save_env_config,
    load_env_config,
    mask_token,
)


class DummyUploadedFile:
    """Mock Streamlit UploadedFile."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data

    def read(self):
        return self._data


def test_format_facebook_url():
    assert format_facebook_url(None) is None
    assert format_facebook_url("") is None
    assert format_facebook_url("   ") is None
    assert (
        format_facebook_url("123456789_987654321")
        == "https://www.facebook.com/123456789_987654321"
    )
    assert (
        format_facebook_url("https://www.facebook.com/post_123")
        == "https://www.facebook.com/post_123"
    )
    assert (
        format_facebook_url("http://facebook.com/12345")
        == "http://facebook.com/12345"
    )


def test_validate_schedule_datetime_fb():
    now = datetime(2026, 11, 6, 10, 0, 0)

    # Valid: 1 hour in future
    dt_valid = now + timedelta(hours=1)
    is_valid, err, ts = validate_schedule_datetime_fb(dt_valid, now=now)
    assert is_valid is True
    assert err is None
    assert ts == int(dt_valid.timestamp())

    # Invalid: Only 5 minutes in future (< 10 minutes)
    dt_too_soon = now + timedelta(minutes=5)
    is_valid, err, ts = validate_schedule_datetime_fb(dt_too_soon, now=now)
    assert is_valid is False
    assert "ít nhất 10 phút" in err
    assert ts is None

    # Invalid: 80 days in future (> 75 days)
    dt_too_far = now + timedelta(days=80)
    is_valid, err, ts = validate_schedule_datetime_fb(dt_too_far, now=now)
    assert is_valid is False
    assert "75 ngày" in err
    assert ts is None

    # Edge cases: Exactly 10 minutes (valid)
    dt_min = now + timedelta(minutes=10)
    is_valid, err, ts = validate_schedule_datetime_fb(dt_min, now=now)
    assert is_valid is True
    assert err is None

    # Edge cases: Exactly 75 days (valid)
    dt_max = now + timedelta(days=75)
    is_valid, err, ts = validate_schedule_datetime_fb(dt_max, now=now)
    assert is_valid is True
    assert err is None


def test_validate_schedule_datetime_local():
    now = datetime(2026, 11, 6, 10, 0, 0)

    # In future
    dt_future = now + timedelta(minutes=2)
    is_valid, err = validate_schedule_datetime_local(dt_future, now=now)
    assert is_valid is True
    assert err is None

    # In past
    dt_past = now - timedelta(minutes=5)
    is_valid, err = validate_schedule_datetime_local(dt_past, now=now)
    assert is_valid is False
    assert "tương lai" in err

    # Equal to now
    is_valid, err = validate_schedule_datetime_local(now, now=now)
    assert is_valid is False
    assert "tương lai" in err


def test_get_status_badge():
    badge_pub = get_status_badge("published")
    assert badge_pub["label"] == "Đã đăng"
    assert "color" in badge_pub
    assert "icon" in badge_pub

    badge_sched_fb = get_status_badge("scheduled_fb")
    assert badge_sched_fb["label"] == "Hẹn giờ Facebook"

    badge_sched_local = get_status_badge("scheduled_local")
    assert badge_sched_local["label"] == "Hẹn giờ Local"

    badge_draft = get_status_badge("draft")
    assert badge_draft["label"] == "Bản nháp"

    badge_failed = get_status_badge("failed")
    assert badge_failed["label"] == "Thất bại"

    badge_cancelled = get_status_badge("cancelled")
    assert badge_cancelled["label"] == "Đã hủy"

    badge_unknown = get_status_badge("unknown_custom")
    assert badge_unknown["label"] == "unknown_custom"


def test_render_status_badge_html():
    html = render_status_badge_html("published")
    assert "Đã đăng" in html
    assert "<span" in html
    assert "</span>" in html


def test_save_uploaded_file(tmp_path):
    upload_dir = tmp_path / "uploads"
    file_bytes = b"fake image content PNG/JPEG"
    mock_file = DummyUploadedFile(name="photo test.jpg", data=file_bytes)

    saved_path = save_uploaded_file(mock_file, upload_dir=str(upload_dir))
    assert os.path.exists(saved_path)
    assert saved_path.endswith(".jpg")
    with open(saved_path, "rb") as f:
        assert f.read() == file_bytes


def test_save_uploaded_file_empty(tmp_path):
    upload_dir = tmp_path / "uploads"
    mock_file = DummyUploadedFile(name="empty.jpg", data=b"")

    with pytest.raises(ValueError, match="rỗng"):
        save_uploaded_file(mock_file, upload_dir=str(upload_dir))


def test_mask_token():
    assert mask_token(None) == "***"
    assert mask_token("") == "***"
    assert mask_token("short") == "***"
    token = "EAAG1234567890abcdefgHIJKLMNOP"
    masked = mask_token(token)
    assert masked.startswith("EAAG")
    assert masked.endswith("MNOP")
    assert "..." in masked
    assert "abcdef" not in masked


def test_save_and_load_env_config(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    # Ensure fresh state
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("FB_PAGE_ID", raising=False)
    monkeypatch.delenv("FB_PAGE_ACCESS_TOKEN", raising=False)

    # Initial write
    configs = {
        "GEMINI_API_KEY": "AIzaSyTestKey123",
        "OPENROUTER_API_KEY": "sk-or-v1-abc",
        "FB_PAGE_ID": "100200300400",
        "FB_PAGE_ACCESS_TOKEN": "EAAXsampletoken",
        "APP_PASSWORD": "SecretPassword123",
    }
    success = save_env_config(configs, env_path=str(env_file))
    assert success is True
    assert env_file.exists()

    # Loaded back
    loaded = load_env_config(env_path=str(env_file))
    assert loaded["GEMINI_API_KEY"] == "AIzaSyTestKey123"
    assert loaded["OPENROUTER_API_KEY"] == "sk-or-v1-abc"
    assert loaded["FB_PAGE_ID"] == "100200300400"
    assert loaded["FB_PAGE_ACCESS_TOKEN"] == "EAAXsampletoken"
    assert loaded["APP_PASSWORD"] == "SecretPassword123"

    # os.environ should also be updated
    assert os.environ.get("GEMINI_API_KEY") == "AIzaSyTestKey123"

    # Update only one key
    save_env_config({"GEMINI_API_KEY": "AIzaSyNewKey456"}, env_path=str(env_file))
    loaded2 = load_env_config(env_path=str(env_file))
    assert loaded2["GEMINI_API_KEY"] == "AIzaSyNewKey456"
    assert loaded2["FB_PAGE_ID"] == "100200300400"


def test_parse_image_paths():
    from src.ui_helpers import parse_image_paths

    assert parse_image_paths(None) == []
    assert parse_image_paths("") == []
    assert parse_image_paths("   ") == []

    # Single path
    assert parse_image_paths("data/uploads/img1.png") == ["data/uploads/img1.png"]

    # Comma-separated paths
    assert parse_image_paths("data/uploads/img1.png, data/uploads/img2.jpg") == [
        "data/uploads/img1.png",
        "data/uploads/img2.jpg",
    ]

    # JSON array
    import json
    json_val = json.dumps(["data/uploads/a.png", "data/uploads/b.png"])
    assert parse_image_paths(json_val) == ["data/uploads/a.png", "data/uploads/b.png"]

    # Python list
    assert parse_image_paths(["p1.jpg", "p2.jpg"]) == ["p1.jpg", "p2.jpg"]



def test_replace_page_hashtags():
    from src.ui_helpers import replace_page_hashtags

    # 1. Base content with no tags
    content = "Dịch vụ sửa chữa laptop uy tín, kiểm tra miễn phí."
    conic_tags = "#q8 #q4 #q6 #q1 #BinhChanh #Conic #SuaLaptopConic"
    result = replace_page_hashtags(content, conic_tags)
    assert "#q8" in result
    assert "#Conic" in result
    assert "Dịch vụ sửa chữa laptop uy tín" in result

    # 2. Replacing Conic tags with BMT tags
    bmt_tags = "#Bmt #BuonMaThuot #PhuongTanLap #PhuongTanAn #SuaMayTinhBMT"
    bmt_result = replace_page_hashtags(result, bmt_tags)
    assert "#Bmt" in bmt_result
    assert "#BuonMaThuot" in bmt_result
    assert "#q8" not in bmt_result
    assert "#Conic" not in bmt_result
    assert "Dịch vụ sửa chữa laptop uy tín" in bmt_result

    # 3. Empty inputs
    assert replace_page_hashtags("", conic_tags) == conic_tags
    assert replace_page_hashtags("Some content", "") == "Some content"
    assert replace_page_hashtags("Some content", "   ") == "Some content"
