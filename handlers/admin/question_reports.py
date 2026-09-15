"""
⚠️ گزارش‌های اشکال تست (پنل ادمین).
اینجا ادمین می‌تونه سوالات گزارش‌شده رو ببینه (عکس واقعی سوال) و مستقیماً اصلاح کنه.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import ADMIN_IDS, QUESTION_REPORT_TYPES
from database import content as C
from database import reports as R
from database.content import VALID_QUESTION_FIELDS

LIST_PAGE, VIEW_DETAIL, AWAITING_NEW_VALUE = range(3)
PAGE_SIZE = 10

FIELD_PROMPTS = {
    "question_image_file_id": "📷 عکس جدید سوال (همراه با گزینه‌ها) رو بفرست:",
    "correct_option": "شماره گزینه‌ی صحیح جدید رو بنویس (۱ تا ۴):",
    "explanation_image_file_id": "📷 عکس جدید توضیح/پاسخ‌نامه رو بفرست:",
}
IMAGE_FIELDS = {"question_image_file_id", "explanation_image_file_id"}


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _extract_image_file_id(message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id  # بزرگ‌ترین سایز
    if message.document:
        return message.document.file_id
    return None


async def _reject_non_admin(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔ این بخش فقط برای ادمینه.")


def _format_list_text(groups: list[dict], page: int, total: int) -> str:
    lines = ["⚠️ گزارش‌های اشکال تست", "━━━━━━━━━━━━━━━", f"🔴 در انتظار بررسی: {total}", ""]
    if not groups:
        lines.append("گزارش در انتظاری وجود نداره ✅")
    for i, g in enumerate(groups, start=1):
        q = g["question"]
        idx = (page - 1) * PAGE_SIZE + i
        lines.append(
            f"{idx}. {q['grade']} {q['subject']} — {q['book_name']} — "
            f"{q['chapter_name']} — تست {q['number']}"
        )
        lines.append(f"   ⚠️ تعداد گزارش: {g['report_count']}")
    return "\n".join(lines)


async def entry_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update.effective_user.id):
        await _reject_non_admin(update)
        return ConversationHandler.END
    return await _show_list_page(update, context, page=1)


async def paginate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    page = int(query.data.split(":", 2)[2])
    return await _show_list_page(update, context, page)


async def _show_list_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> int:
    total = R.count_pending_report_groups()
    groups = R.list_pending_report_groups(page=page, page_size=PAGE_SIZE)
    total_pages = max(1, -(-total // PAGE_SIZE))
    page = max(1, min(page, total_pages))

    text = _format_list_text(groups, page, total)
    rows = [
        [InlineKeyboardButton(
            f"سوال {g['question']['number']} — {g['question']['subject']}",
            callback_data=f"qrep:view:{g['question_id']}")]
        for g in groups
    ]
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"qrep:page:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"qrep:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin:tests")])

    markup = InlineKeyboardMarkup(rows)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return LIST_PAGE


def _detail_action_rows() -> list[list[InlineKeyboardButton]]:
    return [
        [InlineKeyboardButton("✏️ عکس سوال", callback_data="qrep:field:question_image_file_id", style="primary")],
        [InlineKeyboardButton("✏️ پاسخ صحیح", callback_data="qrep:field:correct_option", style="primary")],
        [InlineKeyboardButton("✏️ عکس توضیح/پاسخ", callback_data="qrep:field:explanation_image_file_id", style="primary")],
        [InlineKeyboardButton("✅ گزارش نادرسته (بدون تغییر)", callback_data="qrep:reject", style="success")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="qrep:page:1")],
    ]


def _format_reports_text(question, pending_reports) -> str:
    lines = [
        "📝 اصلاح تست", "━━━━━━━━━━━━━━━",
        f"📚 {question['grade']} {question['subject']} — {question['book_name']} — "
        f"{question['chapter_name']} — تست {question['number']}",
        f"✅ پاسخ فعلی: گزینه {question['correct_option']}",
        "━━━━━━━━━━━━━━━",
    ]
    for r in pending_reports:
        type_label = QUESTION_REPORT_TYPES.get(r["report_type"], r["report_type"])
        lines.append(f"⚠️ گزارش کاربر ({r['user_id']}): «{type_label}»")
        if r["description"]:
            lines.append(f"💬 توضیح: {r['description']}")
    return "\n".join(lines)


async def _send_detail(target_message, context: ContextTypes.DEFAULT_TYPE, question_id: int) -> None:
    """
    عکس سوال (و عکس توضیح، اگه داشته باشه) رو می‌فرسته، بعد یه پیام متنی
    با اطلاعات گزارش‌ها + دکمه‌های اصلاح.
    """
    question = C.get_question_full_path(question_id)
    pending_reports = R.get_pending_reports_for_question(question_id)

    await target_message.reply_photo(
        photo=question["question_image_file_id"],
        caption=f"❓ تست {question['number']} — {question['subject']} {question['grade']}",
    )
    if question["explanation_image_file_id"]:
        await target_message.reply_photo(
            photo=question["explanation_image_file_id"], caption="📝 توضیح/پاسخ‌نامه‌ی فعلی"
        )

    text = _format_reports_text(question, pending_reports)
    await target_message.reply_text(text, reply_markup=InlineKeyboardMarkup(_detail_action_rows()))


async def view_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_id = int(query.data.split(":", 2)[2])
    context.user_data["admin_report_question_id"] = question_id

    question = C.get_question_full_path(question_id)
    if question is None:
        await query.edit_message_text("این سوال دیگه وجود نداره.")
        return await _show_list_page(update, context, page=1)

    await _send_detail(query.message, context, question_id)
    return VIEW_DETAIL


async def ask_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split(":", 2)[2]
    if field not in VALID_QUESTION_FIELDS:
        await query.answer("فیلد نامعتبره.", show_alert=True)
        return VIEW_DETAIL
    context.user_data["admin_edit_field"] = field
    # این پیام (لیست دکمه‌های اصلاح) متنیه، پس edit_message_text درسته
    await query.edit_message_text(FIELD_PROMPTS[field])
    return AWAITING_NEW_VALUE


async def receive_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فقط برای فیلد متنی «پاسخ صحیح» — بقیه‌ی فیلدها عکس هستن (receive_new_image)."""
    field = context.user_data.get("admin_edit_field")
    if field != "correct_option":
        await update.message.reply_text("❌ برای این فیلد باید عکس بفرستی، نه متن.")
        return AWAITING_NEW_VALUE

    question_id = context.user_data.get("admin_report_question_id")
    admin_id = update.effective_user.id
    raw_value = (update.message.text or "").strip()

    if raw_value not in {"1", "2", "3", "4"}:
        await update.message.reply_text("❌ باید عددی بین ۱ تا ۴ باشه. دوباره بنویس:")
        return AWAITING_NEW_VALUE

    return await _apply_edit(update, context, question_id, admin_id, field, int(raw_value))


