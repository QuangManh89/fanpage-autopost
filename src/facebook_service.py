"""Facebook Graph API Service for Facebook Fanpage Auto-Poster."""

from __future__ import annotations

import os
import time
from typing import Any
import requests

__all__ = [
    "FacebookService",
    "FacebookAPIError",
    "FacebookTokenError",
    "FacebookPermissionError",
]


class FacebookAPIError(Exception):
    """Base exception for Facebook Graph API errors."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        subcode: int | None = None,
        error_type: str | None = None,
        user_message: str | None = None,
        response_json: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.subcode = subcode
        self.error_type = error_type
        self.user_message = user_message or message
        self.response_json = response_json or {}

    def __str__(self) -> str:
        parts = [self.message]
        if self.code is not None:
            parts.append(f"(Code: {self.code})")
        if self.subcode is not None:
            parts.append(f"(Subcode: {self.subcode})")
        return " ".join(parts)


class FacebookTokenError(FacebookAPIError):
    """Exception raised when Facebook Page Access Token is invalid or expired (Code 190)."""

    pass


class FacebookPermissionError(FacebookAPIError):
    """Exception raised when Facebook Page token lacks required posting permissions."""

    pass


class FacebookService:
    """Service to interact with Meta Facebook Graph API for Fanpage management.

    Handles token verification, publishing text posts, photo posts with multipart upload,
    and native Facebook scheduling.
    """

    def __init__(
        self,
        page_id: str | None = None,
        access_token: str | None = None,
        api_version: str = "v20.0",
        timeout: int = 30,
    ) -> None:
        """Initialize FacebookService.

        Args:
            page_id: Facebook Fanpage ID. Defaults to FB_PAGE_ID env var.
            access_token: Facebook Page Access Token. Defaults to FB_PAGE_ACCESS_TOKEN env var.
            api_version: Facebook Graph API version (e.g. 'v20.0').
            timeout: HTTP request timeout in seconds.

        Raises:
            ValueError: If page_id or access_token is missing or empty.
        """
        raw_page_id = page_id if page_id is not None else os.environ.get("FB_PAGE_ID")
        raw_token = (
            access_token
            if access_token is not None
            else os.environ.get("FB_PAGE_ACCESS_TOKEN")
        )

        if not raw_page_id or not str(raw_page_id).strip():
            raise ValueError(
                "FB_PAGE_ID is required. Provide it in constructor or set FB_PAGE_ID environment variable."
            )
        if not raw_token or not str(raw_token).strip():
            raise ValueError(
                "FB_PAGE_ACCESS_TOKEN is required. Provide it in constructor or set FB_PAGE_ACCESS_TOKEN environment variable."
            )

        self.page_id = str(raw_page_id).strip()
        self.access_token = str(raw_token).strip()

        clean_version = api_version.strip().lstrip("/")
        if not clean_version.startswith("v"):
            clean_version = f"v{clean_version}"
        self.api_version = clean_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.timeout = timeout

    def __repr__(self) -> str:
        """Representation masking sensitive access token."""
        return (
            f"FacebookService(page_id={self.page_id!r}, "
            f"access_token='***', api_version={self.api_version!r})"
        )

    def _mask_token(self, text: str) -> str:
        """Replace occurrences of access token with masked string."""
        if not text or not self.access_token:
            return text
        return text.replace(self.access_token, "***")

    def _parse_error_response(self, response: requests.Response) -> FacebookAPIError:
        """Parse error details from Facebook Graph API response."""
        try:
            resp_json = response.json()
        except Exception:
            sanitized_body = self._mask_token(response.text)
            return FacebookAPIError(
                message=f"HTTP {response.status_code}: {sanitized_body}",
                code=response.status_code,
                user_message=f"Lỗi phản hồi từ Facebook (HTTP {response.status_code}).",
            )

        error_data = resp_json.get("error", {})
        raw_msg = str(error_data.get("message", "Unknown Facebook API Error"))
        sanitized_msg = self._mask_token(raw_msg)
        code = error_data.get("code")
        subcode = error_data.get("error_subcode")
        err_type = error_data.get("type")

        # Classify token errors (Code 190 or OAuthException expired/invalid)
        if code == 190 or (
            err_type == "OAuthException"
            and any(
                term in sanitized_msg.lower()
                for term in ("expired", "session", "access token", "invalid token")
            )
        ):
            user_msg = (
                f"Token Fanpage đã hết hạn hoặc không hợp lệ (Code 190, Subcode {subcode}). "
                "Vui lòng cập nhật Page Access Token mới từ Meta Business Suite / Graph API Explorer."
            )
            return FacebookTokenError(
                message=sanitized_msg,
                code=code,
                subcode=subcode,
                error_type=err_type,
                user_message=user_msg,
                response_json=resp_json,
            )

        # Classify permission errors (Code 200, 10, 283 or permission denied)
        if code in (200, 10, 283) or "permission" in sanitized_msg.lower():
            user_msg = (
                f"Token Fanpage không đủ quyền thực hiện thao tác (Code {code}). "
                "Vui lòng kiểm tra quyền hạn của Fanpage (cần quyền pages_manage_posts, CREATE_CONTENT)."
            )
            return FacebookPermissionError(
                message=sanitized_msg,
                code=code,
                subcode=subcode,
                error_type=err_type,
                user_message=user_msg,
                response_json=resp_json,
            )

        # General Facebook API Error
        user_msg = f"Lỗi Facebook API (Code {code}): {sanitized_msg}"
        return FacebookAPIError(
            message=sanitized_msg,
            code=code,
            subcode=subcode,
            error_type=err_type,
            user_message=user_msg,
            response_json=resp_json,
        )

    def _execute_request(self, method: str, url: str, **kwargs) -> dict:
        """Execute HTTP request with error handling and token masking."""
        kwargs.setdefault("timeout", self.timeout)
        try:
            if method.upper() == "GET":
                response = requests.get(url, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, **kwargs)
            else:
                response = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            sanitized_exc = self._mask_token(str(exc))
            raise FacebookAPIError(
                message=f"Lỗi kết nối Facebook API: {sanitized_exc}",
                user_message="Không thể kết nối đến máy chủ Facebook. Vui lòng kiểm tra kết nối mạng.",
            ) from exc

        # Check for error condition
        is_error = False
        resp_json = None
        try:
            resp_json = response.json()
            if isinstance(resp_json, dict) and "error" in resp_json:
                is_error = True
        except Exception:
            pass

        if not is_error:
            if hasattr(response, "status_code") and isinstance(response.status_code, int):
                if response.status_code >= 400:
                    is_error = True
            elif not getattr(response, "ok", True):
                is_error = True

        if is_error:
            raise self._parse_error_response(response)

        if resp_json is not None:
            return resp_json

        try:
            return response.json()
        except Exception:
            return {"text": response.text}

    def validate_schedule_time(
        self, scheduled_publish_time: int | None
    ) -> int | None:
        """Validate Facebook Graph API scheduling time constraints.

        Constraints:
            Must be between 10 minutes and 75 days in the future.

        Args:
            scheduled_publish_time: Unix timestamp (seconds).

        Returns:
            Validated integer timestamp, or None if not scheduling.

        Raises:
            ValueError: If scheduled time is less than 10 minutes or more than 75 days from now.
        """
        if scheduled_publish_time is None:
            return None

        try:
            timestamp = int(scheduled_publish_time)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Thời gian hẹn giờ không hợp lệ: {scheduled_publish_time}"
            ) from exc

        now = int(time.time())
        min_allowed = now + 600  # 10 minutes
        max_allowed = now + (75 * 86400)  # 75 days

        if timestamp < min_allowed:
            raise ValueError(
                "Thời gian hẹn giờ phải cách thời điểm hiện tại ít nhất 10 phút."
            )
        if timestamp > max_allowed:
            raise ValueError(
                "Thời gian hẹn giờ không được vượt quá 75 ngày kể từ thời điểm hiện tại."
            )

        return timestamp

    def verify_token(self) -> dict:
        """Verify the Page Access Token and retrieve page permissions.

        Returns:
            dict containing:
                - valid (bool): True if token is valid.
                - page_id (str): Facebook Page ID.
                - page_name (str): Name of the Fanpage.
                - tasks (list[str]): List of assigned tasks/permissions.
                - can_post (bool): True if the token has permission to post content.
                - raw (dict): Raw Graph API response.

        Raises:
            FacebookTokenError: If token is expired or invalid.
            FacebookPermissionError: If token lacks access to page.
            FacebookAPIError: If Facebook API returns an error.
        """
        url = f"{self.base_url}/{self.page_id}"
        # Page tokens directly querying /{page_id} accept 'id,name'
        params = {
            "fields": "id,name",
            "access_token": self.access_token,
        }

        data = self._execute_request("GET", url, params=params)
        tasks = data.get("tasks", [])
        # If successfully retrieved page info using Page token, posting is enabled
        can_post = True if not tasks else ("CREATE_CONTENT" in tasks or "MANAGE" in tasks)

        return {
            "valid": True,
            "page_id": data.get("id", self.page_id),
            "page_name": data.get("name", ""),
            "tasks": tasks,
            "can_post": can_post,
            "raw": data,
        }

    def publish_text_post(
        self,
        message: str,
        scheduled_publish_time: int | None = None,
    ) -> dict:
        """Publish a text-only post to the Facebook Fanpage feed.

        Supports immediate publishing or native Facebook scheduling.

        Args:
            message: Post text content.
            scheduled_publish_time: Optional Unix timestamp for scheduling (10 mins to 75 days).

        Returns:
            dict with Facebook post ID (e.g. `{"id": "page_id_post_id"}`).

        Raises:
            ValueError: If message is empty or schedule time is invalid.
            FacebookAPIError: If Facebook API returns an error.
        """
        if not message or not message.strip():
            raise ValueError("Nội dung bài viết không được để trống.")

        sched_time = self.validate_schedule_time(scheduled_publish_time)
        url = f"{self.base_url}/{self.page_id}/feed"

        payload: dict[str, Any] = {
            "message": message.strip(),
            "access_token": self.access_token,
        }

        if sched_time is not None:
            payload["published"] = False
            payload["scheduled_publish_time"] = sched_time
        else:
            payload["published"] = True

        return self._execute_request("POST", url, data=payload)

    def publish_photo_post(
        self,
        message: str,
        photo_path: str,
        scheduled_publish_time: int | None = None,
    ) -> dict:
        """Publish a photo post to the Facebook Fanpage with multipart file upload.

        Supports immediate publishing or native Facebook scheduling.

        Args:
            message: Caption text for the photo.
            photo_path: Local filesystem path to the image file.
            scheduled_publish_time: Optional Unix timestamp for scheduling.

        Returns:
            dict with photo ID and post ID (e.g. `{"id": "photo_id", "post_id": "page_id_post_id"}`).

        Raises:
            FileNotFoundError: If photo file does not exist.
            ValueError: If photo file is empty or exceeds 10MB, or schedule time invalid.
            FacebookAPIError: If Facebook API returns an error.
        """
        if not photo_path or not os.path.exists(photo_path):
            raise FileNotFoundError(f"Không tìm thấy file ảnh: {photo_path}")

        if not os.path.isfile(photo_path):
            raise FileNotFoundError(f"Đường dẫn không phải là file: {photo_path}")

        file_size = os.path.getsize(photo_path)
        if file_size == 0:
            raise ValueError("File ảnh rỗng (0 bytes).")

        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise ValueError(
                f"Dung lượng ảnh ({file_size / (1024 * 1024):.2f}MB) vượt quá giới hạn 10MB của Facebook."
            )

        sched_time = self.validate_schedule_time(scheduled_publish_time)
        url = f"{self.base_url}/{self.page_id}/photos"

        payload: dict[str, Any] = {
            "caption": message or "",
            "access_token": self.access_token,
        }

        if sched_time is not None:
            payload["published"] = False
            payload["scheduled_publish_time"] = sched_time
        else:
            payload["published"] = True

        with open(photo_path, "rb") as photo_file:
            files = {"source": photo_file}
            return self._execute_request(
                "POST", url, data=payload, files=files
            )

    def publish_multi_photo_post(
        self,
        message: str,
        photo_paths: list[str],
        scheduled_publish_time: int | None = None,
    ) -> dict:
        """Publish a post with one or multiple photos attached to the Facebook Fanpage.

        If a single photo is provided, delegates to publish_photo_post.
        If multiple photos are provided, uploads each photo as unpublished
        and creates a single feed post with `attached_media`.

        Args:
            message: Caption text for the post.
            photo_paths: List of local image file paths.
            scheduled_publish_time: Optional Unix timestamp for scheduling.

        Returns:
            dict with post ID (e.g. `{"id": "page_id_post_id"}`).

        Raises:
            ValueError: If photo_paths is empty or contains invalid files.
            FileNotFoundError: If any photo file is missing.
            FacebookAPIError: If Facebook API returns an error.
        """
        valid_paths = [p for p in photo_paths if p and str(p).strip()]
        if not valid_paths:
            raise ValueError("Danh sách file ảnh không được để trống.")

        if len(valid_paths) == 1:
            return self.publish_photo_post(
                message=message,
                photo_path=valid_paths[0],
                scheduled_publish_time=scheduled_publish_time,
            )

        # Validate all files before starting upload
        for p in valid_paths:
            if not os.path.exists(p) or not os.path.isfile(p):
                raise FileNotFoundError(f"Không tìm thấy file ảnh: {p}")
            sz = os.path.getsize(p)
            if sz == 0:
                raise ValueError(f"File ảnh rỗng (0 bytes): {p}")
            if sz > 10 * 1024 * 1024:
                raise ValueError(f"Dung lượng ảnh ({sz / (1024 * 1024):.2f}MB) vượt quá giới hạn 10MB: {p}")

        sched_time = self.validate_schedule_time(scheduled_publish_time)

        # Upload each photo as unpublished
        import json
        media_fbids = []
        upload_url = f"{self.base_url}/{self.page_id}/photos"
        for p in valid_paths:
            upload_payload: dict[str, Any] = {
                "published": False,
                "access_token": self.access_token,
            }
            with open(p, "rb") as pf:
                files = {"source": pf}
                res = self._execute_request("POST", upload_url, data=upload_payload, files=files)
                photo_id = res.get("id")
                if not photo_id:
                    raise FacebookAPIError(f"Upload ảnh thất bại: {res}")
                media_fbids.append({"media_fbid": str(photo_id)})

        # Publish the feed post with attached_media
        feed_url = f"{self.base_url}/{self.page_id}/feed"
        feed_payload: dict[str, Any] = {
            "message": message or "",
            "access_token": self.access_token,
            "attached_media": json.dumps(media_fbids),
        }
        if sched_time is not None:
            feed_payload["published"] = False
            feed_payload["scheduled_publish_time"] = sched_time
        else:
            feed_payload["published"] = True

        return self._execute_request("POST", feed_url, data=feed_payload)


    def get_post_info(self, post_id: str) -> dict:
        """Fetch information about a published Facebook post.

        Args:
            post_id: Facebook post ID.

        Returns:
            dict containing post information (id, message, created_time, shares, likes, comments).

        Raises:
            ValueError: If post_id is empty.
            FacebookAPIError: If post not found or API error occurs.
        """
        if not post_id or not str(post_id).strip():
            raise ValueError("post_id không được để trống.")

        clean_post_id = str(post_id).strip()
        url = f"{self.base_url}/{clean_post_id}"
        params = {
            "fields": "id,message,created_time,shares,comments.summary(true),likes.summary(true)",
            "access_token": self.access_token,
        }

        return self._execute_request("GET", url, params=params)

    # ==================== Token Exchange & Account Tools ====================

    @classmethod
    def exchange_token_to_long_lived(
        cls,
        app_id: str,
        app_secret: str,
        short_token: str,
        api_version: str = "v20.0",
        timeout: int = 30,
    ) -> dict:
        """Exchange a short-lived User token for a 60-day long-lived User token.

        Calls: GET https://graph.facebook.com/{api_version}/oauth/access_token
        Params:
            grant_type: fb_exchange_token
            client_id: app_id
            client_secret: app_secret
            fb_exchange_token: short_token

        Returns:
            dict containing access_token, token_type, and expires_in.
        """
        clean_app_id = str(app_id or "").strip()
        clean_secret = str(app_secret or "").strip()
        clean_token = str(short_token or "").strip()
        if not clean_app_id or not clean_secret or not clean_token:
            raise ValueError("Vui lòng nhập đầy đủ App ID, App Secret và Token ngắn hạn.")

        url = f"https://graph.facebook.com/{api_version}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": clean_app_id,
            "client_secret": clean_secret,
            "fb_exchange_token": clean_token,
        }
        svc = cls(page_id="dummy", access_token=clean_token, api_version=api_version, timeout=timeout)
        return svc._execute_request("GET", url, params=params)

    @classmethod
    def get_user_accounts(
        cls,
        user_access_token: str,
        api_version: str = "v20.0",
        timeout: int = 30,
    ) -> list[dict]:
        """Fetch list of Facebook Pages managed by user using a user access token.

        When called with a 60-day long-lived user token, the returned page access tokens
        NEVER EXPIRE (vĩnh viễn).

        Calls: GET https://graph.facebook.com/{api_version}/me/accounts
        Params:
            access_token: user_access_token
            fields: id,name,access_token,tasks

        Returns:
            list of dicts containing page id, name, access_token, and tasks.
        """
        clean_token = str(user_access_token or "").strip()
        if not clean_token:
            raise ValueError("Chưa có User Access Token.")

        url = f"https://graph.facebook.com/{api_version}/me/accounts"
        params = {
            "fields": "id,name,access_token,tasks",
            "access_token": clean_token,
        }
        svc = cls(page_id="dummy", access_token=clean_token, api_version=api_version, timeout=timeout)
        data = svc._execute_request("GET", url, params=params)
        return data.get("data", [])

    @classmethod
    def exchange_page_token_to_never_expire(
        cls,
        app_id: str,
        app_secret: str,
        page_token_short: str,
        api_version: str = "v20.0",
        timeout: int = 30,
    ) -> dict:
        """Directly exchange a short-lived Page token for a permanent Page token."""
        return cls.exchange_token_to_long_lived(
            app_id=app_id,
            app_secret=app_secret,
            short_token=page_token_short,
            api_version=api_version,
            timeout=timeout,
        )

