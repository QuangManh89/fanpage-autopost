"""UI Helper functions and utilities for the Streamlit Fanpage Dashboard."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import Any
from dotenv import dotenv_values, set_key

__all__ = [
    "format_facebook_url",
    "validate_schedule_datetime_fb",
    "validate_schedule_datetime_local",
    "get_status_badge",
    "render_status_badge_html",
    "save_uploaded_file",
    "save_env_config",
    "load_env_config",
    "mask_token",
]

# Status badge dictionary definitions
STATUS_MAP: dict[str, dict[str, str]] = {
    "published": {
        "label": "Đã đăng",
        "color": "#28a745",
        "icon": "✅",
    },
    "scheduled_fb": {
        "label": "Hẹn giờ Facebook",
        "color": "#007bff",
        "icon": "⏰",
    },
    "scheduled_local": {
        "label": "Hẹn giờ Local",
        "color": "#6f42c1",
        "icon": "💻",
    },
    "draft": {
        "label": "Bản nháp",
        "color": "#fd7e14",
        "icon": "📝",
    },
    "failed": {
        "label": "Thất bại",
        "color": "#dc3545",
        "icon": "❌",
    },
    "cancelled": {
        "label": "Đã hủy",
        "color": "#6c757d",
        "icon": "🚫",
    },
}


def format_facebook_url(post_id: str | None) -> str | None:
    """Format a Facebook post ID into a direct clickable Facebook URL.

    Args:
        post_id: Raw post ID string (e.g. '123456_789012') or full URL.

    Returns:
        Formatted full URL, or None if post_id is empty.
    """
    if not post_id or not str(post_id).strip():
        return None

    clean_id = str(post_id).strip()
    if clean_id.startswith(("http://", "https://")):
        return clean_id

    return f"https://www.facebook.com/{clean_id}"


def validate_schedule_datetime_fb(
    dt: datetime, now: datetime | None = None
) -> tuple[bool, str | None, int | None]:
    """Validate scheduled datetime for Meta Facebook Graph API.

    Facebook API requirement:
    Must be between 10 minutes (600 seconds) and 75 days (75 * 86400 seconds) in the future.

    Args:
        dt: Desired scheduled datetime.
        now: Optional current datetime reference (defaults to datetime.now()).

    Returns:
        tuple (is_valid, error_message, unix_timestamp)
    """
    ref_now = now or datetime.now()
    diff = (dt - ref_now).total_seconds()

    min_seconds = 10 * 60  # 10 minutes
    max_seconds = 75 * 86400  # 75 days

    if diff < min_seconds:
        return (
            False,
            "Thời gian hẹn giờ Facebook phải cách thời điểm hiện tại ít nhất 10 phút.",
            None,
        )

    if diff > max_seconds:
        return (
            False,
            "Thời gian hẹn giờ Facebook không được vượt quá 75 ngày kể từ thời điểm hiện tại.",
            None,
        )

    return True, None, int(dt.timestamp())


def validate_schedule_datetime_local(
    dt: datetime, now: datetime | None = None
) -> tuple[bool, str | None]:
    """Validate scheduled datetime for APScheduler Local scheduling.

    Local requirement:
    Must be strictly in the future compared to current time.

    Args:
        dt: Desired scheduled datetime.
        now: Optional current datetime reference (defaults to datetime.now()).

    Returns:
        tuple (is_valid, error_message)
    """
    ref_now = now or datetime.now()
    if dt <= ref_now:
        return False, "Thời gian hẹn giờ Local phải ở tương lai."

    return True, None


def get_status_badge(status: str) -> dict[str, str]:
    """Return styling dictionary for a post status badge.

    Args:
        status: Post status string (e.g. 'published', 'scheduled_fb', etc.).

    Returns:
        dict with keys: 'label', 'color', 'icon'.
    """
    clean_status = (status or "").strip().lower()
    if clean_status in STATUS_MAP:
        return STATUS_MAP[clean_status]

    return {
        "label": status or "N/A",
        "color": "#6c757d",
        "icon": "ℹ️",
    }


def render_status_badge_html(status: str) -> str:
    """Render an HTML badge pill for the given post status.

    Args:
        status: Post status string.

    Returns:
        HTML formatted string.
    """
    info = get_status_badge(status)
    return (
        f'<span style="background-color: {info["color"]}; color: #ffffff; '
        f'padding: 3px 8px; border-radius: 12px; font-size: 0.82rem; '
        f'font-weight: 500; display: inline-flex; align-items: center; gap: 4px;">'
        f'{info["icon"]} {info["label"]}</span>'
    )


def save_uploaded_file(uploaded_file: Any, upload_dir: str = "data/uploads") -> str:
    """Save an uploaded file from Streamlit or test buffer to the uploads directory.

    Args:
        uploaded_file: Streamlit UploadedFile or file-like object with .name and .getbuffer()/.read().
        upload_dir: Destination directory.

    Returns:
        Path string to the saved file.

    Raises:
        ValueError: If file is empty or cannot be saved.
    """
    os.makedirs(upload_dir, exist_ok=True)

    # Read bytes
    if hasattr(uploaded_file, "getbuffer"):
        data = bytes(uploaded_file.getbuffer())
    elif hasattr(uploaded_file, "read"):
        data = uploaded_file.read()
    else:
        raise ValueError("Đối tượng upload không hỗ trợ đọc dữ liệu.")

    if not data or len(data) == 0:
        raise ValueError("File tải lên rỗng (0 bytes).")

    # Sanitize original name
    original_name = getattr(uploaded_file, "name", "upload.jpg")
    safe_name = re.sub(r"[^a-zA-Z0-9_\.-]", "_", original_name)
    timestamp = int(time.time() * 1000)
    filename = f"{timestamp}_{safe_name}"

    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(data)

    return os.path.normpath(file_path)


def mask_token(
    token: str | None, visible_prefix: int = 4, visible_suffix: int = 4
) -> str:
    """Mask a secret token, keeping only the start and end visible.

    Args:
        token: Raw secret string.
        visible_prefix: Number of prefix characters to show.
        visible_suffix: Number of suffix characters to show.

    Returns:
        Masked string (e.g. 'EAAX...b8CD').
    """
    if not token or not str(token).strip():
        return "***"

    clean = str(token).strip()
    if len(clean) <= (visible_prefix + visible_suffix + 2):
        return "***"

    return f"{clean[:visible_prefix]}...{clean[-visible_suffix:]}"


def save_env_config(updates: dict[str, str], env_path: str = ".env") -> bool:
    """Safely update keys in .env file and active os.environ.

    Args:
        updates: Key-value dictionary of settings to save.
        env_path: Path to the .env file.

    Returns:
        True if successfully saved.
    """
    if not os.path.exists(env_path):
        dirname = os.path.dirname(env_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# Environment Configuration\n")

    for key, val in updates.items():
        clean_key = str(key).strip()
        clean_val = str(val).strip() if val is not None else ""
        set_key(env_path, clean_key, clean_val)
        os.environ[clean_key] = clean_val

    return True


def load_env_config(env_path: str = ".env") -> dict[str, str]:
    """Load configuration keys from active os.environ or .env file fallback.

    Args:
        env_path: Path to .env file.

    Returns:
        Dictionary containing GEMINI_API_KEY, FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN.
    """
    env_file_vals = {}
    if os.path.exists(env_path):
        env_file_vals = dotenv_values(env_path)

    keys = [
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "FB_PAGE_ID",
        "FB_PAGE_ACCESS_TOKEN",
    ]
    result: dict[str, str] = {}
    for key in keys:
        # Prioritize values from .env file over stale OS environment variables
        val = env_file_vals.get(key)
        if val is None or val == "":
            val = os.environ.get(key, "") or ""
        val_clean = str(val).strip()
        result[key] = val_clean
        if val_clean:
            os.environ[key] = val_clean

    return result
