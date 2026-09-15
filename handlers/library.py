"""
بخش ۶: کتابخانه (دانلود کتاب‌های درسی).
هر درس می‌تونه چند ناشر داشته باشه (مثل تمرین و آزمون)، پس بعد از انتخاب
درس، یه لیست از ناشرها نشون داده می‌شه، نه مستقیم یه فایل.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from database import content as C
from database.misc import create_book_request
from utils.keyboards import grades_keyboard, majors_keyboard, with_back

SEL_GRADE, SEL_MAJOR, SEL_SUBJECT, SEL_PUBLISHER = range(4)
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
        [InlineKeyboardButton("🚀 شروع", callback_data=f"{PREFIX}:go", style="success")],
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
    ud = _ud(context)
    from config import get_subjects
    subjects = get_subjects(ud["grade"], ud["major"])
    rows = [[InlineKeyboardButton(s, callback_data=f"{PREFIX}:subj:{s}")] for s in subjects]
    await update.callback_query.edit_message_text(
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


async def _show_publishers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    books = C.list_library_books_for_subject(ud["grade"], ud["major"], ud["subject"])

    if not books:
        rows = [
            [InlineKeyboardButton("📢 گزارش به مدیر", callback_data=f"{PREFIX}:report", style="primary")],
            [InlineKeyboardButton("🔙 بازگشت به لیست درس‌ها", callback_data=f"{PREFIX}:back_subj")],
            [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
        ]
        await update.callback_query.edit_message_text(
            f"📕 {ud['subject']} {ud['grade']}\n━━━━━━━━━━━━━━━\n"
            "❌ متأسفانه فایلی برای این درس ثبت نشده.\n\n"
            "می‌تونی به مدیر گزارش بدی تا اضافه کنه 🌹",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return SEL_SUBJECT

    rows = [[InlineKeyboardButton(f"📕 {b['publisher']}", callback_data=f"{PREFIX}:pub:{b['id']}")]
            for b in books]
    rows.append([InlineKeyboardButton("📢 ناشر دیگه‌ای می‌خوام", callback_data=f"{PREFIX}:report", style="primary")])
    await update.callback_query.edit_message_text(
        f"📚 {ud['subject']} {ud['grade']} — کدوم ناشر رو می‌خوای؟",
        reply_markup=with_back(rows, callback_data=f"{PREFIX}:back"),
    )
    return SEL_PUBLISHER


async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    subject = query.data.split(":", 2)[2]
    _ud(context)["subject"] = subject
    return await _show_publishers(update, context)


async def back_to_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _show_subjects(update, context)


async def back_to_publishers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await _show_publishers(update, context)


async def select_publisher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    book_id = int(query.data.split(":", 2)[2])
    ud = _ud(context)

    book = C.get_library_book(book_id)
    if book is None or not book["available"] or not book["file_id"]:
        await query.answer("❌ این فایل دیگه در دسترس نیست.", show_alert=True)
        return await _show_publishers(update, context)

    await query.message.reply_document(
        document=book["file_id"],
        caption=f"📕 {book['subject']} {book['grade']} — {book['publisher']}\n✅ فایل آماده دانلوده.",
    )
    rows = [
        [InlineKeyboardButton("🔙 بازگشت به لیست ناشرها", callback_data=f"{PREFIX}:back_pub")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
    ]
    await query.edit_message_text(
        f"📕 {book['subject']} {book['grade']} — {book['publisher']}\n"
        "━━━━━━━━━━━━━━━\n✅ فایل آماده دانلوده.",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return SEL_PUBLISHER


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
            SEL_PUBLISHER: [
                CallbackQueryHandler(select_publisher, pattern=f"^{PREFIX}:pub:"),
                CallbackQueryHandler(report_missing_book, pattern=f"^{PREFIX}:report$"),
                CallbackQueryHandler(back_to_publishers, pattern=f"^{PREFIX}:back_pub$"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:main$"),
                CallbackQueryHandler(back_to_subjects, pattern=f"^{PREFIX}:back$"),
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
