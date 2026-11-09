"""Unit tests for FacebookService mocking Facebook Graph API requests."""

import time
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.facebook_service import (
    FacebookService,
    FacebookAPIError,
    FacebookTokenError,
    FacebookPermissionError,
)


@pytest.fixture
def fb_service():
    """Create a FacebookService instance with mock credentials."""
    return FacebookService(
        page_id="1234567890",
        access_token="EAABtesttokensecret12345",
        api_version="v20.0",
    )


class TestFacebookServiceInit:
    """Tests for FacebookService initialization and configuration."""

    def test_init_with_explicit_params(self):
        service = FacebookService(
            page_id="123456",
            access_token="token123",
            api_version="v20.0",
        )
        assert service.page_id == "123456"
        assert service.access_token == "token123"
        assert service.api_version == "v20.0"
        assert service.base_url == "https://graph.facebook.com/v20.0"

    def test_init_with_env_vars(self, monkeypatch):
        monkeypatch.setenv("FB_PAGE_ID", "env_page_999")
        monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "env_token_secret")

        service = FacebookService()
        assert service.page_id == "env_page_999"
        assert service.access_token == "env_token_secret"

    def test_init_missing_page_id(self, monkeypatch):
        monkeypatch.delenv("FB_PAGE_ID", raising=False)
        monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "valid_token")

        with pytest.raises(ValueError, match="FB_PAGE_ID"):
            FacebookService(page_id=None, access_token=None)

    def test_init_missing_access_token(self, monkeypatch):
        monkeypatch.setenv("FB_PAGE_ID", "valid_page")
        monkeypatch.delenv("FB_PAGE_ACCESS_TOKEN", raising=False)

        with pytest.raises(ValueError, match="FB_PAGE_ACCESS_TOKEN"):
            FacebookService(page_id=None, access_token=None)

    def test_init_strips_whitespace(self):
        service = FacebookService(
            page_id="  123456  ",
            access_token="  token123  ",
        )
        assert service.page_id == "123456"
        assert service.access_token == "token123"

    def test_repr_masks_token(self, fb_service):
        repr_str = repr(fb_service)
        assert "EAABtesttokensecret12345" not in repr_str
        assert "***" in repr_str
        assert "1234567890" in repr_str


class TestFacebookServiceVerifyToken:
    """Tests for token verification and page permission checking."""

    @patch("requests.get")
    def test_verify_token_success_with_permissions(self, mock_get, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "1234567890",
            "name": "My Tech Fanpage",
            "tasks": ["CREATE_CONTENT", "MODERATE", "ADVERTISE"],
        }
        mock_get.return_value = mock_resp

        result = fb_service.verify_token()

        assert result["valid"] is True
        assert result["page_id"] == "1234567890"
        assert result["page_name"] == "My Tech Fanpage"
        assert "CREATE_CONTENT" in result["tasks"]
        assert result["can_post"] is True

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "1234567890" in args[0]
        assert kwargs["params"]["access_token"] == fb_service.access_token

    @patch("requests.get")
    def test_verify_token_success_without_create_content(self, mock_get, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "1234567890",
            "name": "Read Only Fanpage",
            "tasks": ["ANALYZE"],
        }
        mock_get.return_value = mock_resp

        result = fb_service.verify_token()
        assert result["valid"] is True
        assert result["can_post"] is False

    @patch("requests.get")
    def test_verify_token_expired_code_190(self, mock_get, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "Error validating access token: Session has expired on...",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 463,
            }
        }
        mock_get.return_value = mock_resp

        with pytest.raises(FacebookTokenError) as exc_info:
            fb_service.verify_token()

        assert exc_info.value.code == 190
        assert exc_info.value.subcode == 463
        assert "hết hạn" in exc_info.value.user_message.lower() or "token" in exc_info.value.user_message.lower()

    @patch("requests.get")
    def test_verify_token_network_error(self, mock_get, fb_service):
        mock_get.side_effect = requests.RequestException("Connection timed out")

        with pytest.raises(FacebookAPIError, match="Lỗi kết nối"):
            fb_service.verify_token()

    @patch("requests.get")
    def test_verify_token_masks_secret_in_error_message(self, mock_get, fb_service):
        secret = fb_service.access_token
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": f"Invalid OAuth access token: {secret} has expired",
                "type": "OAuthException",
                "code": 190,
            }
        }
        mock_get.return_value = mock_resp

        with pytest.raises(FacebookTokenError) as exc_info:
            fb_service.verify_token()

        assert secret not in str(exc_info.value)
        assert "***" in str(exc_info.value)


