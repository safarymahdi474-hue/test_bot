"""
توابع کار با جلسات آزمون (شروع آزمون، ثبت پاسخ، پایان آزمون، کارنامه، اشتباهات).
"""
import sqlite3
from datetime import datetime, timezone

from database.db import get_connection
from database.content import get_questions_in_range
from config import POINTS_PER_CORRECT_ANSWER


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(user_id: int, chapter_id: int, start_number: int,
                    end_number: int, mode: str) -> sqlite3.Row:
    """
    یک جلسه‌ی آزمون جدید می‌سازه و ردیف‌های exam_answers خالی
    (unanswered) برای تمام سوالات محدوده از قبل ایجاد می‌کنه.
    این کار باعث می‌شه شمارش «پاسخ‌نداده» همیشه دقیق باشه، حتی اگه
    کاربر آزمون رو نیمه‌کاره رها کنه.
    """
    if mode not in ("timed", "free"):
        raise ValueError("حالت آزمون باید timed یا free باشه")
    if start_number > end_number:
        raise ValueError("شماره شروع نباید از پایان بزرگ‌تر باشه")

    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO exam_sessions
               (user_id, chapter_id, start_number, end_number, mode,
                status, current_index, started_at)
               VALUES (?, ?, ?, ?, ?, 'in_progress', 0, ?)""",
            (user_id, chapter_id, start_number, end_number, mode, _now()),
        )
        session_id = cur.lastrowid

        questions = conn.execute(
            """SELECT id FROM questions WHERE chapter_id = ?
               AND number BETWEEN ? AND ? ORDER BY number""",
            (chapter_id, start_number, end_number),
        ).fetchall()
        if not questions:
            raise ValueError("سوالی در این محدوده پیدا نشد")

        conn.executemany(
            """INSERT INTO exam_answers (session_id, question_id,
                                          selected_option, is_correct)
               VALUES (?, ?, NULL, NULL)""",
            [(session_id, q["id"]) for q in questions],
        )
        return conn.execute(
            "SELECT * FROM exam_sessions WHERE id = ?", (session_id,)
        ).fetchone()


def get_session(session_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM exam_sessions WHERE id = ?", (session_id,)
        ).fetchone()


def get_active_session(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM exam_sessions
               WHERE user_id = ? AND status = 'in_progress'
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()


def get_session_questions_ordered(session_id: int) -> list[sqlite3.Row]:
    """سوالات این جلسه، به همراه وضعیت پاسخ، به ترتیب شماره."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT q.*, ea.selected_option, ea.is_correct
               FROM exam_answers ea
               JOIN questions q ON ea.question_id = q.id
               WHERE ea.session_id = ?
               ORDER BY q.number""",
            (session_id,),
        ).fetchall()


def get_current_question(session_id: int) -> sqlite3.Row | None:
    session = get_session(session_id)
    if session is None:
        return None
    questions = get_session_questions_ordered(session_id)
    idx = session["current_index"]
    if idx < 0 or idx >= len(questions):
        return None
    return questions[idx]


def submit_answer(session_id: int, question_id: int, selected_option: int) -> dict:
    """
    ثبت پاسخ کاربر به یک سوال داخل جلسه.
    اگه قبلاً به این سوال پاسخ داده بود (و امتیازش رو گرفته بود)، امتیاز
    دوباره اضافه نمی‌شه (جلوگیری از duplicate scoring در صورت تغییر پاسخ).
    برمی‌گردونه: {"is_correct": bool, "correct_option": int, "newly_answered": bool}
    """
    if selected_option not in (1, 2, 3, 4):
        raise ValueError("گزینه‌ی انتخابی باید بین ۱ تا ۴ باشه")

    with get_connection() as conn:
        existing = conn.execute(
            """SELECT * FROM exam_answers
               WHERE session_id = ? AND question_id = ?""",
            (session_id, question_id),
        ).fetchone()
        if existing is None:
            raise ValueError("این سوال متعلق به این جلسه‌ی آزمون نیست")

        question = conn.execute(
            "SELECT correct_option FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        correct_option = question["correct_option"]
        is_correct = 1 if selected_option == correct_option else 0
        newly_answered = existing["selected_option"] is None

        conn.execute(
            """UPDATE exam_answers
               SET selected_option = ?, is_correct = ?, answered_at = ?
               WHERE session_id = ? AND question_id = ?""",
            (selected_option, is_correct, _now(), session_id, question_id),
        )

        session = conn.execute(
            "SELECT user_id FROM exam_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if newly_answered and is_correct:
            conn.execute(
                """UPDATE users SET points = points + ?, weekly_points = weekly_points + ?
                   WHERE user_id = ?""",
                (POINTS_PER_CORRECT_ANSWER, POINTS_PER_CORRECT_ANSWER, session["user_id"]),
            )
        elif not newly_answered:
            # کاربر پاسخش رو عوض کرده؛ امتیاز قبلی رو اصلاح می‌کنیم
            was_correct = existing["is_correct"] == 1
            if was_correct and not is_correct:
                conn.execute(
                    """UPDATE users SET points = points - ?, weekly_points = weekly_points - ?
                       WHERE user_id = ?""",
                    (POINTS_PER_CORRECT_ANSWER, POINTS_PER_CORRECT_ANSWER, session["user_id"]),
                )
            elif not was_correct and is_correct:
                conn.execute(
                    """UPDATE users SET points = points + ?, weekly_points = weekly_points + ?
                       WHERE user_id = ?""",
                    (POINTS_PER_CORRECT_ANSWER, POINTS_PER_CORRECT_ANSWER, session["user_id"]),
                )

        return {
            "is_correct": bool(is_correct),
            "correct_option": correct_option,
            "newly_answered": newly_answered,
        }


def advance_session(session_id: int) -> int:
    """اشاره‌گر سوال فعلی رو یکی جلو می‌بره. ایندکس جدید رو برمی‌گردونه."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE exam_sessions SET current_index = current_index + 1 WHERE id = ?",
            (session_id,),
        )
        return conn.execute(
            "SELECT current_index FROM exam_sessions WHERE id = ?", (session_id,)
        ).fetchone()["current_index"]


