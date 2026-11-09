"""Database Manager for Fanpage Auto-Poster using SQLite."""

from __future__ import annotations

import os
import sqlite3
from typing import Any


class DatabaseManager:
    """Manages SQLite database storage for Facebook fanpage posts and scheduling."""

    def __init__(self, db_path: str = "data/fanpage.db") -> None:
        self.db_path = db_path
        self._ensure_dir()
        self.init_db()

    def _ensure_dir(self) -> None:
        """Create parent directory for the database if it doesn't exist."""
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a SQLite connection with Row row_factory, WAL mode, and 30s timeout."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.Error:
            pass
        return conn

    def init_db(self) -> None:
        """Initialize the database schema if tables do not exist and apply migrations."""
        self._ensure_dir()
        create_posts_table_sql = """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            status TEXT NOT NULL,
            scheduled_time TEXT,
            fb_post_id TEXT,
            error_message TEXT,
            page_id TEXT,
            page_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_fanpages_table_sql = """
        CREATE TABLE IF NOT EXISTS fanpages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id TEXT UNIQUE NOT NULL,
            page_name TEXT NOT NULL,
            access_token TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_posts_table_sql)
            cursor.execute(create_fanpages_table_sql)

            # Safe migration: ensure page_id and page_name columns exist in posts
            cursor.execute("PRAGMA table_info(posts)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "page_id" not in columns:
                cursor.execute("ALTER TABLE posts ADD COLUMN page_id TEXT;")
            if "page_name" not in columns:
                cursor.execute("ALTER TABLE posts ADD COLUMN page_name TEXT;")

            conn.commit()

    def save_post(
        self,
        topic: str,
        content: str,
        image_path: str | None = None,
        status: str = "draft",
        scheduled_time: str | None = None,
        fb_post_id: str | None = None,
        page_id: str | None = None,
        page_name: str | None = None,
    ) -> int:
        """Save a new post record and return its generated ID."""
        sql = """
        INSERT INTO posts (topic, content, image_path, status, scheduled_time, fb_post_id, page_id, page_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (topic, content, image_path, status, scheduled_time, fb_post_id, page_id, page_name),
            )
            conn.commit()
            last_id = cursor.lastrowid
            if last_id is None:
                raise RuntimeError("Failed to retrieve generated post ID.")
            return last_id

    def update_post_status(
        self,
        post_id: int,
        status: str,
        fb_post_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update status, fb_post_id, error_message, and timestamp for a post."""
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = [status]

        if fb_post_id is not None:
            updates.append("fb_post_id = ?")
            params.append(fb_post_id)

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        elif status == "published":
            updates.append("error_message = NULL")

        params.append(post_id)
        sql = f"UPDATE posts SET {', '.join(updates)} WHERE id = ?"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        """Retrieve a single post record by its ID."""
        sql = "SELECT * FROM posts WHERE id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (post_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def get_all_posts(self, limit: int = 50, page_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve latest posts ordered by ID descending, optionally filtered by page_id."""
        if page_id:
            sql = "SELECT * FROM posts WHERE page_id = ? ORDER BY id DESC LIMIT ?"
            params: tuple[Any, ...] = (page_id, limit)
        else:
            sql = "SELECT * FROM posts ORDER BY id DESC LIMIT ?"
            params = (limit,)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_pending_local_scheduled_posts(self) -> list[dict[str, Any]]:
        """Retrieve pending posts waiting for local scheduler dispatch."""
        sql = """
        SELECT * FROM posts
        WHERE status = 'scheduled_local'
        ORDER BY scheduled_time ASC, id ASC
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_post(self, post_id: int) -> bool:
        """Delete a post by its ID. Returns True if deleted, False if not found."""
        sql = "DELETE FROM posts WHERE id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (post_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== Fanpage Management Methods ====================

    def add_fanpage(
        self,
        page_id: str,
        page_name: str,
        access_token: str,
        is_active: int = 1,
    ) -> int:
        """Add or update a Facebook fanpage entry. Returns record ID."""
        sql = """
        INSERT INTO fanpages (page_id, page_name, access_token, is_active)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(page_id) DO UPDATE SET
            page_name = excluded.page_name,
            access_token = excluded.access_token,
            is_active = excluded.is_active,
            updated_at = CURRENT_TIMESTAMP
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (str(page_id).strip(), str(page_name).strip(), str(access_token).strip(), is_active),
            )
            conn.commit()
            last_id = cursor.lastrowid
            if last_id is None:
                # If updated, fetch existing id
                cursor.execute("SELECT id FROM fanpages WHERE page_id = ?", (str(page_id).strip(),))
                row = cursor.fetchone()
                return row["id"] if row else 0
            return last_id

    def get_fanpages(self, only_active: bool = False) -> list[dict[str, Any]]:
        """Retrieve fanpages list ordered by id ascending."""
        if only_active:
            sql = "SELECT * FROM fanpages WHERE is_active = 1 ORDER BY id ASC"
            params: tuple[Any, ...] = ()
        else:
            sql = "SELECT * FROM fanpages ORDER BY id ASC"
            params = ()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_fanpage_by_page_id(self, page_id: str) -> dict[str, Any] | None:
        """Retrieve a fanpage record by its Facebook page_id."""
        sql = "SELECT * FROM fanpages WHERE page_id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (str(page_id).strip(),))
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def update_fanpage(
        self,
        page_id: str,
        page_name: str | None = None,
        access_token: str | None = None,
        is_active: int | None = None,
    ) -> bool:
        """Update fanpage details. Returns True if row was updated."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []

        if page_name is not None:
            updates.append("page_name = ?")
            params.append(str(page_name).strip())

        if access_token is not None:
            updates.append("access_token = ?")
            params.append(str(access_token).strip())

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        params.append(str(page_id).strip())
        sql = f"UPDATE fanpages SET {', '.join(updates)} WHERE page_id = ?"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def delete_fanpage(self, page_id: str) -> bool:
        """Delete a fanpage record by its page_id. Returns True if deleted."""
        sql = "DELETE FROM fanpages WHERE page_id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (str(page_id).strip(),))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_fanpage_status(self, page_id: str) -> bool:
        """Toggle active/inactive status (1 <-> 0) for a fanpage."""
        sql = """
        UPDATE fanpages
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
            updated_at = CURRENT_TIMESTAMP
        WHERE page_id = ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (str(page_id).strip(),))
            conn.commit()
            return cursor.rowcount > 0

    def migrate_from_env(
        self,
        page_id: str,
        access_token: str,
        page_name: str = "Trang mặc định",
    ) -> bool:
        """Import fanpage credentials from .env if table is empty or page does not exist."""
        clean_id = str(page_id or "").strip()
        clean_token = str(access_token or "").strip()
        if not clean_id or not clean_token:
            return False

        existing = self.get_fanpage_by_page_id(clean_id)
        if existing:
            return False

        self.add_fanpage(
            page_id=clean_id,
            page_name=page_name,
            access_token=clean_token,
            is_active=1,
        )
        return True