class TestFacebookServicePublishTextPost:
    """Tests for publishing text posts to Facebook Fanpage feed."""

    def test_publish_text_post_empty_message_raises_value_error(self, fb_service):
        with pytest.raises(ValueError, match="không được để trống"):
            fb_service.publish_text_post("")

        with pytest.raises(ValueError, match="không được để trống"):
            fb_service.publish_text_post("   \n\t  ")

    @patch("requests.post")
    def test_publish_text_post_immediate_success(self, mock_post, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "1234567890_987654321"}
        mock_post.return_value = mock_resp

        result = fb_service.publish_text_post("Bài viết test không hẹn giờ #tintuc")

        assert result["id"] == "1234567890_987654321"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == f"{fb_service.base_url}/{fb_service.page_id}/feed"
        data = kwargs["data"]
        assert data["message"] == "Bài viết test không hẹn giờ #tintuc"
        assert data["published"] is True
        assert "scheduled_publish_time" not in data

    @patch("requests.post")
    def test_publish_text_post_scheduled_success(self, mock_post, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "1234567890_987654321"}
        mock_post.return_value = mock_resp

        target_time = int(time.time()) + 3600  # 1 hour later
        result = fb_service.publish_text_post(
            message="Bài viết hẹn giờ trên FB",
            scheduled_publish_time=target_time,
        )

        assert result["id"] == "1234567890_987654321"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        data = kwargs["data"]
        assert data["message"] == "Bài viết hẹn giờ trên FB"
        assert data["published"] is False
        assert data["scheduled_publish_time"] == target_time

    def test_publish_text_post_scheduled_too_soon_raises_value_error(self, fb_service):
        # 5 minutes in the future (< 10 minutes requirement)
        too_soon = int(time.time()) + 300
        with pytest.raises(ValueError, match="10 phút"):
            fb_service.publish_text_post("Bài test", scheduled_publish_time=too_soon)

    def test_publish_text_post_scheduled_in_past_raises_value_error(self, fb_service):
        in_past = int(time.time()) - 3600
        with pytest.raises(ValueError, match="10 phút"):
            fb_service.publish_text_post("Bài test", scheduled_publish_time=in_past)

    def test_publish_text_post_scheduled_too_far_raises_value_error(self, fb_service):
        # 76 days in future (> 75 days requirement)
        too_far = int(time.time()) + (76 * 86400)
        with pytest.raises(ValueError, match="75 ngày"):
            fb_service.publish_text_post("Bài test", scheduled_publish_time=too_far)

    @patch("requests.post")
    def test_publish_text_post_permission_error(self, mock_post, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {
            "error": {
                "message": "(#200) Feed story publishing to a group/page must be granted permissions.",
                "type": "OAuthException",
                "code": 200,
            }
        }
        mock_post.return_value = mock_resp

        with pytest.raises(FacebookPermissionError) as exc_info:
            fb_service.publish_text_post("Bài viết bị chặn quyền")

        assert exc_info.value.code == 200
        assert "quyền" in exc_info.value.user_message.lower()


class TestFacebookServicePublishPhotoPost:
    """Tests for publishing photo posts to Facebook Fanpage."""

    def test_publish_photo_file_not_found(self, fb_service):
        with pytest.raises(FileNotFoundError, match="Không tìm thấy file ảnh"):
            fb_service.publish_photo_post(
                message="Caption",
                photo_path="non_existent_image_12345.jpg",
            )

    def test_publish_photo_file_empty(self, fb_service, tmp_path):
        empty_file = tmp_path / "empty.jpg"
        empty_file.write_bytes(b"")

        with pytest.raises(ValueError, match="rỗng"):
            fb_service.publish_photo_post(
                message="Caption",
                photo_path=str(empty_file),
            )

    def test_publish_photo_file_exceeds_10mb(self, fb_service, tmp_path):
        large_file = tmp_path / "large.jpg"
        # Mocking os.path.getsize to avoid allocating 11MB on disk
        large_file.write_bytes(b"mock data")

        with patch("os.path.getsize", return_value=11 * 1024 * 1024):
            with pytest.raises(ValueError, match="10MB"):
                fb_service.publish_photo_post(
                    message="Caption",
                    photo_path=str(large_file),
                )

    @patch("requests.post")
    def test_publish_photo_post_immediate_success(self, mock_post, fb_service, tmp_path):
        image_file = tmp_path / "sample.jpg"
        image_file.write_bytes(b"\xff\xd8\xff\xe0testimagecontent")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "photo_id_111",
            "post_id": "1234567890_987654321",
        }
        mock_post.return_value = mock_resp

        result = fb_service.publish_photo_post(
            message="Hình ảnh tuyệt đẹp #photo",
            photo_path=str(image_file),
        )

        assert result["id"] == "photo_id_111"
        assert result["post_id"] == "1234567890_987654321"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == f"{fb_service.base_url}/{fb_service.page_id}/photos"
        assert kwargs["data"]["caption"] == "Hình ảnh tuyệt đẹp #photo"
        assert kwargs["data"]["published"] is True
        assert "scheduled_publish_time" not in kwargs["data"]
        assert "source" in kwargs["files"]

    @patch("requests.post")
    def test_publish_photo_post_scheduled_success(self, mock_post, fb_service, tmp_path):
        image_file = tmp_path / "scheduled.jpg"
        image_file.write_bytes(b"\xff\xd8\xff\xe0testimagecontent")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "photo_id_222",
            "post_id": "1234567890_987654322",
        }
        mock_post.return_value = mock_resp

        target_time = int(time.time()) + 7200  # 2 hours later
        result = fb_service.publish_photo_post(
            message="Ảnh hẹn giờ 2 tiếng sau",
            photo_path=str(image_file),
            scheduled_publish_time=target_time,
        )

        assert result["id"] == "photo_id_222"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["published"] is False
        assert kwargs["data"]["scheduled_publish_time"] == target_time

    @patch("requests.post")
    def test_publish_photo_post_api_error(self, mock_post, fb_service, tmp_path):
        image_file = tmp_path / "sample.jpg"
        image_file.write_bytes(b"\xff\xd8\xff\xe0testimagecontent")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "There was an error uploading the photo.",
                "type": "FacebookApiException",
                "code": 368,
            }
        }
        mock_post.return_value = mock_resp

        with pytest.raises(FacebookAPIError) as exc_info:
            fb_service.publish_photo_post(
                message="Ảnh lỗi",
                photo_path=str(image_file),
            )
        assert exc_info.value.code == 368


