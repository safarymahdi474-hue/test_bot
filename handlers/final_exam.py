"""
📝 امتحان نهایی — مرور و دانلود فایل‌های امتحان نهایی که ادمین آپلود کرده.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from database import final_exams as FE
from utils.keyboards import grades_keyboard, majors_keyboard, subjects_keyboard, with_back

SEL_GRADE, SEL_MAJOR, SEL_SUBJECT = range(3)
PREFIX = "fexam"


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("final_exam", {})


async def entry_final_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["final_exam"] = {}
    await query.edit_message_text(
        "📝 امتحان نهایی\n━━━━━━━━━━━━━━━\nپایه‌ت رو انتخاب کن:",
        reply_markup=grades_keyboard(PREFIX),
    )
    return SEL_GRADE


async def select_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    grade = query.data.split(":", 2)[2]
    _ud(context)["grade"] = grade
    await query.edit_message_text(
        "رشته‌ت رو انتخاب کن:", reply_markup=majors_keyboard(PREFIX)
    )
    return SEL_MAJOR


async def select_major(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    major = query.data.split(":", 2)[2]
    ud = _ud(context)
    ud["major"] = major
    await query.edit_message_text(
        f"📝 امتحان نهایی {ud['grade']} {major}:\n\nدرست رو انتخاب کن:",
        reply_markup=subjects_keyboard(PREFIX, major),
    )
    return SEL_SUBJECT


async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    subject = query.data.split(":", 2)[2]
    ud = _ud(context)
    ud["subject"] = subject

    exams = FE.list_final_exams(ud["grade"], ud["major"], subject)
    if not exams:
        await query.edit_message_text(
            f"📝 {subject} {ud['grade']}\n━━━━━━━━━━━━━━━\n"
            "❌ هنوز امتحان نهایی‌ای برای این درس آپلود نشده.",
            reply_markup=subjects_keyboard(PREFIX, ud["major"]),
        )
        return SEL_SUBJECT

    rows = [[InlineKeyboardButton(f"📄 {e['title']}", callback_data=f"{PREFIX}:dl:{e['id']}")]
            for e in exams]
    await query.edit_message_text(
        f"📝 امتحان‌های نهایی {subject} {ud['grade']}:", reply_markup=with_back(rows, callback_data=f"{PREFIX}:back")
    )
    return SEL_SUBJECT


async def download_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    exam_id = int(query.data.split(":", 2)[2])
    exam = FE.get_final_exam(exam_id)
    if exam is None:
        await query.answer("❌ این فایل دیگه در دسترس نیست.", show_alert=True)
        return SEL_SUBJECT

    await query.message.reply_document(
        document=exam["file_id"],
        caption=f"📝 {exam['subject']} {exam['grade']} — {exam['title']}",
    )
    return SEL_SUBJECT


async def go_back_to_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 امتحان نهایی\n━━━━━━━━━━━━━━━\nپایه‌ت رو انتخاب کن:",
        reply_markup=grades_keyboard(PREFIX),
    )
    return SEL_GRADE


async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.main_menu import main_menu_callback
    await main_menu_callback(update, context)
    return ConversationHandler.END


def build_final_exam_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_final_exam, pattern=r"^menu:final_exam$")],
        states={
            SEL_GRADE: [
                CallbackQueryHandler(select_grade, pattern=f"^{PREFIX}:grade:"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(exit_to_main_menu, pattern=f"^{PREFIX}:back$"),
            ],
            SEL_MAJOR: [
                CallbackQueryHandler(select_major, pattern=f"^{PREFIX}:major:"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(go_back_to_grades, pattern=f"^{PREFIX}:back$"),
            ],
            SEL_SUBJECT: [
                CallbackQueryHandler(select_subject, pattern=f"^{PREFIX}:subject:"),
                CallbackQueryHandler(download_exam, pattern=f"^{PREFIX}:dl:"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(go_back_to_grades, pattern=f"^{PREFIX}:back$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(go_back_to_grades, pattern=f"^{PREFIX}:back$"),
            CallbackQueryHandler(entry_final_exam, pattern=r"^menu:final_exam$"),
        ],
        name="final_exam_conversation",
        persistent=False,
    )
