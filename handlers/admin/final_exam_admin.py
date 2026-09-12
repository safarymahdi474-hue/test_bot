"""
📝 مدیریت امتحان نهایی (سمت ادمین) — افزودن فایل با انتخاب پایه/رشته/درس + عنوان.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import ADMIN_IDS
from database import final_exams as FE
from utils.keyboards import grades_keyboard, majors_keyboard, subjects_keyboard

SEL_GRADE, SEL_MAJOR, SEL_SUBJECT, AWAITING_TITLE, AWAITING_FILE = range(5)
PREFIX = "fexadd"


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("fexadd", {})


async def entry_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    total = FE.count_final_exams()
    summary = FE.list_final_exam_subjects_summary()
    lines = ["📝 مدیریت امتحان نهایی", "━━━━━━━━━━━━━━━", f"📊 تعداد فایل‌ها: {total}", ""]
    if summary:
        lines.append("📚 دروسی که فایل دارن:")
        for s in summary[:15]:
            lines.append(f"• {s['subject']} {s['grade']} ({s['major']}) — {s['exam_count']} فایل")
    else:
        lines.append("هنوز فایلی آپلود نشده.")

    rows = [
        [InlineKeyboardButton("➕ افزودن امتحان نهایی", callback_data="admin:add_fexam")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")],
    ]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END
    context.user_data["fexadd"] = {}
    await query.edit_message_text(
        "➕ افزودن امتحان نهایی\n━━━━━━━━━━━━━━━\nپایه رو انتخاب کن:",
        reply_markup=grades_keyboard(PREFIX, with_back_button=False),
    )
    return SEL_GRADE


async def select_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    grade = query.data.split(":", 2)[2]
    _ud(context)["grade"] = grade
    await query.edit_message_text(
        "رشته رو انتخاب کن:", reply_markup=majors_keyboard(PREFIX, with_back_button=False)
    )
    return SEL_MAJOR


async def select_major(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    major = query.data.split(":", 2)[2]
    ud = _ud(context)
    ud["major"] = major
    await query.edit_message_text(
        "درس رو انتخاب کن:", reply_markup=subjects_keyboard(PREFIX, major)
    )
    return SEL_SUBJECT


async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    subject = query.data.split(":", 2)[2]
    ud = _ud(context)
    ud["subject"] = subject
    await query.edit_message_text(
        f"📝 {subject} {ud['grade']} ({ud['major']})\n\n"
        "عنوان این امتحان رو بنویس:\n(مثال: نوبت دوم - خرداد ۱۴۰۲)"
    )
    return AWAITING_TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text("❌ عنوان نمی‌تونه خالی باشه. دوباره بنویس:")
        return AWAITING_TITLE
    _ud(context)["title"] = title
    await update.message.reply_text("حالا فایل امتحان (PDF یا …) رو بفرست:")
    return AWAITING_FILE


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    if doc is None:
        await update.message.reply_text("❌ این فایل نیست. یه فایل بفرست:")
        return AWAITING_FILE

    ud = _ud(context)
    FE.add_final_exam(
        ud["grade"], ud["major"], ud["subject"], ud["title"],
        doc.file_id, uploaded_by=update.effective_user.id,
    )
    await update.message.reply_text(
        f"✅ امتحان نهایی اضافه شد!\n({ud['subject']} {ud['grade']} — {ud['title']})"
    )
    context.user_data.pop("fexadd", None)
    return ConversationHandler.END


def build_add_final_exam_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add, pattern=r"^admin:add_fexam$")],
        states={
            SEL_GRADE: [CallbackQueryHandler(select_grade, pattern=f"^{PREFIX}:grade:")],
            SEL_MAJOR: [CallbackQueryHandler(select_major, pattern=f"^{PREFIX}:major:")],
            SEL_SUBJECT: [CallbackQueryHandler(select_subject, pattern=f"^{PREFIX}:subject:")],
            AWAITING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            AWAITING_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
        },
        fallbacks=[],
        name="admin_add_final_exam_conversation",
        persistent=False,
    )


final_exam_admin_handlers = [
    CallbackQueryHandler(entry_stats, pattern=r"^admin:final_exams$"),
]
