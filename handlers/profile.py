"""
بخش ۹: پروفایل من (شامل پشتیبانی و انتقاد/پیشنهاد).
همچنین بخش ۵: کارنامه (📊 کارنامه من) که از همون منو باز می‌شه.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import get_rank, MISTAKES_PAGE_SIZE, MISTAKES_MAX_PAGES
from database import users as U, exams as E, content as C
from database.misc import create_feedback, list_user_feedback

AWAITING_FEEDBACK = 0


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = U.get_user(update.effective_user.id)
    text = (
        "👤 پروفایل من\n━━━━━━━━━━━━━━━\n"
        f"👤 نام: {user['full_name']}\n"
        f"📚 پایه: {user['grade']}\n"
        f"🎓 رشته: {user['major']}\n"
        f"🆔 آیدی: @{user['username'] or '—'}\n"
        f"🏅 مقام: {get_rank(user['points'])}\n"
        f"💰 امتیاز: {user['points']:,}\n"
    )
    rows = [
        [InlineKeyboardButton("✏️ ویرایش اطلاعات", callback_data="profile:edit")],
        [InlineKeyboardButton("🆘 پشتیبانی", callback_data="profile:support")],
        [InlineKeyboardButton("📩 انتقاد و پیشنهاد", callback_data="profile:feedback")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "🆘 پشتیبانی\n━━━━━━━━━━━━━━━\n"
        "سوالات متداول:\n"
        "• چرا تست‌هام ذخیره نمی‌شه؟\n"
        "• چطور فایل کتب بگیرم؟\n"
        "• چطور درصد بالاتری بزنم؟\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📩 برای ارتباط با پشتیبانی، از بخش «📩 انتقاد و پیشنهاد» پیام بده."
    )
    rows = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:profile")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


def _format_feedback_history(items) -> str:
    lines = ["📩 انتقاد و پیشنهاد", "━━━━━━━━━━━━━━━", "📬 پیام‌های تو (۱۰ تای آخر):", ""]
    if not items:
        lines.append("هنوز پیامی نفرستادی.")
    for i, f in enumerate(items, start=1):
        lines.append(f"{i}. {f['message']}")
        lines.append(f"   📅 {f['created_at'][:10]}")
        if f["admin_response"]:
            lines.append(f"   💬 پاسخ ادمین: {f['admin_response']}")
        else:
            lines.append("   💬 پاسخ ادمین: در انتظار پاسخ")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append("پیام جدیدت رو بنویس:")
    return "\n".join(lines)


async def show_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    items = list_user_feedback(update.effective_user.id)
    rows = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:profile")]]
    await query.edit_message_text(_format_feedback_history(items), reply_markup=InlineKeyboardMarkup(rows))
    return AWAITING_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("متن پیامت رو بنویس:")
        return AWAITING_FEEDBACK
    create_feedback(update.effective_user.id, text)
    rows = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:profile")]]
    await update.message.reply_text(
        "✅ پیامت ارسال شد.\nممنون که کمک می‌کنی بهتر بشیم 🌹",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return ConversationHandler.END


# ==================== کارنامه (بخش ۵) ====================

async def show_report_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    overview = U.get_user_overview(user_id)

    if overview["total_tests"] == 0:
        text = "📊 کارنامه من\n━━━━━━━━━━━━━━━\nهنوز تستی نزدی!\nبریم اولین تستت رو بزنیم؟"
        rows = [
            [InlineKeyboardButton("🎯 شروع تست", callback_data="menu:practice")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
        return

    breakdown = U.get_subject_breakdown(user_id)
    weakest = U.get_weakest_topic(user_id)

    lines = [
        "📊 کارنامه من", "━━━━━━━━━━━━━━━",
        f"👤 {overview['full_name']} | {overview['grade']} {overview['major']}",
        f"🏅 مقام: {overview['rank']}", "",
        f"💰 امتیاز: {overview['points']:,}",
        f"📝 تست کل: {overview['total_tests']}",
        f"🎯 درصد کلی: {overview['overall_percent']}٪",
        "━━━━━━━━━━━━━━━", "📚 عملکرد درسی:",
    ]
    for b in breakdown:
        filled = "█" * (b["percent"] // 10)
        empty = "░" * (10 - b["percent"] // 10)
        emoji = "🟢" if b["percent"] >= 70 else ("🟡" if b["percent"] >= 50 else "🔴")
        lines.append(f"{b['subject']:<7} {filled}{empty}  {b['percent']}٪  {emoji}")

    if weakest:
        lines += ["━━━━━━━━━━━━━━━", "⚠️ ضعیف‌ترین مبحث:",
                   f"«{weakest['subject']} - {weakest['chapter']}» {weakest['percent']}٪"]

    rows = [
        [InlineKeyboardButton("📖 دیدن اشتباهاتم", callback_data="mistakes:page:1")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")],
    ]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


def _format_mistakes_page(items, page: int, total_pages: int) -> str:
    lines = [
        "📖 اشتباهات من", "━━━━━━━━━━━━━━━",
        f"صفحه {page} از {total_pages}", "",
    ]
    if not items:
        lines.append("اشتباهی ثبت نشده 🎉")
    for m in items:
        lines.append(f"📚 {m['subject']} — {m['chapter_name']} — تست {m['question_number']}")
        lines.append(f"   پاسخ تو: گزینه {m['selected_option']}")
        lines.append(f"   پاسخ درست: گزینه {m['correct_option']}")
        lines.append("")
    return "\n".join(lines)


async def show_mistakes_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 2)[2])
    user_id = update.effective_user.id

    total_mistakes = E.count_user_mistakes(user_id, cap=MISTAKES_PAGE_SIZE * MISTAKES_MAX_PAGES)
    total_pages = max(1, -(-total_mistakes // MISTAKES_PAGE_SIZE))  # سقف تقسیم
    page = max(1, min(page, total_pages))

    items = E.get_user_mistakes_page(user_id, page, MISTAKES_PAGE_SIZE)
    text = _format_mistakes_page(items, page, total_pages)

    rows = []
    if items:
        # هر ۳ آیتم توی یه ردیف، برای دیدن عکس سوال + پاسخ‌نامه
        view_buttons = [
            InlineKeyboardButton(f"🖼 تست {m['question_number']}",
                                  callback_data=f"mistakes:view:{m['question_id']}")
            for m in items
        ]
        for i in range(0, len(view_buttons), 3):
            rows.append(view_buttons[i:i + 3])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"mistakes:page:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"mistakes:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:report_card")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def view_mistake_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    question_id = int(query.data.split(":", 2)[2])
    question = C.get_question(question_id)
    if question is None:
        await query.answer("❌ این سوال دیگه در دسترس نیست.", show_alert=True)
        return

    await query.message.reply_photo(
        photo=question["question_image_file_id"],
        caption=f"❓ تست {question['number']}\n✅ پاسخ درست: گزینه {question['correct_option']}",
    )
    if question["explanation_image_file_id"]:
        await query.message.reply_photo(
            photo=question["explanation_image_file_id"], caption="📝 توضیح / پاسخ‌نامه"
        )


def build_feedback_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(show_feedback, pattern=r"^profile:feedback$")],
        states={
            AWAITING_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback)],
        },
        fallbacks=[CallbackQueryHandler(show_feedback, pattern=r"^profile:feedback$")],
        name="feedback_conversation",
        persistent=False,
    )


profile_handlers = [
    CallbackQueryHandler(show_profile, pattern=r"^menu:profile$"),
    CallbackQueryHandler(show_support, pattern=r"^profile:support$"),
    CallbackQueryHandler(show_report_card, pattern=r"^menu:report_card$"),
    CallbackQueryHandler(show_mistakes_page, pattern=r"^mistakes:page:"),
    CallbackQueryHandler(view_mistake_image, pattern=r"^mistakes:view:"),
]
