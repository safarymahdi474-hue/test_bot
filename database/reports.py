"""
توابع کار با گزارش اشکال تست و تاریخچه‌ی اصلاحات ادمین.
"""
import sqlite3
from datetime import datetime, timezone

from database.db import get_connection
from database.content import VALID_QUESTION_FIELDS

VALID_REPORT_TYPES = {"wrong_options", "wrong_answer", "bad_text", "other"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_question_report(question_id: int, user_id: int, report_type: str,
                            description: str | None = None) -> sqlite3.Row:
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"نوع گزارش نامعتبر: {report_type}")
    with get_connection() as conn:
        q = conn.execute(
            "SELECT id FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if q is None:
            raise ValueError("سوال پیدا نشد")
        cur = conn.execute(
            """INSERT INTO question_reports
               (question_id, user_id, report_type, description, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (question_id, user_id, report_type, description, _now()),
        )
        return conn.execute(
            "SELECT * FROM question_reports WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def count_pending_report_groups() -> int:
    """تعداد سوالاتِ متمایزی که گزارش در انتظار بررسی دارن."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT COUNT(DISTINCT question_id) AS c
               FROM question_reports WHERE status = 'pending'"""
        ).fetchone()["c"]


def list_pending_report_groups(page: int = 1, page_size: int = 10) -> list[dict]:
    """
    گزارش‌های در انتظار بررسی، گروه‌بندی‌شده بر اساس سوال (نه هر گزارش جدا).
    هر آیتم شامل اطلاعات سوال + تعداد گزارش‌ها + آخرین نوع گزارش‌هاست.
    """
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        groups = conn.execute(
            """SELECT question_id, COUNT(*) AS report_count,
                      MAX(created_at) AS latest_report_at
               FROM question_reports
               WHERE status = 'pending'
               GROUP BY question_id
               ORDER BY latest_report_at DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()

        result = []
        for g in groups:
            q_info = conn.execute(
                """SELECT q.id, q.number, q.question_image_file_id, tb.subject, tb.name AS book_name,
                          c.name AS chapter_name, tb.grade, tb.major
                   FROM questions q
                   JOIN chapters c ON q.chapter_id = c.id
                   JOIN test_books tb ON c.test_book_id = tb.id
                   WHERE q.id = ?""",
                (g["question_id"],),
            ).fetchone()
            result.append({
                "question_id": g["question_id"],
                "report_count": g["report_count"],
                "latest_report_at": g["latest_report_at"],
                "question": dict(q_info) if q_info else None,
            })
        return result


def get_pending_reports_for_question(question_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM question_reports
               WHERE question_id = ? AND status = 'pending'
               ORDER BY created_at""",
            (question_id,),
        ).fetchall()


def resolve_reports_for_question(question_id: int, admin_id: int,
                                  accepted: bool, admin_note: str | None = None) -> int:
    """
    تمام گزارش‌های در انتظار برای یک سوال رو resolved یا rejected می‌کنه.
    برمی‌گردونه تعداد گزارش‌هایی که بسته شدن.
    """
    status = "resolved" if accepted else "rejected"
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE question_reports
               SET status = ?, resolved_at = ?, resolved_by = ?, admin_note = ?
               WHERE question_id = ? AND status = 'pending'""",
            (status, _now(), admin_id, admin_note, question_id),
        )
        return cur.rowcount


def get_reporters_for_question(question_id: int) -> list[int]:
    """آیدی کاربرانی که برای این سوال گزارش pending یا تازه‌resolved داده‌ن (برای اطلاع‌رسانی)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT user_id FROM question_reports WHERE question_id = ?""",
            (question_id,),
        ).fetchall()
        return [r["user_id"] for r in rows]


# ==================== اصلاح سوال توسط ادمین (با ثبت لاگ) ====================

def edit_question_with_log(question_id: int, admin_id: int, field: str, new_value) -> bool:
    """
    یک فیلد از سوال رو اصلاح می‌کنه و تغییر رو در question_edit_log ثبت می‌کنه.
    هر دو عملیات (آپدیت سوال + ثبت لاگ) روی یک کانکشن مشترک انجام می‌شن،
    پس واقعاً اتمیک هستن: یا هر دو با موفقیت commit می‌شن، یا در صورت خطا
    هیچ‌کدوم اعمال نمی‌شن (rollback خودکار).
    برمی‌گردونه True اگه مقدار واقعاً تغییر کرده باشه، False اگه مقدار جدید
    با قدیم یکسان بوده (که در این حالت لاگ اضافه‌ای ثبت نمی‌شه).
    """
    if field not in VALID_QUESTION_FIELDS:
        raise ValueError(f"فیلد نامعتبر: {field}")
    if field == "correct_option" and int(new_value) not in (1, 2, 3, 4):
        raise ValueError("پاسخ صحیح باید بین ۱ تا ۴ باشه")

    with get_connection() as conn:
        old_row = conn.execute(
            f"SELECT {field} FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if old_row is None:
            raise ValueError("سوال پیدا نشد")
        old_value = str(old_row[field])
        new_value_str = str(new_value)

        if old_value == new_value_str:
            return False

        conn.execute(
            f"UPDATE questions SET {field} = ? WHERE id = ?",
            (new_value, question_id),
        )
        conn.execute(
            """INSERT INTO question_edit_log
               (question_id, admin_id, field_changed, old_value, new_value, changed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (question_id, admin_id, field, old_value, new_value_str, _now()),
        )
        return True


def get_edit_history(question_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM question_edit_log WHERE question_id = ?
               ORDER BY changed_at DESC""",
            (question_id,),
        ).fetchall()
