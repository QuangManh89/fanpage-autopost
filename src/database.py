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
        """Create and return a SQLite connection with Row row_factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize the database schema if tables do not exist."""
        self._ensure_dir()
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS posts (
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
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()

    def save_post(
        self,
        topic: str,
        content: str,
        image_path: str | None = None,
        status: str = "draft",
        scheduled_time: str | None = None,
        fb_post_id: str | None = None,
    ) -> int:
        """Save a new post record and return its generated ID."""
        sql = """
        INSERT INTO posts (topic, content, image_path, status, scheduled_time, fb_post_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (topic, content, image_path, status, scheduled_time, fb_post_id),
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

    def get_all_posts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve latest posts ordered by ID descending."""
        sql = "SELECT * FROM posts ORDER BY id DESC LIMIT ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (limit,))
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
