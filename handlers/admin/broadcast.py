"""
📢 پیام همگانی.
"""
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import TelegramError

from config import ADMIN_IDS
from database.users import get_all_registered_user_ids

AWAITING_TEXT, AWAITING_CONFIRM = range(2)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END

    total = len(get_all_registered_user_ids())
    await query.edit_message_text(
        f"📢 پیام همگانی\n━━━━━━━━━━━━━━━\n👥 ارسال به: همه کاربران ({total} نفر)\n\nمتن پیامت رو بنویس:"
    )
    return AWAITING_TEXT


async def receive_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""
    context.user_data["broadcast_text"] = text
    total = len(get_all_registered_user_ids())

    preview = f"📢 پیش‌نمایش پیام\n━━━━━━━━━━━━━━━\n{text}\n\n👥 ارسال به: {total} نفر"
    rows = [
        [InlineKeyboardButton("📤 ارسال", callback_data="bc:send")],
        [InlineKeyboardButton("✏️ ویرایش", callback_data="bc:edit")],
        [InlineKeyboardButton("❌ لغو", callback_data="bc:cancel")],
    ]
    await update.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(rows))
    return AWAITING_CONFIRM


async def edit_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("متن جدید پیامت رو بنویس:")
    return AWAITING_TEXT


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("broadcast_text", None)
    await query.edit_message_text("❌ پیام همگانی لغو شد.")
    return ConversationHandler.END


async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = context.user_data.pop("broadcast_text", None)
    if not text:
        await query.edit_message_text("❌ متنی برای ارسال پیدا نشد.")
        return ConversationHandler.END

    user_ids = get_all_registered_user_ids()
    success, failed = 0, 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            success += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)  # جلوگیری از برخورد به محدودیت نرخ تلگرام

    await query.edit_message_text(
        f"✅ پیام همگانی ارسال شد!\n\n📤 موفق: {success}\n❌ ناموفق: {failed}"
    )
    return ConversationHandler.END


def build_broadcast_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern=r"^admin:broadcast$")],
        states={
            AWAITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_text)],
            AWAITING_CONFIRM: [
                CallbackQueryHandler(send_broadcast, pattern=r"^bc:send$"),
                CallbackQueryHandler(edit_broadcast, pattern=r"^bc:edit$"),
                CallbackQueryHandler(cancel_broadcast, pattern=r"^bc:cancel$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(start_broadcast, pattern=r"^admin:broadcast$")],
        name="admin_broadcast_conversation",
        persistent=False,
    )
