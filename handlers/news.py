"""
📢 کانال اخبار — دکمه‌ی ساده در پنل اصلی که لینک کانال اخبار رو نشون می‌ده.
لینک/عنوان از پنل مدیریت قابل تنظیمه (database/settings.py).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database.settings import get_news_channel


async def show_news_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    channel = get_news_channel()

    if channel is None:
        text = "📢 کانال اخبار\n━━━━━━━━━━━━━━━\nهنوز کانال اخباری تنظیم نشده."
        rows = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")]]
    else:
        text = f"📢 کانال اخبار\n━━━━━━━━━━━━━━━\nبرای اطلاع از آخرین اخبار و به‌روزرسانی‌ها عضو شو:"
        rows = [
            [InlineKeyboardButton(f"📢 عضویت در {channel['title']}", url=channel["link"], style="primary")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")],
        ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


news_handler = CallbackQueryHandler(show_news_channel, pattern=r"^menu:news$")
