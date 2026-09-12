"""
⚙️ تنظیم جوین اجباری.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from config import ADMIN_IDS
from database.misc import add_forced_channel, remove_forced_channel, list_forced_channels

AWAITING_ADD_LINE = 0


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def show_channels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    channels = list_forced_channels()
    lines = ["⚙️ تنظیم جوین اجباری", "━━━━━━━━━━━━━━━", "📢 کانال‌های فعلی:", ""]
    if not channels:
        lines.append("هیچ کانالی تنظیم نشده.")
    for i, ch in enumerate(channels, start=1):
        lines.append(f"{i}. {ch['title']} — {ch['channel_id']}")

    rows = [
        [InlineKeyboardButton("➕ افزودن کانال", callback_data="admin:add_channel")],
        [InlineKeyboardButton("🗑 حذف کانال", callback_data="admin:remove_channel_menu")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")],
    ]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def ask_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END
    await query.edit_message_text(
        "➕ افزودن کانال\n\nفرمت ارسال کن:\nآیدی | عنوان | لینک\n\n"
        "مثال:\n@mychannel | کانال اصلی | https://t.me/mychannel"
    )
    return AWAITING_ADD_LINE


async def receive_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parts = [p.strip() for p in (update.message.text or "").split("|")]
    if len(parts) != 3 or not all(parts):
        await update.message.reply_text("❌ فرمت اشتباهه. دوباره بفرست:\nآیدی | عنوان | لینک")
        return AWAITING_ADD_LINE

    channel_id, title, link = parts
    try:
        add_forced_channel(channel_id, title, link)
        await update.message.reply_text("✅ کانال اضافه شد!")
    except Exception:
        await update.message.reply_text("❌ این کانال قبلاً اضافه شده.")
    return ConversationHandler.END


async def show_remove_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    channels = list_forced_channels()
    if not channels:
        await query.edit_message_text("هیچ کانالی برای حذف وجود نداره.")
        return
    rows = [[InlineKeyboardButton(f"{i}. {ch['title']}", callback_data=f"admin:remove_channel:{ch['id']}")]
            for i, ch in enumerate(channels, start=1)]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin:channels")])
    await query.edit_message_text("🗑 حذف کانال\n\nکدوم کانال رو حذف کنم؟", reply_markup=InlineKeyboardMarkup(rows))


async def do_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return
    channel_db_id = int(query.data.split(":", 2)[2])
    remove_forced_channel(channel_db_id)
    await query.answer("✅ حذف شد.")
    await show_channels(update, context)


def build_add_channel_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_add_channel, pattern=r"^admin:add_channel$")],
        states={AWAITING_ADD_LINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_channel)]},
        fallbacks=[CallbackQueryHandler(ask_add_channel, pattern=r"^admin:add_channel$")],
        name="admin_add_channel_conversation",
        persistent=False,
    )


channel_handlers = [
    CallbackQueryHandler(show_channels, pattern=r"^admin:channels$"),
    CallbackQueryHandler(show_remove_menu, pattern=r"^admin:remove_channel_menu$"),
    CallbackQueryHandler(do_remove_channel, pattern=r"^admin:remove_channel:"),
]
