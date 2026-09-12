"""
مدیریت اتصال به دیتابیس SQLite.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from database.schema import SCHEMA

DB_PATH = Path(__file__).parent.parent / "bot_data.db"


def _connect(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(db_path: str | Path = DB_PATH):
    """
    Context manager برای گرفتن یک کانکشن.
    در پایان، commit خودکار انجام می‌شه؛ اگه خطا رخ بده rollback می‌شه.
    """
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path = DB_PATH) -> None:
    """ساخت تمام جدول‌ها در صورت عدم وجود."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
