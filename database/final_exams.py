"""
توابع کار با «امتحان نهایی» — فایل‌هایی که ادمین مستقیم توی ربات آپلود می‌کنه.
برخلاف کتابخانه (یک فایل ثابت به ازای هر درس)، هر درس می‌تونه چند امتحان
نهایی داشته باشه (مثلاً نوبت اول/دوم، سال‌های مختلف)، هر کدوم با یه عنوان.
"""
import sqlite3
from datetime import datetime, timezone

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_final_exam(grade: str, major: str, subject: str, title: str,
                    file_id: str, uploaded_by: int | None = None) -> sqlite3.Row:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO final_exams (grade, major, subject, title, file_id,
                                         uploaded_by, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (grade, major, subject, title.strip(), file_id, uploaded_by, _now()),
        )
        return conn.execute(
            "SELECT * FROM final_exams WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def list_final_exams(grade: str, major: str, subject: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM final_exams WHERE grade=? AND major=? AND subject=?
               ORDER BY uploaded_at DESC""",
            (grade, major, subject),
        ).fetchall()


def get_final_exam(exam_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM final_exams WHERE id = ?", (exam_id,)
        ).fetchone()


def delete_final_exam(exam_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM final_exams WHERE id = ?", (exam_id,))
        return cur.rowcount > 0


def count_final_exams() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM final_exams").fetchone()["c"]


def list_final_exam_subjects_summary() -> list[sqlite3.Row]:
    """برای پنل ادمین: هر (پایه/رشته/درس) با تعداد فایل‌هاش."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT grade, major, subject, COUNT(*) AS exam_count
               FROM final_exams
               GROUP BY grade, major, subject
               ORDER BY grade, major, subject"""
        ).fetchall()