async def receive_new_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("admin_edit_field")
    if field not in IMAGE_FIELDS:
        await update.message.reply_text("❌ برای این فیلد باید متن بفرستی، نه عکس.")
        return AWAITING_NEW_VALUE

    file_id = _extract_image_file_id(update.message)
    if file_id is None:
        await update.message.reply_text("❌ این عکس/فایل نیست. دوباره بفرست:")
        return AWAITING_NEW_VALUE

    question_id = context.user_data.get("admin_report_question_id")
    admin_id = update.effective_user.id
    return await _apply_edit(update, context, question_id, admin_id, field, file_id)


async def _apply_edit(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       question_id: int, admin_id: int, field: str, new_value) -> int:
    try:
        R.edit_question_with_log(question_id, admin_id, field, new_value)
    except ValueError as e:
        await update.message.reply_text(f"❌ خطا: {e}")
        return AWAITING_NEW_VALUE

    await update.message.reply_text("✅ تست با موفقیت اصلاح شد.")

    # اگه گزارش pending‌ای برای این سوال هست، بستشون کن (کاربر واقعاً درست گفته بود)
    pending = R.get_pending_reports_for_question(question_id)
    reporter_ids = list({r["user_id"] for r in pending})
    if pending:
        R.resolve_reports_for_question(question_id, admin_id, accepted=True)

    rows = []
    if reporter_ids:
        rows.append([InlineKeyboardButton(
            "📤 اطلاع‌رسانی به گزارش‌دهنده(ها)", callback_data=f"qrep:notify:{question_id}", style="success"
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت به لیست گزارش‌ها", callback_data="qrep:page:1")])
    await update.message.reply_text("ادامه:", reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END


async def reject_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_id = context.user_data.get("admin_report_question_id")
    admin_id = update.effective_user.id
    R.resolve_reports_for_question(question_id, admin_id, accepted=False, admin_note="بررسی شد، مشکلی نبود")
    await query.edit_message_text("✅ گزارش‌ها بسته شدن (بدون تغییر در سوال).")
    return await _show_list_page(update, context, page=1)


async def notify_reporters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    question_id = int(query.data.split(":", 2)[2])
    question = C.get_question_full_path(question_id)
    reporter_ids = R.get_reporters_for_question(question_id)

    text = (
        "📢 نتیجه گزارش تو\n\n"
        f"📚 {question['subject']} — {question['chapter_name']} — تست {question['number']}\n"
        "✅ این تست اصلاح شد. ممنون بابت گزارشت 🌹"
    )
    sent = 0
    for uid in reporter_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            pass

    await query.edit_message_text(f"✅ به {sent} نفر اطلاع داده شد.")
    return ConversationHandler.END


def build_question_reports_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(entry_reports, pattern=r"^admin:question_reports$"),
            CallbackQueryHandler(paginate, pattern=r"^qrep:page:"),
            CallbackQueryHandler(notify_reporters, pattern=r"^qrep:notify:"),
        ],
        states={
            LIST_PAGE: [
                CallbackQueryHandler(paginate, pattern=r"^qrep:page:"),
                CallbackQueryHandler(view_question, pattern=r"^qrep:view:"),
            ],
            VIEW_DETAIL: [
                CallbackQueryHandler(ask_new_value, pattern=r"^qrep:field:"),
                CallbackQueryHandler(reject_report, pattern=r"^qrep:reject$"),
                CallbackQueryHandler(paginate, pattern=r"^qrep:page:"),
            ],
            AWAITING_NEW_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_value),
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_new_image),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(entry_reports, pattern=r"^admin:question_reports$"),
            CallbackQueryHandler(paginate, pattern=r"^qrep:page:"),
            CallbackQueryHandler(notify_reporters, pattern=r"^qrep:notify:"),
        ],
        name="admin_question_reports_conversation",
        persistent=False,
    )
