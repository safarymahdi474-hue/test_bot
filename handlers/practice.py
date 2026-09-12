"""
بخش ۳: تمرین و آزمون — انتخاب پایه/رشته/درس/کتاب/فصل/محدوده/حالت و اجرای آزمون.
همچنین گزارش اشکال تست از همین‌جا شروع می‌شه.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import GRADES, MAJORS, SUBJECTS_BY_MAJOR, TEST_BOOK_PUBLISHERS, QUESTION_REPORT_TYPES
from database import content as C, exams as E, users as U
from database.reports import create_question_report
from utils.helpers import parse_range_input
from utils.keyboards import (
    grades_keyboard, majors_keyboard, subjects_keyboard,
    test_book_publishers_keyboard, with_back, plain_options_keyboard,
)

(SEL_GRADE, SEL_MAJOR, SEL_SUBJECT, SEL_BOOK, SEL_CHAPTER, SEL_RANGE,
 SEL_MODE, PRE_START, IN_EXAM, REPORT_TYPE, REPORT_DESC) = range(11)

PREFIX = "prac"


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """داده‌های موقت این جریان تمرین/آزمون رو در user_data نگه می‌داریم."""
    return context.user_data.setdefault("practice", {})


async def entry_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["practice"] = {}
    await query.edit_message_text(
        "🎯 تمرین و آزمون\n━━━━━━━━━━━━━━━\nپایه‌ت رو انتخاب کن:",
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
    _ud(context)["major"] = major
    await query.edit_message_text(
        f"📚 دروس {_ud(context)['grade']} {major}:",
        reply_markup=subjects_keyboard(PREFIX, major),
    )
    return SEL_SUBJECT


async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    subject = query.data.split(":", 2)[2]
    ud = _ud(context)
    ud["subject"] = subject

    books = C.list_test_books(ud["grade"], ud["major"], subject)
    if not books:
        await query.edit_message_text(
            "📖 هنوز تستی برای این درس ثبت نشده. یه درس دیگه رو امتحان کن.",
            reply_markup=subjects_keyboard(PREFIX, ud["major"]),
        )
        return SEL_SUBJECT

    rows = [[InlineKeyboardButton(b["name"], callback_data=f"{PREFIX}:tbook:{b['id']}")]
            for b in books]
    await query.edit_message_text(
        "📖 کتاب تستت رو انتخاب کن:", reply_markup=with_back(rows)
    )
    return SEL_BOOK


async def select_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    test_book_id = int(query.data.split(":", 2)[2])
    ud = _ud(context)
    ud["test_book_id"] = test_book_id

    book = C.get_test_book(test_book_id)
    chapters = C.list_chapters(test_book_id)
    if not chapters:
        await query.edit_message_text("📚 برای این کتاب هنوز فصلی ثبت نشده.")
        return ConversationHandler.END

    rows = [[InlineKeyboardButton(ch["name"], callback_data=f"{PREFIX}:chap:{ch['id']}")]
            for ch in chapters]
    await query.edit_message_text(
        f"📚 فصل‌های {book['name']} — {ud['subject']}:", reply_markup=with_back(rows)
    )
    return SEL_CHAPTER


async def select_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chapter_id = int(query.data.split(":", 2)[2])
    ud = _ud(context)
    ud["chapter_id"] = chapter_id

    chapter = C.get_chapter(chapter_id)
    bounds = C.get_min_max_question_number(chapter_id)
    if bounds is None:
        await query.edit_message_text("📝 برای این فصل هنوز سوالی ثبت نشده.")
        return ConversationHandler.END

    ud["min_number"], ud["max_number"] = bounds
    rows = [[InlineKeyboardButton("همه تست‌ها", callback_data=f"{PREFIX}:allrange")]]
    await query.edit_message_text(
        f"📝 فصل {chapter['name']}\n"
        f"تست‌های این فصل: {bounds[0]} تا {bounds[1]}\n\n"
        "از کدوم تا کدوم بزنی؟\n(مثال: {}-{})".format(bounds[0], bounds[1]),
        reply_markup=with_back(rows),
    )
    return SEL_RANGE


async def select_range_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ud = _ud(context)
    ud["start"], ud["end"] = ud["min_number"], ud["max_number"]
    return await _ask_mode(update, context)


async def select_range_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    ok, start, end, err = parse_range_input(update.message.text or "", ud["min_number"], ud["max_number"])
    if not ok:
        await update.message.reply_text(err)
        return SEL_RANGE
    ud["start"], ud["end"] = start, end
    await update.message.reply_text(f"✅ محدوده: تست {start} تا {end}")
    return await _ask_mode(update, context)


async def _ask_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = [
        [InlineKeyboardButton("⏱ زمان‌دار", callback_data=f"{PREFIX}:mode:timed")],
        [InlineKeyboardButton("📖 آزاد", callback_data=f"{PREFIX}:mode:free")],
    ]
    text = "⏱ حالت آزمون:"
    markup = with_back(rows)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return SEL_MODE


async def select_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":", 2)[2]
    ud = _ud(context)
    ud["mode"] = mode

    book = C.get_test_book(ud["test_book_id"])
    chapter = C.get_chapter(ud["chapter_id"])
    mode_label = "⏱ آزمون زمان‌دار" if mode == "timed" else "📖 آزمون آزاد"
    text = (
        f"{mode_label}\n━━━━━━━━━━━━━━━\n"
        f"📚 {ud['subject']} — {chapter['name']}\n"
        f"📖 {book['name']}\n"
        f"📝 تست {ud['start']} تا {ud['end']}\n"
    )
    rows = [[InlineKeyboardButton("🚀 شروع آزمون", callback_data=f"{PREFIX}:launch")]]
    await query.edit_message_text(text, reply_markup=with_back(rows))
    return PRE_START


async def launch_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ud = _ud(context)
    user_id = update.effective_user.id

    session = E.create_session(user_id, ud["chapter_id"], ud["start"], ud["end"], ud["mode"])
    ud["session_id"] = session["id"]
    return await _show_current_question(update, context)


async def _show_current_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    session_id = ud["session_id"]
    questions = E.get_session_questions_ordered(session_id)
    session = E.get_session(session_id)
    idx = session["current_index"]

    if idx >= len(questions):
        return await _finish_and_show_results(update, context, mark_finished=True)

    q = questions[idx]
    caption = f"❓ تست {idx + 1} از {len(questions)}"
    if session["mode"] == "timed":
        caption = "⏱ در حال اجرا (زمان‌دار)\n" + caption

    markup_rows = list(plain_options_keyboard(PREFIX).inline_keyboard)
    markup_rows.append([
        InlineKeyboardButton("⏭ رد کردن", callback_data=f"{PREFIX}:next"),
        InlineKeyboardButton("⏹ پایان آزمون", callback_data=f"{PREFIX}:stop"),
    ])
    markup_rows.append([
        InlineKeyboardButton("⚠️ گزارش اشکال در این تست", callback_data=f"{PREFIX}:report:{q['id']}")
    ])
    markup = InlineKeyboardMarkup(markup_rows)

    # سوال همیشه به‌صورت یه پیام عکسِ جدید فرستاده می‌شه (نه edit روی پیام قبلی)،
    # چون پیام قبلی می‌تونه متنی یا عکس باشه و تلگرام اجازه‌ی تبدیل نوع پیام
    # با edit_message_text/caption رو نمی‌ده.
    target_message = update.callback_query.message if update.callback_query else update.message
    await target_message.reply_photo(
        photo=q["question_image_file_id"], caption=caption, reply_markup=markup
    )
    return IN_EXAM


async def submit_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    ud = _ud(context)
    session_id = ud["session_id"]
    questions = E.get_session_questions_ordered(session_id)
    session = E.get_session(session_id)
    idx = session["current_index"]
    if idx >= len(questions):
        await query.answer()
        return await _finish_and_show_results(update, context, mark_finished=True)

    q = questions[idx]
    selected = int(query.data.split(":", 2)[2])
    result = E.submit_answer(session_id, q["id"], selected)

    if result["is_correct"]:
        await query.answer("✅ درسته!")
    else:
        await query.answer(f"❌ غلط. پاسخ درست: گزینه {result['correct_option']}", show_alert=True)
        if q["explanation_image_file_id"]:
            await query.message.reply_photo(
                photo=q["explanation_image_file_id"], caption="📝 توضیح / پاسخ‌نامه"
            )

    E.advance_session(session_id)
    return await _show_current_question(update, context)


async def skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ud = _ud(context)
    E.advance_session(ud["session_id"])
    return await _show_current_question(update, context)


async def stop_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # آزمونی که زودتر متوقف می‌شه finished نمی‌شه تا بشه بعداً «ادامه»اش داد
    return await _finish_and_show_results(update, context, mark_finished=False)


async def _finish_and_show_results(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    mark_finished: bool) -> int:
    ud = _ud(context)
    session_id = ud["session_id"]
    if mark_finished:
        E.finish_session(session_id)
    stats = E.get_session_stats(session_id)

    minutes, seconds = divmod(stats["elapsed_seconds"] or 0, 60)
    # «زودتر تموم شده» یعنی کاربر با دکمه‌ی ⏹ متوقف کرده (mark_finished=False)،
    # نه اینکه لزوماً سوال بی‌جواب مونده باشه.
    was_early = not mark_finished

    if was_early:
        text = (
            "⏹ آزمون تموم شد!\n━━━━━━━━━━━━━━━\n"
            "بعضی سوال‌ها پاسخ داده نشده.\n\n"
            f"📊 نتیجه تا اینجا:\n"
            f"تست کل: {stats['total']}\n"
            f"درست: {stats['correct']}\n"
            f"غلط: {stats['wrong']}\n"
            f"پاسخ‌نداده: {stats['unanswered']}\n"
            f"درصد: {stats['percent']}٪\n\n"
            f"⏱ زمان: {minutes:02d}:{seconds:02d}\n\n"
            f"💰 امتیاز: +{stats['points_earned']}"
        )
    else:
        text = (
            "✅ آزمون تموم شد!\n\n"
            f"📊 نتیجه:\n━━━━━━━━━━━━━━━\n"
            f"تست کل: {stats['total']}\n"
            f"درست: {stats['correct']}\n"
            f"غلط: {stats['wrong']}\n"
            f"درصد: {stats['percent']}٪\n\n"
            f"⏱ زمان: {minutes:02d}:{seconds:02d}\n\n"
            f"💰 امتیاز: +{stats['points_earned']}"
        )

    rows = [[InlineKeyboardButton("📊 کارنامه کامل", callback_data="menu:report_card")]]
    if was_early:
        rows.append([InlineKeyboardButton("🔁 ادامه آزمون", callback_data=f"{PREFIX}:resume:{session_id}")])
    else:
        rows.append([InlineKeyboardButton("🔁 دوباره", callback_data=f"{PREFIX}:restart")])
    rows.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu:main")])

    markup = InlineKeyboardMarkup(rows)
    # این تابع همیشه در واکنش به کلیک روی دکمه‌ای زیر عکسِ یه سوال صدا زده می‌شه؛
    # چون پیام مبدا عکسه، به‌جای edit یه پیام متنی جدید می‌فرستیم.
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

    if not was_early:
        # آزمون واقعاً تموم شده (کامل یا به هر دلیلی finish شده)؛ دیگه چیزی برای ادامه نیست
        context.user_data.pop("practice", None)
    return ConversationHandler.END


async def resume_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    session_id = int(query.data.split(":", 2)[2])
    session = E.get_session(session_id)

    if session is None or session["user_id"] != update.effective_user.id \
            or session["status"] != "in_progress":
        await query.edit_message_text("این آزمون دیگه در دسترس نیست.")
        return ConversationHandler.END

    context.user_data["practice"] = {"session_id": session_id, "chapter_id": session["chapter_id"]}
    return await _show_current_question(update, context)


async def restart_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["practice"] = {}
    return await entry_practice(update, context)


# ==================== گزارش اشکال تست ====================

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_id = int(query.data.split(":", 2)[2])
    context.user_data["report_question_id"] = question_id

    rows = [[InlineKeyboardButton(label, callback_data=f"rep:type:{key}")]
            for key, label in QUESTION_REPORT_TYPES.items()]
    # توجه: پیام مبدا (سوال) الان یه عکسه، نه متن؛ نمی‌شه با edit_message_text
    # یه عکس رو به متن تبدیل کرد، پس یه پیام جدید می‌فرستیم.
    await query.message.reply_text("⚠️ گزارش اشکال\n━━━━━━━━━━━━━━━\nمشکل این تست چیه؟",
                                    reply_markup=InlineKeyboardMarkup(rows))
    return REPORT_TYPE


async def select_report_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    report_type = query.data.split(":", 2)[2]
    context.user_data["report_type"] = report_type

    if report_type == "other":
        await query.edit_message_text("💬 توضیحت رو بنویس:")
        return REPORT_DESC

    question_id = context.user_data.pop("report_question_id")
    create_question_report(question_id, update.effective_user.id, report_type, None)
    await query.edit_message_text("✅ گزارشت ثبت شد!\nممنون که کمک می‌کنی دقیق‌تر بشیم 🌹")
    return await _return_to_exam_or_end(update, context)


async def receive_report_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question_id = context.user_data.pop("report_question_id")
    report_type = context.user_data.pop("report_type", "other")
    create_question_report(question_id, update.effective_user.id, report_type, update.message.text)
    await update.message.reply_text("✅ گزارشت ثبت شد!\nممنون که کمک می‌کنی دقیق‌تر بشیم 🌹")
    return await _return_to_exam_or_end(update, context)


async def _return_to_exam_or_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = context.user_data.get("practice")
    if ud and ud.get("session_id"):
        session = E.get_session(ud["session_id"])
        if session and session["status"] == "in_progress":
            return await _show_current_question(update, context)
    return ConversationHandler.END


def build_practice_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(entry_practice, pattern=r"^menu:practice$"),
            CallbackQueryHandler(resume_exam, pattern=f"^{PREFIX}:resume:"),
            CallbackQueryHandler(restart_exam, pattern=f"^{PREFIX}:restart$"),
        ],
        states={
            SEL_GRADE: [CallbackQueryHandler(select_grade, pattern=f"^{PREFIX}:grade:")],
            SEL_MAJOR: [CallbackQueryHandler(select_major, pattern=f"^{PREFIX}:major:")],
            SEL_SUBJECT: [CallbackQueryHandler(select_subject, pattern=f"^{PREFIX}:subject:")],
            SEL_BOOK: [CallbackQueryHandler(select_book, pattern=f"^{PREFIX}:tbook:")],
            SEL_CHAPTER: [CallbackQueryHandler(select_chapter, pattern=f"^{PREFIX}:chap:")],
            SEL_RANGE: [
                CallbackQueryHandler(select_range_all, pattern=f"^{PREFIX}:allrange$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_range_text),
            ],
            SEL_MODE: [CallbackQueryHandler(select_mode, pattern=f"^{PREFIX}:mode:")],
            PRE_START: [CallbackQueryHandler(launch_exam, pattern=f"^{PREFIX}:launch$")],
            IN_EXAM: [
                CallbackQueryHandler(submit_answer_callback, pattern=f"^{PREFIX}:answer:"),
                CallbackQueryHandler(skip_question, pattern=f"^{PREFIX}:next$"),
                CallbackQueryHandler(stop_exam, pattern=f"^{PREFIX}:stop$"),
                CallbackQueryHandler(start_report, pattern=f"^{PREFIX}:report:"),
            ],
            REPORT_TYPE: [CallbackQueryHandler(select_report_type, pattern=r"^rep:type:")],
            REPORT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_report_desc)],
        },
        fallbacks=[
            CallbackQueryHandler(entry_practice, pattern=r"^back$"),
            # اگه کاربر وسط یه مرحله گیر کرده باشه (مثلاً با /start یا منوی اصلی
            # خارج شده و این ConversationHandler هنوز state قدیمیش رو نگه داشته)،
            # کلیک دوباره روی همین دکمه‌های ورودی باید از نو شروع کنه، نه اینکه
            # بی‌صدا نادیده گرفته بشه. برای همین همون entry_points رو این‌جا هم می‌ذاریم.
            CallbackQueryHandler(entry_practice, pattern=r"^menu:practice$"),
            CallbackQueryHandler(resume_exam, pattern=f"^{PREFIX}:resume:"),
            CallbackQueryHandler(restart_exam, pattern=f"^{PREFIX}:restart$"),
        ],
        name="practice_conversation",
        persistent=False,
        map_to_parent={ConversationHandler.END: ConversationHandler.END},
    )
