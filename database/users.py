"""
توابع کار با جدول کاربران.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

from database.db import get_connection
from config import get_rank, POINTS_PER_INVITE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_user(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def get_or_create_user(user_id: int, username: str | None) -> sqlite3.Row:
    """
    اگه کاربر وجود نداشت می‌سازتش (با وضعیت ثبت‌نام نشده)،
    اگه بود، username رو در صورت تغییر آپدیت می‌کنه.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        now = _now()
        if row is None:
            conn.execute(
                """INSERT INTO users (user_id, username, registration_step,
                                       registered_at, last_active_at)
                   VALUES (?, ?, 'not_started', ?, ?)""",
                (user_id, username, now, now),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        else:
            conn.execute(
                "UPDATE users SET username = ?, last_active_at = ? WHERE user_id = ?",
                (username, now, user_id),
            )
        return row


def touch_last_active(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_active_at = ? WHERE user_id = ?",
            (_now(), user_id),
        )


def set_registration_step(user_id: int, step: str) -> None:
    valid_steps = {
        "not_started", "awaiting_name", "awaiting_grade",
        "awaiting_major", "awaiting_confirm", "done",
    }
    if step not in valid_steps:
        raise ValueError(f"مرحله‌ی ثبت‌نام نامعتبر: {step}")
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET registration_step = ? WHERE user_id = ?",
            (step, user_id),
        )


def set_full_name(user_id: int, full_name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET full_name = ? WHERE user_id = ?",
            (full_name.strip(), user_id),
        )


def set_grade(user_id: int, grade: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET grade = ? WHERE user_id = ?", (grade, user_id)
        )


def set_major(user_id: int, major: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET major = ? WHERE user_id = ?", (major, user_id)
        )


def complete_registration(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE users SET registration_step = 'done',
                                 registered_at = ? WHERE user_id = ?""",
            (_now(), user_id),
        )


def is_registered(user_id: int) -> bool:
    row = get_user(user_id)
    return row is not None and row["registration_step"] == "done"


def set_referrer(user_id: int, referrer_id: int) -> bool:
    """
    فقط اگه کاربر قبلاً معرف نداشته باشه و معرف با خودش یکی نباشه، ثبت می‌شه.
    برمی‌گردونه که آیا ثبت موفق بود یا نه (برای جلوگیری از دور زدن سیستم امتیاز).
    """
    if user_id == referrer_id:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT referred_by FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None or row["referred_by"] is not None:
            return False
        referrer = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (referrer_id,)
        ).fetchone()
        if referrer is None:
            return False
        conn.execute(
            "UPDATE users SET referred_by = ? WHERE user_id = ?",
            (referrer_id, user_id),
        )
        conn.execute(
            """UPDATE users SET invited_count = invited_count + 1,
                                 points = points + ?,
                                 weekly_points = weekly_points + ?
               WHERE user_id = ?""",
            (POINTS_PER_INVITE, POINTS_PER_INVITE, referrer_id),
        )
        return True


def add_points(user_id: int, points: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE users SET points = points + ?,
                                 weekly_points = weekly_points + ?
               WHERE user_id = ?""",
            (points, points, user_id),
        )


