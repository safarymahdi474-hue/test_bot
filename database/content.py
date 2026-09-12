"""
توابع کار با کتاب‌های تست، فصل‌ها و سوالات.
همچنین کتابخانه‌ی فایل‌های دانلودی (library_books).
"""
import sqlite3
from datetime import datetime, timezone

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================== کتابخانه (فایل‌های دانلودی) ====================

def get_library_book(grade: str, major: str, subject: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM library_books
               WHERE grade = ? AND major = ? AND subject = ?""",
            (grade, major, subject),
        ).fetchone()


def upsert_library_book_file(grade: str, major: str, subject: str, file_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO library_books (grade, major, subject, file_id, available)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(grade, major, subject)
               DO UPDATE SET file_id = excluded.file_id, available = 1""",
            (grade, major, subject, file_id),
        )


def list_library_books(grade: str, major: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM library_books WHERE grade = ? AND major = ?
               ORDER BY subject""",
            (grade, major),
        ).fetchall()


def count_library_books() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM library_books").fetchone()["c"]
        available = conn.execute(
            "SELECT COUNT(*) AS c FROM library_books WHERE available = 1"
        ).fetchone()["c"]
        return {"total": total, "available": available, "unavailable": total - available}


def list_all_library_books_page(page: int, page_size: int) -> list[sqlite3.Row]:
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM library_books ORDER BY grade, major, subject
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()


# ==================== کتاب‌های تست ====================

def get_or_create_test_book(grade: str, major: str, subject: str, name: str) -> sqlite3.Row:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM test_books
               WHERE grade=? AND major=? AND subject=? AND name=?""",
            (grade, major, subject, name),
        ).fetchone()
        if row:
            return row
        cur = conn.execute(
            """INSERT INTO test_books (grade, major, subject, name)
               VALUES (?, ?, ?, ?)""",
            (grade, major, subject, name),
        )
        return conn.execute(
            "SELECT * FROM test_books WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def list_test_books(grade: str, major: str, subject: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM test_books WHERE grade=? AND major=? AND subject=?
               ORDER BY name""",
            (grade, major, subject),
        ).fetchall()


def get_test_book(test_book_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM test_books WHERE id = ?", (test_book_id,)
        ).fetchone()


def list_all_test_books_summary() -> list[sqlite3.Row]:
    """برای نمایش «کتاب‌های ثبت‌شده» در پنل مدیریت تست‌ها."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT tb.*, COUNT(q.id) AS question_count
               FROM test_books tb
               LEFT JOIN chapters c ON c.test_book_id = tb.id
               LEFT JOIN questions q ON q.chapter_id = c.id
               GROUP BY tb.id
               ORDER BY tb.grade, tb.major, tb.subject, tb.name"""
        ).fetchall()


# ==================== فصل‌ها ====================

def get_or_create_chapter(test_book_id: int, name: str, order_index: int = 0) -> sqlite3.Row:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM chapters WHERE test_book_id=? AND name=?",
            (test_book_id, name),
        ).fetchone()
        if row:
            return row
        cur = conn.execute(
            """INSERT INTO chapters (test_book_id, name, order_index)
               VALUES (?, ?, ?)""",
            (test_book_id, name, order_index),
        )
        return conn.execute(
            "SELECT * FROM chapters WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def list_chapters(test_book_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM chapters WHERE test_book_id = ?
               ORDER BY order_index, id""",
            (test_book_id,),
        ).fetchall()


def get_chapter(chapter_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()


# ==================== سوالات ====================

def add_question(chapter_id: int, number: int, question_image_file_id: str,
                  correct_option: int, explanation_image_file_id: str | None = None) -> sqlite3.Row:
    if correct_option not in (1, 2, 3, 4):
        raise ValueError("پاسخ صحیح باید بین ۱ تا ۴ باشه")
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO questions
               (chapter_id, number, question_image_file_id, correct_option,
                explanation_image_file_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chapter_id, number, question_image_file_id, correct_option,
             explanation_image_file_id, _now()),
        )
        return conn.execute(
            "SELECT * FROM questions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def get_question(question_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()


def get_question_full_path(question_id: int) -> sqlite3.Row | None:
    """سوال به همراه اطلاعات فصل/کتاب/درس/پایه/رشته (برای نمایش در پنل ادمین)."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT q.*, c.name AS chapter_name, tb.name AS book_name,
                      tb.subject AS subject, tb.grade AS grade, tb.major AS major
               FROM questions q
               JOIN chapters c ON q.chapter_id = c.id
               JOIN test_books tb ON c.test_book_id = tb.id
               WHERE q.id = ?""",
            (question_id,),
        ).fetchone()


def get_questions_in_range(chapter_id: int, start: int, end: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM questions WHERE chapter_id = ?
               AND number BETWEEN ? AND ? ORDER BY number""",
            (chapter_id, start, end),
        ).fetchall()


def count_questions_in_chapter(chapter_id: int) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM questions WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()["c"]


def get_min_max_question_number(chapter_id: int) -> tuple[int, int] | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT MIN(number) AS mn, MAX(number) AS mx
               FROM questions WHERE chapter_id = ?""",
            (chapter_id,),
        ).fetchone()
        if row is None or row["mn"] is None:
            return None
        return row["mn"], row["mx"]


VALID_QUESTION_FIELDS = {
    "question_image_file_id": "عکس سوال",
    "correct_option": "پاسخ صحیح",
    "explanation_image_file_id": "عکس توضیح/پاسخ",
}


def update_question_field(question_id: int, field: str, new_value) -> tuple[str, str]:
    """
    یک فیلد از سوال رو آپدیت می‌کنه.
    برمی‌گردونه (مقدار قدیم, مقدار جدید) به‌صورت رشته، برای ثبت در لاگ.
    """
    if field not in VALID_QUESTION_FIELDS:
        raise ValueError(f"فیلد نامعتبر برای اصلاح سوال: {field}")
    if field == "correct_option" and int(new_value) not in (1, 2, 3, 4):
        raise ValueError("پاسخ صحیح باید بین ۱ تا ۴ باشه")

    with get_connection() as conn:
        old_row = conn.execute(
            f"SELECT {field} FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if old_row is None:
            raise ValueError("سوال پیدا نشد")
        old_value = old_row[field]
        conn.execute(
            f"UPDATE questions SET {field} = ? WHERE id = ?",
            (new_value, question_id),
        )
        return str(old_value), str(new_value)


def count_total_questions() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
