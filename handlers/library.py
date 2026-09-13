"""
بخش ۶: کتابخانه (دانلود کتاب‌های درسی).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from database import content as C
from database.misc import create_book_request
from utils.keyboards import grades_keyboard, majors_keyboard, with_back

SEL_GRADE, SEL_MAJOR, SEL_SUBJECT = range(3)
PREFIX = "lib"


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("library", {})


async def entry_library(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["library"] = {}
    text = (
        "📚 کتابخونه شخصی تو\n━━━━━━━━━━━━━━━\n"
        "سلام 👋\n\nاینجا همه‌ی کتاب‌های درسیت آماده‌ست.\n"
        "هر وقت خواستی، فقط انتخاب کن و دانلود کن."
    )
    rows = [
        [InlineKeyboardButton("🚀 شروع", callback_data=f"{PREFIX}:go")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
    return SEL_GRADE


async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.main_menu import main_menu_callback
    await main_menu_callback(update, context)
    return ConversationHandler.END


async def _render_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.edit_message_text(
        "📚 کتاب‌ها بر اساس پایه:", reply_markup=grades_keyboard(PREFIX)
    )
    return SEL_GRADE


async def go_to_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await _render_grades(update, context)


async def back_to_intro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دکمه‌ی «بازگشت» توی صفحه‌ی انتخاب پایه؛ چون این اولین قدمه، برمی‌گرده
    به صفحه‌ی معرفی کتابخونه (نه اینکه دوباره همون صفحه رو نشون بده -
    که تلگرام edit با متن/دکمه‌ی یکسان رو خطا می‌ده)."""
    return await entry_library(update, context)


async def _show_majors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    await update.callback_query.edit_message_text(
        f"📚 کتاب‌های {ud['grade']}\n\nرشته‌ت رو انتخاب کن:",
        reply_markup=majors_keyboard(PREFIX),
    )
    return SEL_MAJOR


async def select_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    grade = query.data.split(":", 2)[2]
    _ud(context)["grade"] = grade
    return await _show_majors(update, context)


async def _show_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    ud = _ud(context)
    from config import SUBJECTS_BY_MAJOR
    subjects = SUBJECTS_BY_MAJOR.get(ud["major"], [])
    rows = [[InlineKeyboardButton(s, callback_data=f"{PREFIX}:subj:{s}")] for s in subjects]
    await query.edit_message_text(
        f"📚 کتاب‌های {ud['grade']} {ud['major']}:", reply_markup=with_back(rows, callback_data=f"{PREFIX}:back")
    )
    return SEL_SUBJECT


async def select_major(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    major = query.data.split(":", 2)[2]
    _ud(context)["major"] = major
    return await _show_subjects(update, context)


async def back_to_majors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await _show_majors(update, context)


async def back_to_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _show_subjects(update, context)


async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    subject = query.data.split(":", 2)[2]
    ud = _ud(context)
    book = C.get_library_book(ud["grade"], ud["major"], subject)

    ud["subject"] = subject

    if book and book["available"] and book["file_id"]:
        await query.message.reply_document(
            document=book["file_id"],
            caption=f"📕 {subject} {ud['grade']}\n✅ فایل آماده دانلوده.",
        )
        rows = [
            [InlineKeyboardButton("🔙 بازگشت به لیست کتاب‌ها", callback_data=f"{PREFIX}:back_subj")],
            [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
        ]
        await query.edit_message_text(f"📕 {subject} {ud['grade']}\n━━━━━━━━━━━━━━━\n✅ فایل آماده دانلوده.",
                                       reply_markup=InlineKeyboardMarkup(rows))
        return SEL_SUBJECT

    rows = [
        [InlineKeyboardButton("📢 گزارش به مدیر", callback_data=f"{PREFIX}:report")],
        [InlineKeyboardButton("🔙 بازگشت به لیست کتاب‌ها", callback_data=f"{PREFIX}:back_subj")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
    ]
    await query.edit_message_text(
        f"📕 {subject} {ud['grade']}\n━━━━━━━━━━━━━━━\n"
        "❌ متأسفانه فایل این کتاب فعلاً موجود نیست.\n\n"
        "می‌تونی به مدیر گزارش بدی تا اضافه کنه 🌹",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return SEL_SUBJECT


async def report_missing_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ud = _ud(context)
    create_book_request(update.effective_user.id, ud["grade"], ud["major"], ud["subject"])
    await query.edit_message_text(
        "✅ گزارش ارسال شد!\n\nمدیر به‌زودی کتاب رو بررسی می‌کنه.\nنتیجه رو بهت اطلاع می‌دیم 🌹"
    )
    return ConversationHandler.END


def build_library_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_library, pattern=r"^menu:library$")],
        states={
            SEL_GRADE: [
                CallbackQueryHandler(go_to_grades, pattern=f"^{PREFIX}:go$"),
                CallbackQueryHandler(select_grade, pattern=f"^{PREFIX}:grade:"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(back_to_intro, pattern=f"^{PREFIX}:back$"),
            ],
            SEL_MAJOR: [
                CallbackQueryHandler(select_major, pattern=f"^{PREFIX}:major:"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(go_to_grades, pattern=f"^{PREFIX}:back$"),
            ],
            SEL_SUBJECT: [
                CallbackQueryHandler(select_subject, pattern=f"^{PREFIX}:subj:"),
                CallbackQueryHandler(report_missing_book, pattern=f"^{PREFIX}:report$"),
                CallbackQueryHandler(back_to_subjects, pattern=f"^{PREFIX}:back_subj$"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(back_to_majors, pattern=f"^{PREFIX}:back$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(go_to_grades, pattern=f"^{PREFIX}:back$"),
            # اگه این مکالمه قبلاً یه‌جایی گیر کرده باشه (state قدیمی مونده)،
            # کلیک دوباره روی «📚 کتابخانه» باید از نو بازش کنه، نه بی‌صدا هیچی نشه.
            CallbackQueryHandler(entry_library, pattern=r"^menu:library$"),
        ],
        name="library_conversation",
        persistent=False,
    )