def get_user_overview(user_id: int) -> dict | None:
    """آمار کامل برای نمایش کارنامه/پروفایل: امتیاز، مقام، تعداد تست و درصد کلی."""
    with get_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if user is None:
            return None
        stats = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
               FROM exam_answers
               WHERE session_id IN (
                   SELECT id FROM exam_sessions WHERE user_id = ?
               ) AND selected_option IS NOT NULL""",
            (user_id,),
        ).fetchone()
        total = stats["total"] or 0
        correct = stats["correct"] or 0
        percent = round((correct / total) * 100) if total else 0
        return {
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "username": user["username"],
            "grade": user["grade"],
            "major": user["major"],
            "points": user["points"],
            "weekly_points": user["weekly_points"],
            "rank": get_rank(user["points"]),
            "total_tests": total,
            "correct_tests": correct,
            "overall_percent": percent,
            "invited_count": user["invited_count"],
            "registered_at": user["registered_at"],
            "last_active_at": user["last_active_at"],
        }


def get_subject_breakdown(user_id: int) -> list[dict]:
    """درصد کاربر به تفکیک درس (برای نمودار کارنامه)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT tb.subject AS subject,
                      COUNT(*) AS total,
                      SUM(CASE WHEN ea.is_correct = 1 THEN 1 ELSE 0 END) AS correct
               FROM exam_answers ea
               JOIN exam_sessions es ON ea.session_id = es.id
               JOIN chapters c ON es.chapter_id = c.id
               JOIN test_books tb ON c.test_book_id = tb.id
               WHERE es.user_id = ? AND ea.selected_option IS NOT NULL
               GROUP BY tb.subject
               ORDER BY tb.subject""",
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            total = r["total"] or 0
            correct = r["correct"] or 0
            percent = round((correct / total) * 100) if total else 0
            result.append({"subject": r["subject"], "total": total,
                            "correct": correct, "percent": percent})
        return result


def get_weakest_topic(user_id: int) -> dict | None:
    """ضعیف‌ترین مبحث (درس-فصل) بر اساس کمترین درصد، حداقل ۵ تست پاسخ‌داده‌شده."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT tb.subject AS subject, c.name AS chapter_name,
                      COUNT(*) AS total,
                      SUM(CASE WHEN ea.is_correct = 1 THEN 1 ELSE 0 END) AS correct
               FROM exam_answers ea
               JOIN exam_sessions es ON ea.session_id = es.id
               JOIN chapters c ON es.chapter_id = c.id
               JOIN test_books tb ON c.test_book_id = tb.id
               WHERE es.user_id = ? AND ea.selected_option IS NOT NULL
               GROUP BY tb.subject, c.name
               HAVING total >= 5
               ORDER BY (CAST(correct AS FLOAT) / total) ASC
               LIMIT 1""",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        percent = round((row["correct"] / row["total"]) * 100)
        return {"subject": row["subject"], "chapter": row["chapter_name"],
                "percent": percent}


# ==================== لیدربورد ====================

def get_leaderboard(weekly: bool, limit: int = 10) -> list[sqlite3.Row]:
    field = "weekly_points" if weekly else "points"
    with get_connection() as conn:
        return conn.execute(
            f"""SELECT user_id, full_name, {field} AS score
                FROM users
                WHERE registration_step = 'done'
                ORDER BY {field} DESC, user_id ASC
                LIMIT ?""",
            (limit,),
        ).fetchall()


def get_user_rank_position(user_id: int, weekly: bool) -> tuple[int, int] | None:
    """برمی‌گردونه (رتبه کاربر, تعداد کل کاربران ثبت‌نام‌شده)."""
    field = "weekly_points" if weekly else "points"
    with get_connection() as conn:
        user = conn.execute(
            f"SELECT {field} AS score FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if user is None:
            return None
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE registration_step = 'done'"
        ).fetchone()["c"]
        higher = conn.execute(
            f"""SELECT COUNT(*) AS c FROM users
                WHERE registration_step = 'done' AND {field} > ?""",
            (user["score"],),
        ).fetchone()["c"]
        return higher + 1, total


def reset_weekly_points() -> None:
    """هر جمعه شب صدا زده می‌شه (توسط job scheduler)."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET weekly_points = 0")


# ==================== جستجو و لیست کاربران (پنل ادمین) ====================

def search_user(query: str) -> sqlite3.Row | None:
    """جستجو با آیدی عددی یا یوزرنیم (با یا بدون @)."""
    query = query.strip().lstrip("@")
    with get_connection() as conn:
        if query.isdigit():
            return conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(query),)
            ).fetchone()
        return conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (query,)
        ).fetchone()


def list_users_page(page: int, page_size: int) -> list[sqlite3.Row]:
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM users WHERE registration_step = 'done'
               ORDER BY registered_at DESC LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()


def count_registered_users() -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE registration_step = 'done'"
        ).fetchone()["c"]


def _count_registered_since(days: int) -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT COUNT(*) AS c FROM users
               WHERE registration_step = 'done' AND registered_at >= ?""",
            (since,),
        ).fetchone()["c"]


def count_registered_today() -> int:
    return _count_registered_since(1)


def count_registered_this_week() -> int:
    return _count_registered_since(7)


def count_registered_this_month() -> int:
    return _count_registered_since(30)


def count_tests_answered_today() -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT COUNT(*) AS c FROM exam_answers
               WHERE answered_at >= ? AND selected_option IS NOT NULL""",
            (since,),
        ).fetchone()["c"]


def count_active_users_today() -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT COUNT(*) AS c FROM users
               WHERE last_active_at >= ? AND registration_step = 'done'""",
            (since,),
        ).fetchone()["c"]


def get_all_registered_user_ids() -> list[int]:
    """برای پیام همگانی."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE registration_step = 'done'"
        ).fetchall()
        return [r["user_id"] for r in rows]