class TestFacebookServiceGetPostInfo:
    """Tests for fetching post information from Graph API."""

    def test_get_post_info_empty_id(self, fb_service):
        with pytest.raises(ValueError, match="post_id không được để trống"):
            fb_service.get_post_info("")

        with pytest.raises(ValueError, match="post_id không được để trống"):
            fb_service.get_post_info("   ")

    @patch("requests.get")
    def test_get_post_info_success(self, mock_get, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "1234567890_987654321",
            "message": "Nội dung bài viết",
            "created_time": "2026-11-06T10:00:00+0000",
            "shares": {"count": 15},
            "likes": {"summary": {"total_count": 120}},
        }
        mock_get.return_value = mock_resp

        info = fb_service.get_post_info("1234567890_987654321")

        assert info["id"] == "1234567890_987654321"
        assert info["shares"]["count"] == 15
        assert info["likes"]["summary"]["total_count"] == 120

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == f"{fb_service.base_url}/1234567890_987654321"
        assert "fields" in kwargs["params"]
        assert kwargs["params"]["access_token"] == fb_service.access_token

    @patch("requests.get")
    def test_get_post_info_not_found(self, mock_get, fb_service):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {
            "error": {
                "message": "Unsupported get request. Object with ID 'fake_id' does not exist",
                "type": "GraphMethodException",
                "code": 100,
            }
        }
        mock_get.return_value = mock_resp

        with pytest.raises(FacebookAPIError) as exc_info:
            fb_service.get_post_info("fake_id")

        assert exc_info.value.code == 100

    @patch("requests.post")
    def test_publish_multi_photo_post_success(self, mock_post, fb_service, tmp_path):
        import json
        img1 = tmp_path / "img1.png"
        img1.write_bytes(b"image_data_one")
        img2 = tmp_path / "img2.png"
        img2.write_bytes(b"image_data_two")

        # Mock 2 photo uploads then 1 feed post
        mock_resp_photo1 = MagicMock(status_code=200)
        mock_resp_photo1.json.return_value = {"id": "photo_id_1"}

        mock_resp_photo2 = MagicMock(status_code=200)
        mock_resp_photo2.json.return_value = {"id": "photo_id_2"}

        mock_resp_feed = MagicMock(status_code=200)
        mock_resp_feed.json.return_value = {"id": "page_id_feed_123"}

        mock_post.side_effect = [mock_resp_photo1, mock_resp_photo2, mock_resp_feed]

        res = fb_service.publish_multi_photo_post(
            message="Multi photo test",
            photo_paths=[str(img1), str(img2)],
        )

        assert res["id"] == "page_id_feed_123"
        assert mock_post.call_count == 3

        # Verify feed call arguments
        feed_call = mock_post.call_args_list[2]
        assert "feed" in feed_call[0][0]
        data = feed_call[1]["data"]
        assert data["message"] == "Multi photo test"
        attached = json.loads(data["attached_media"])
        assert attached == [{"media_fbid": "photo_id_1"}, {"media_fbid": "photo_id_2"}]

    def test_publish_multi_photo_empty_raises(self, fb_service):
        with pytest.raises(ValueError, match="trống"):
            fb_service.publish_multi_photo_post("message", [])

    def test_publish_multi_photo_missing_file_raises(self, fb_service):
        with pytest.raises(FileNotFoundError):
            fb_service.publish_multi_photo_post("message", ["non_existent_1.png", "non_existent_2.png"])

    @patch("requests.get")
    def test_exchange_token_to_long_lived_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "EAAB_long_lived_user_token_60d",
            "token_type": "bearer",
            "expires_in": 5184000,
        }
        mock_get.return_value = mock_resp

        result = FacebookService.exchange_token_to_long_lived(
            app_id="123456",
            app_secret="abcdef32charssecret",
            short_token="EAAB_short_token",
        )

        assert result["access_token"] == "EAAB_long_lived_user_token_60d"
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "oauth/access_token" in args[0]
        assert kwargs["params"]["grant_type"] == "fb_exchange_token"
        assert kwargs["params"]["client_id"] == "123456"

    def test_exchange_token_missing_params_raises(self):
        with pytest.raises(ValueError, match="đầy đủ"):
            FacebookService.exchange_token_to_long_lived("", "secret", "tok")
        with pytest.raises(ValueError, match="đầy đủ"):
            FacebookService.exchange_token_to_long_lived("app", "", "tok")
        with pytest.raises(ValueError, match="đầy đủ"):
            FacebookService.exchange_token_to_long_lived("app", "secret", "")

    @patch("requests.get")
    def test_get_user_accounts_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "619960427857965",
                    "name": "Sửa Máy Tính Tại Nhà BMT",
                    "access_token": "EAAB_permanent_page_token",
                    "tasks": ["MANAGE", "CREATE_CONTENT"],
                }
            ]
        }
        mock_get.return_value = mock_resp

        accounts = FacebookService.get_user_accounts(user_access_token="EAAB_long_user_tok")
        assert len(accounts) == 1
        assert accounts[0]["id"] == "619960427857965"
        assert accounts[0]["name"] == "Sửa Máy Tính Tại Nhà BMT"
        assert accounts[0]["access_token"] == "EAAB_permanent_page_token"

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "me/accounts" in args[0]
        assert kwargs["params"]["access_token"] == "EAAB_long_user_tok"

    def test_get_user_accounts_empty_token_raises(self):
        with pytest.raises(ValueError, match="User Access Token"):
            FacebookService.get_user_accounts("")

    @patch("requests.get")
    def test_exchange_page_token_to_never_expire(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "EAAB_perm_page_token"}
        mock_get.return_value = mock_resp

        res = FacebookService.exchange_page_token_to_never_expire("app_id", "secret", "short_page_tok")
        assert res["access_token"] == "EAAB_perm_page_token"


