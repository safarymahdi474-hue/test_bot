"""
📢 تنظیم کانال اخبار (سمت ادمین) — عنوان و لینک کانالی که در پنل اصلی
به کاربرا نشون داده می‌شه.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import ADMIN_IDS
from database.settings import get_news_channel, set_news_channel

AWAITING_INPUT = 0


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def entry_news_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END

    current = get_news_channel()
    lines = ["📢 تنظیم کانال اخبار", "━━━━━━━━━━━━━━━"]
    if current:
        lines.append(f"وضعیت فعلی: {current['title']} — {current['link']}")
    else:
        lines.append("هنوز کانالی تنظیم نشده.")
    lines.append("")
    lines.append("عنوان و لینک جدید رو به این فرمت بفرست:\nعنوان | لینک")
    lines.append("مثال:\nکانال اخبار ما | https://t.me/our_news_channel")

    rows = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")]]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))
    return AWAITING_INPUT


async def receive_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if "|" not in text:
        await update.message.reply_text(
            "❌ فرمت اشتباهه. به این شکل بفرست:\nعنوان | لینک"
        )
        return AWAITING_INPUT

    title, _, link = text.partition("|")
    title, link = title.strip(), link.strip()
    if not title or not link.startswith(("http://", "https://", "t.me")):
        await update.message.reply_text(
            "❌ لینک باید با http یا https شروع بشه. دوباره بفرست:\nعنوان | لینک"
        )
        return AWAITING_INPUT

    set_news_channel(title, link)
    await update.message.reply_text(f"✅ کانال اخبار ثبت شد:\n{title}\n{link}")
    return ConversationHandler.END


def build_news_settings_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_news_settings, pattern=r"^admin:news_settings$")],
        states={
            AWAITING_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_input)],
        },
        fallbacks=[],
        name="admin_news_settings_conversation",
        persistent=False,
    )
