"""
تنظیمات کلید-مقداری ساده‌ی ربات (مثل لینک کانال اخبار).
"""
import sqlite3

from database.db import get_connection

NEWS_CHANNEL_TITLE_KEY = "news_channel_title"
NEWS_CHANNEL_LINK_KEY = "news_channel_link"


def get_setting(key: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM bot_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO bot_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )


def get_news_channel() -> dict | None:
    title = get_setting(NEWS_CHANNEL_TITLE_KEY)
    link = get_setting(NEWS_CHANNEL_LINK_KEY)
    if not title or not link:
        return None
    return {"title": title, "link": link}


def set_news_channel(title: str, link: str) -> None:
    set_setting(NEWS_CHANNEL_TITLE_KEY, title.strip())
    set_setting(NEWS_CHANNEL_LINK_KEY, link.strip())
