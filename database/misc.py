"""
توابع کار با:
- گزارش کتاب ناموجود در کتابخانه (book_requests)
- انتقاد و پیشنهاد (feedback)
- کانال‌های جوین اجباری (forced_channels)
"""
import sqlite3
from datetime import datetime, timezone

from database.db import get_connection

VALID_BOOK_REQUEST_STATUSES = {"pending", "added", "rejected", "unavailable", "custom_replied"}
FEEDBACK_HISTORY_LIMIT = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================== گزارش کتاب ناموجود ====================

def create_book_request(user_id: int, grade: str, major: str, subject: str) -> sqlite3.Row:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO book_requests (user_id, grade, major, subject, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (user_id, grade, major, subject, _now()),
        )
        return conn.execute(
            "SELECT * FROM book_requests WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def get_book_request(request_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM book_requests WHERE id = ?", (request_id,)
        ).fetchone()


def count_pending_book_requests() -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM book_requests WHERE status = 'pending'"
        ).fetchone()["c"]


def list_pending_book_requests(page: int = 1, page_size: int = 10) -> list[sqlite3.Row]:
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        return conn.execute(
            """SELECT br.*, u.full_name, u.username
               FROM book_requests br
               JOIN users u ON br.user_id = u.user_id
               WHERE br.status = 'pending'
               ORDER BY br.created_at
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()


def resolve_book_request(request_id: int, status: str, admin_response: str | None = None) -> None:
    if status not in VALID_BOOK_REQUEST_STATUSES or status == "pending":
        raise ValueError(f"وضعیت نامعتبر برای بستن گزارش: {status}")
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE book_requests SET status = ?, admin_response = ?, resolved_at = ?
               WHERE id = ? AND status = 'pending'""",
            (status, admin_response, _now(), request_id),
        )
        if cur.rowcount == 0:
            raise ValueError("گزارش پیدا نشد یا قبلاً بسته شده")


# ==================== انتقاد و پیشنهاد ====================

def create_feedback(user_id: int, message: str) -> sqlite3.Row:
    """
    پیام جدید ثبت می‌شه. طبق قانون «۱۰ پیام آخر»، اگه بیشتر از ۱۰ پیام
    برای این کاربر موجود باشه، قدیمی‌ترین‌ها حذف می‌شن.
    """
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO feedback (user_id, message, created_at)
               VALUES (?, ?, ?)""",
            (user_id, message.strip(), _now()),
        )
        new_id = cur.lastrowid

        # حذف قدیمی‌ترین پیام‌ها در صورت عبور از سقف ۱۰ تا
        old_ids = conn.execute(
            """SELECT id FROM feedback WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT -1 OFFSET ?""",
            (user_id, FEEDBACK_HISTORY_LIMIT),
        ).fetchall()
        if old_ids:
            conn.executemany(
                "DELETE FROM feedback WHERE id = ?", [(r["id"],) for r in old_ids]
            )

        return conn.execute("SELECT * FROM feedback WHERE id = ?", (new_id,)).fetchone()


def list_user_feedback(user_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM feedback WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, FEEDBACK_HISTORY_LIMIT),
        ).fetchall()


def get_feedback(feedback_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
        ).fetchone()


def count_pending_feedback() -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM feedback WHERE responded_at IS NULL"
        ).fetchone()["c"]


def list_pending_feedback(page: int = 1, page_size: int = 10) -> list[sqlite3.Row]:
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        return conn.execute(
            """SELECT f.*, u.full_name, u.username
               FROM feedback f
               JOIN users u ON f.user_id = u.user_id
               WHERE f.responded_at IS NULL
               ORDER BY f.created_at
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()


def respond_feedback(feedback_id: int, admin_response: str) -> None:
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE feedback SET admin_response = ?, responded_at = ?
               WHERE id = ? AND responded_at IS NULL""",
            (admin_response, _now(), feedback_id),
        )
        if cur.rowcount == 0:
            raise ValueError("پیام پیدا نشد یا قبلاً پاسخ داده شده")


# ==================== کانال‌های جوین اجباری ====================

def add_forced_channel(channel_id: str, title: str, invite_link: str) -> sqlite3.Row:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO forced_channels (channel_id, title, invite_link)
               VALUES (?, ?, ?)""",
            (channel_id, title, invite_link),
        )
        return conn.execute(
            "SELECT * FROM forced_channels WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def remove_forced_channel(channel_db_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM forced_channels WHERE id = ?", (channel_db_id,))


def list_forced_channels() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM forced_channels ORDER BY id").fetchall()