def finish_session(session_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE exam_sessions SET status='finished', finished_at=? WHERE id=?",
            (_now(), session_id),
        )


def get_session_stats(session_id: int) -> dict:
    with get_connection() as conn:
        session = conn.execute(
            "SELECT * FROM exam_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        agg = conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   SUM(CASE WHEN selected_option IS NOT NULL THEN 1 ELSE 0 END) AS answered,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                   SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS wrong
               FROM exam_answers WHERE session_id = ?""",
            (session_id,),
        ).fetchone()

        total = agg["total"] or 0
        answered = agg["answered"] or 0
        correct = agg["correct"] or 0
        wrong = agg["wrong"] or 0
        unanswered = total - answered
        percent = round((correct / total) * 100) if total else 0

        elapsed_seconds = None
        if session["started_at"]:
            end_time = session["finished_at"] or _now()
            start_dt = datetime.fromisoformat(session["started_at"])
            end_dt = datetime.fromisoformat(end_time)
            elapsed_seconds = int((end_dt - start_dt).total_seconds())

        return {
            "session_id": session_id,
            "status": session["status"],
            "total": total,
            "answered": answered,
            "correct": correct,
            "wrong": wrong,
            "unanswered": unanswered,
            "percent": percent,
            "points_earned": correct * POINTS_PER_CORRECT_ANSWER,
            "elapsed_seconds": elapsed_seconds,
        }


# ==================== اشتباهات کاربر (📖 دیدن اشتباهاتم) ====================

def get_user_mistakes_page(user_id: int, page: int, page_size: int) -> list[dict]:
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ea.selected_option, q.id AS question_id, q.number AS question_number,
                      q.question_image_file_id, q.correct_option,
                      q.explanation_image_file_id, c.name AS chapter_name,
                      tb.subject AS subject, tb.name AS book_name, ea.answered_at
               FROM exam_answers ea
               JOIN exam_sessions es ON ea.session_id = es.id
               JOIN questions q ON ea.question_id = q.id
               JOIN chapters c ON q.chapter_id = c.id
               JOIN test_books tb ON c.test_book_id = tb.id
               WHERE es.user_id = ? AND ea.is_correct = 0
               ORDER BY ea.answered_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def count_user_mistakes(user_id: int, cap: int | None = None) -> int:
    with get_connection() as conn:
        if cap:
            row = conn.execute(
                """SELECT COUNT(*) AS c FROM (
                       SELECT ea.id FROM exam_answers ea
                       JOIN exam_sessions es ON ea.session_id = es.id
                       WHERE es.user_id = ? AND ea.is_correct = 0
                       ORDER BY ea.answered_at DESC LIMIT ?
                   )""",
                (user_id, cap),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT COUNT(*) AS c FROM exam_answers ea
                   JOIN exam_sessions es ON ea.session_id = es.id
                   WHERE es.user_id = ? AND ea.is_correct = 0""",
                (user_id,),
            ).fetchone()
        return row["c"]
