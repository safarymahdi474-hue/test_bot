"""
📢 گزارش‌ها (کتاب ناموجود) + 📩 انتقادات — سمت ادمین.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import TelegramError

from config import ADMIN_IDS
from database import misc as M
from database import users as U

(AWAITING_ACTION, AWAITING_REJECT_REASON, AWAITING_CUSTOM_REPLY, AWAITING_FEEDBACK_REPLY) = range(4)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== گزارش‌های کتاب ناموجود ====================

async def show_book_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    pending = M.list_pending_book_requests(page=1, page_size=10)
    total = M.count_pending_book_requests()
    lines = ["📢 گزارش‌ها", "━━━━━━━━━━━━━━━", f"🔴 در انتظار پاسخ: {total}", ""]
    for i, r in enumerate(pending, start=1):
        lines.append(f"{i}. {r['full_name']} → {r['subject']} {r['grade']}")

    rows = [[InlineKeyboardButton(f"{r['full_name']} — {r['subject']}", callback_data=f"admin:book_req:{r['id']}")]
            for r in pending]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def view_book_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    request_id = int(query.data.split(":", 2)[2])
    req = M.get_book_request(request_id)
    if req is None:
        await query.edit_message_text("این گزارش پیدا نشد.")
        return ConversationHandler.END

    context.user_data["admin_book_request_id"] = request_id
    text = (
        f"📢 گزارش کتاب ناموجود\n━━━━━━━━━━━━━━━\n"
        f"📚 درخواست کتاب:\n{req['grade']} — {req['major']} — {req['subject']}\n\n"
        f"📅 تاریخ: {req['created_at'][:10]}"
    )
    rows = [
        [InlineKeyboardButton("✅ اضافه شد", callback_data="admin:book_req_action:added", style="success")],
        [InlineKeyboardButton("❌ وارد نمی‌شه", callback_data="admin:book_req_action:rejected", style="danger")],
        [InlineKeyboardButton("⏳ در دسترس نیست", callback_data="admin:book_req_action:unavailable", style="primary")],
        [InlineKeyboardButton("💬 پاسخ دلخواه", callback_data="admin:book_req_action:custom", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:book_requests")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
    return AWAITING_ACTION


async def handle_book_req_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 2)[2]
    request_id = context.user_data.get("admin_book_request_id")

    if action == "rejected":
        await query.edit_message_text("❌ وارد نمی‌شه.\n\nدلیلش رو بنویس تا کاربر بدونه:\n(اگه نمی‌خوای، خالی بفرست)")
        return AWAITING_REJECT_REASON

    if action == "custom":
        await query.edit_message_text("💬 پاسخ دلخواهت رو بنویس:")
        return AWAITING_CUSTOM_REPLY

    if action == "added":
        M.resolve_book_request(request_id, "added", None)
        req = M.get_book_request(request_id)
        text = f"📕 {req['subject']}\n━━━━━━━━━━━━━━━\n✅ کتابت اضافه شد!\n\nبرو از کتابخونه دانلودش کن 🌹"
        await _notify_user(context, req["user_id"], text)
        await query.edit_message_text("✅ به کاربر اطلاع داده شد.")
        return ConversationHandler.END

    if action == "unavailable":
        M.resolve_book_request(request_id, "unavailable", None)
        req = M.get_book_request(request_id)
        text = (f"📕 {req['subject']}\n━━━━━━━━━━━━━━━\n⏳ این کتاب فعلاً در دسترس نیست.\n\n"
                "ما تلاشمون رو می‌کنیم که به‌زودی اضافه‌ش کنیم 🌹")
        await _notify_user(context, req["user_id"], text)
        await query.edit_message_text("✅ به کاربر اطلاع داده شد.")
        return ConversationHandler.END

    return ConversationHandler.END


async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reason = (update.message.text or "").strip()
    request_id = context.user_data.get("admin_book_request_id")
    M.resolve_book_request(request_id, "rejected", reason or None)
    req = M.get_book_request(request_id)

    text = f"📕 {req['subject']}\n━━━━━━━━━━━━━━━\n❌ متأسفانه این کتاب وارد نمی‌شه.\n"
    if reason:
        text += f"\nدلیل: {reason}\n"
    text += "\nممنون که گزارش دادی 🌹"
    await _notify_user(context, req["user_id"], text)
    await update.message.reply_text("✅ به کاربر اطلاع داده شد.")
    return ConversationHandler.END


async def receive_custom_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply = (update.message.text or "").strip()
    request_id = context.user_data.get("admin_book_request_id")
    M.resolve_book_request(request_id, "custom_replied", reply)
    req = M.get_book_request(request_id)

    text = f"📕 {req['subject']}\n━━━━━━━━━━━━━━━\n💬 {reply}"
    await _notify_user(context, req["user_id"], text)
    await update.message.reply_text("✅ به کاربر اطلاع داده شد.")
    return ConversationHandler.END


async def _notify_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> None:
    try:
        await context.bot.send_message(chat_id=user_id, text=f"📢 جواب مدیر\n\n{text}")
    except TelegramError:
        pass


# ==================== انتقادات ====================

async def show_feedback_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    pending = M.list_pending_feedback(page=1, page_size=10)
    total = M.count_pending_feedback()
    lines = ["📩 انتقادات و پیشنهادات", "━━━━━━━━━━━━━━━", f"📬 در انتظار پاسخ: {total}", ""]
    for i, f in enumerate(pending, start=1):
        lines.append(f"{i}. {f['full_name']} — {f['message'][:30]}")

    rows = [[InlineKeyboardButton(f"{f['full_name']}", callback_data=f"admin:fb_view:{f['id']}")]
            for f in pending]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def view_feedback_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    feedback_id = int(query.data.split(":", 2)[2])
    fb = M.get_feedback(feedback_id)
    if fb is None:
        await query.edit_message_text("این پیام پیدا نشد.")
        return ConversationHandler.END

    user = U.get_user(fb["user_id"])
    context.user_data["admin_feedback_id"] = feedback_id
    text = (
        f"💬 پاسخ به انتقاد/پیشنهاد\n━━━━━━━━━━━━━━━\n"
        f"👤 کاربر: {user['full_name'] if user else fb['user_id']}\n"
        f"📝 پیام کاربر:\n{fb['message']}\n\n━━━━━━━━━━━━━━━\nپاسخ خودت رو بنویس:"
    )
    await query.edit_message_text(text)
    return AWAITING_FEEDBACK_REPLY


async def receive_feedback_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply = (update.message.text or "").strip()
    feedback_id = context.user_data.get("admin_feedback_id")
    if not reply:
        await update.message.reply_text("متن پاسخ نمی‌تونه خالی باشه:")
        return AWAITING_FEEDBACK_REPLY

    M.respond_feedback(feedback_id, reply)
    fb = M.get_feedback(feedback_id)
    user = U.get_user(fb["user_id"])
    first_name = (user["full_name"].split()[0] if user and user["full_name"] else "کاربر")

    text = (
        f"📩 پاسخ ادمین\n\n👤 {first_name} عزیز،\n\n"
        f"💬 پاسخ ادمین:\n{reply}\n\n━━━━━━━━━━━━━━━\n"
        "📬 برای دیدن همه پیام‌هات:\nاز بخش «👤 پروفایل من» → «📩 انتقاد و پیشنهاد»"
    )
    try:
        await context.bot.send_message(chat_id=fb["user_id"], text=text)
    except TelegramError:
        pass

    await update.message.reply_text("✅ پاسخ ارسال شد.")
    return ConversationHandler.END


def build_book_request_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(view_book_request, pattern=r"^admin:book_req:")],
        states={
            AWAITING_ACTION: [CallbackQueryHandler(handle_book_req_action, pattern=r"^admin:book_req_action:")],
            AWAITING_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reject_reason)],
            AWAITING_CUSTOM_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_reply)],
        },
        fallbacks=[CallbackQueryHandler(view_book_request, pattern=r"^admin:book_req:")],
        name="admin_book_request_conversation",
        persistent=False,
    )


def build_feedback_reply_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(view_feedback_item, pattern=r"^admin:fb_view:")],
        states={
            AWAITING_FEEDBACK_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback_reply)],
        },
        fallbacks=[CallbackQueryHandler(view_feedback_item, pattern=r"^admin:fb_view:")],
        name="admin_feedback_reply_conversation",
        persistent=False,
    )


reports_feedback_entry_handlers = [
    CallbackQueryHandler(show_book_requests, pattern=r"^admin:book_requests$"),
    CallbackQueryHandler(show_feedback_queue, pattern=r"^admin:feedback$"),
]
