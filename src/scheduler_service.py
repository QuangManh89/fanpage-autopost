"""Local Scheduler Service using APScheduler for Facebook Fanpage Auto-Poster."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler

from src.database import DatabaseManager
from src.facebook_service import FacebookService

logger = logging.getLogger(__name__)

__all__ = ["LocalSchedulerService"]


class LocalSchedulerService:
    """Manages local background scheduling of posts using APScheduler.

    Coordinates between SQLite database and FacebookService to publish posts
    at designated local run times.
    """

    def __init__(
        self,
        db: DatabaseManager,
        fb_service_provider: Callable[[], FacebookService] | FacebookService,
        scheduler: BackgroundScheduler | None = None,
    ) -> None:
        """Initialize LocalSchedulerService.

        Args:
            db: DatabaseManager instance for reading and updating post statuses.
            fb_service_provider: Either a callable returning a FacebookService or a
                                  direct FacebookService instance.
            scheduler: Optional BackgroundScheduler instance (creates a new one if None).
        """
        self.db = db
        self.fb_service_provider = fb_service_provider
        self.scheduler: BackgroundScheduler = scheduler or BackgroundScheduler()

    @property
    def is_running(self) -> bool:
        """Return True if background scheduler is active and running."""
        return bool(self.scheduler and self.scheduler.running)

    def start(self) -> None:
        """Start the background scheduler if not already running."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler LocalSchedulerService started.")

    def shutdown(self, wait: bool = False) -> None:
        """Shut down the background scheduler if currently running.

        Args:
            wait: If True, wait for currently executing jobs to finish.
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("APScheduler LocalSchedulerService stopped.")

    def __enter__(self) -> LocalSchedulerService:
        """Context manager entry point."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit point."""
        self.shutdown(wait=False)

    def get_job(self, job_id: str) -> Job | None:
        """Retrieve an active scheduled job by its job_id.

        Tolerates passing either '123' or 'post_123'.

        Args:
            job_id: APScheduler job identifier.

        Returns:
            Job instance if found, None otherwise.
        """
        job = self.scheduler.get_job(job_id)
        if job is None and not job_id.startswith("post_"):
            job = self.scheduler.get_job(f"post_{job_id}")
        return job

    def schedule_post(self, post_id: int, run_date: datetime | str) -> str:
        """Schedule a post to be published at a specified datetime.

        Args:
            post_id: Database ID of the post.
            run_date: Scheduled execution time as a datetime object or ISO string.

        Returns:
            job_id: Unique string identifier for the scheduled job (e.g. 'post_12').

        Raises:
            ValueError: If post does not exist or run_date cannot be parsed.
        """
        post = self.db.get_post_by_id(post_id)
        if post is None:
            raise ValueError(f"Không tìm thấy bài viết với ID: {post_id}")

        if isinstance(run_date, str):
            try:
                run_date = datetime.fromisoformat(run_date)
            except Exception as exc:
                raise ValueError(
                    f"Định dạng thời gian run_date không hợp lệ ({run_date}): {exc}"
                ) from exc

        if not isinstance(run_date, datetime):
            raise ValueError("run_date phải là một đối tượng datetime hoặc chuỗi ISO.")

        job_id = f"post_{post_id}"

        # Register or update date job in APScheduler
        self.scheduler.add_job(
            func=self.execute_post_job,
            trigger="date",
            run_date=run_date,
            args=[post_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,
        )

        # Update database status to scheduled_local
        if post["status"] != "scheduled_local":
            self.db.update_post_status(post_id=post_id, status="scheduled_local")

        logger.info(
            f"Scheduled post ID {post_id} at {run_date} with job ID '{job_id}'."
        )
        return job_id

    def cancel_scheduled_post(self, job_id: str) -> bool:
        """Cancel a scheduled post job in APScheduler and mark as cancelled in DB.

        Args:
            job_id: Job identifier (e.g. 'post_12' or '12').

        Returns:
            True if job was found and cancelled, False otherwise.
        """
        job = self.get_job(job_id)
        if job is None:
            return False

        actual_id = job.id
        try:
            self.scheduler.remove_job(actual_id)
        except Exception as exc:
            logger.warning(f"Error removing job {actual_id}: {exc}")

        # Update status in database if post was in scheduled_local state
        try:
            raw_id = actual_id.replace("post_", "")
            if raw_id.isdigit():
                pid = int(raw_id)
                post = self.db.get_post_by_id(pid)
                if post and post["status"] == "scheduled_local":
                    self.db.update_post_status(post_id=pid, status="cancelled")
        except Exception as exc:
            logger.warning(f"Error updating post status after cancellation: {exc}")

        logger.info(f"Cancelled scheduled post job '{actual_id}'.")
        return True

    def execute_post_job(self, post_id: int) -> bool:
        """Execute publishing of a single post by post_id.

        Invoked by APScheduler when trigger fires, or called directly.
        Ensures thread safety and safe exception handling so background scheduler
        does not crash.

        Args:
            post_id: Database ID of post to publish.

        Returns:
            True if post was successfully published, False if skipped or failed.
        """
        post = self.db.get_post_by_id(post_id)
        if post is None:
            logger.warning(f"Bài viết ID {post_id} không tồn tại trong database.")
            return False

        # Avoid duplicate posting if already published or cancelled
        current_status = post.get("status")
        if current_status in ("published", "cancelled"):
            logger.info(
                f"Bỏ qua bài viết {post_id} do trạng thái hiện tại là '{current_status}'."
            )
            return False

        # Resolve FacebookService
        try:
            if callable(self.fb_service_provider):
                fb_service = self.fb_service_provider()
            else:
                fb_service = self.fb_service_provider
        except Exception as exc:
            err_msg = f"Không thể lấy FacebookService: {exc}"
            logger.error(err_msg, exc_info=True)
            self.db.update_post_status(
                post_id=post_id,
                status="failed",
                error_message=err_msg,
            )
            return False

        content = post.get("content", "")
        image_path = post.get("image_path")

        try:
            if image_path and str(image_path).strip():
                clean_img_path = str(image_path).strip()
                result = fb_service.publish_photo_post(
                    message=content,
                    photo_path=clean_img_path,
                )
            else:
                result = fb_service.publish_text_post(
                    message=content,
                )

            fb_post_id = result.get("post_id") or result.get("id")
            self.db.update_post_status(
                post_id=post_id,
                status="published",
                fb_post_id=str(fb_post_id) if fb_post_id else None,
            )
            logger.info(
                f"Đăng bài viết {post_id} thành công lên Facebook (fb_post_id={fb_post_id})."
            )
            return True

        except Exception as exc:
            user_msg = getattr(exc, "user_message", None)
            err_text = str(user_msg or exc)
            logger.error(
                f"Lỗi khi đăng bài viết {post_id} lên Facebook: {err_text}",
                exc_info=True,
            )
            self.db.update_post_status(
                post_id=post_id,
                status="failed",
                error_message=err_text,
            )
            return False

    def load_and_reschedule_pending_jobs(
        self, execute_overdue: bool = False
    ) -> int:
        """Restore pending local scheduled posts from database into APScheduler.

        Intended to be called on application startup.
        - Future scheduled posts are registered with APScheduler.
        - Overdue posts (run_date in the past):
            - If execute_overdue is False (default): marked as failed with explanation.
            - If execute_overdue is True: published immediately.

        Args:
            execute_overdue: Whether to immediately publish overdue posts.

        Returns:
            Number of successfully rescheduled future posts (or executed overdue posts).
        """
        pending_posts = self.db.get_pending_local_scheduled_posts()
        rescheduled_count = 0

        for post in pending_posts:
            post_id = post["id"]
            sched_time_str = post.get("scheduled_time")

            if not sched_time_str:
                self.db.update_post_status(
                    post_id=post_id,
                    status="failed",
                    error_message="Bài viết không có thời gian hẹn giờ (scheduled_time).",
                )
                continue

            # Parse scheduled datetime
            run_date: datetime | None = None
            try:
                run_date = datetime.fromisoformat(sched_time_str)
            except Exception:
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                ):
                    try:
                        run_date = datetime.strptime(sched_time_str, fmt)
                        break
                    except Exception:
                        pass

            if run_date is None:
                self.db.update_post_status(
                    post_id=post_id,
                    status="failed",
                    error_message=f"Định dạng thời gian không hợp lệ: {sched_time_str}",
                )
                continue

            # Determine whether time has already passed
            if run_date.tzinfo is not None:
                now = datetime.now(run_date.tzinfo)
            else:
                now = datetime.now()

            if run_date < now:
                if execute_overdue:
                    if self.execute_post_job(post_id):
                        rescheduled_count += 1
                else:
                    self.db.update_post_status(
                        post_id=post_id,
                        status="failed",
                        error_message="Thời gian hẹn giờ đã qua khi ứng dụng khởi động lại.",
                    )
            else:
                try:
                    self.schedule_post(post_id=post_id, run_date=run_date)
                    rescheduled_count += 1
                except Exception as exc:
                    self.db.update_post_status(
                        post_id=post_id,
                        status="failed",
                        error_message=f"Không thể lên lịch bài viết: {exc}",
                    )

        logger.info(
            f"Restored {rescheduled_count} pending local scheduled posts from database."
        )
        return rescheduled_count
