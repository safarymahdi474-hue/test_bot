"""
⚙️ پنل مدیریت — ورود، آمار کاربران، لیست/جستجوی کاربران.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    CommandHandler, MessageHandler, filters,
)

from config import ADMIN_IDS, get_rank, USERS_LIST_PAGE_SIZE
from database import users as U

AWAITING_SEARCH = 0


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 کاربران", callback_data="admin:users")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⚙️ تنظیم جوین اجباری", callback_data="admin:channels")],
        [InlineKeyboardButton("📚 مدیریت کتاب‌ها", callback_data="admin:library_books")],
        [InlineKeyboardButton("📝 مدیریت تست‌ها", callback_data="admin:tests")],
        [InlineKeyboardButton("📝 مدیریت امتحان نهایی", callback_data="admin:final_exams")],
        [InlineKeyboardButton("📢 تنظیم کانال اخبار", callback_data="admin:news_settings")],
        [InlineKeyboardButton("📢 گزارش‌ها", callback_data="admin:book_requests")],
        [InlineKeyboardButton("📩 انتقادات", callback_data="admin:feedback")],
    ])


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ این دستور فقط برای ادمینه.")
        return
    await update.message.reply_text(
        "⚙️ پنل مدیریت\n━━━━━━━━━━━━━━━\nخوش اومدی مدیر 👋",
        reply_markup=admin_panel_keyboard(),
    )


async def back_to_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return
    await query.edit_message_text(
        "⚙️ پنل مدیریت\n━━━━━━━━━━━━━━━\nخوش اومدی مدیر 👋",
        reply_markup=admin_panel_keyboard(),
    )


# ==================== کاربران ====================

async def show_users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    text = (
        "👥 کاربران\n━━━━━━━━━━━━━━━\n"
        "📊 آمار کلی:\n"
        f"👤 تعداد کل: {U.count_registered_users()}\n"
        f"📅 امروز عضو شدن: {U.count_registered_today()}\n"
        f"📅 این هفته: {U.count_registered_this_week()}\n"
        f"📅 این ماه: {U.count_registered_this_month()}\n"
        f"📝 تست زده‌شده امروز: {U.count_tests_answered_today()}\n"
        f"🔥 کاربران فعال امروز: {U.count_active_users_today()}\n"
    )
    rows = [
        [InlineKeyboardButton("📋 لیست کاربران", callback_data="admin:users_list:1")],
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin:users_search")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


def _format_user_card(u) -> str:
    overview = U.get_user_overview(u["user_id"])
    return (
        f"👤 {u['full_name']}\n"
        f"🆔 @{u['username'] or '—'} | {u['user_id']}\n"
        f"📚 {u['grade']} {u['major']}\n"
        f"📝 تست: {overview['total_tests']} | 🎯 {overview['overall_percent']}٪\n"
        f"💰 امتیاز: {u['points']:,} | 🏅 {get_rank(u['points'])}"
    )


async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    page = int(query.data.split(":", 2)[2])
    total = U.count_registered_users()
    total_pages = max(1, -(-total // USERS_LIST_PAGE_SIZE))
    page = max(1, min(page, total_pages))
    page_users = U.list_users_page(page, USERS_LIST_PAGE_SIZE)

    lines = ["👥 لیست کاربران", "━━━━━━━━━━━━━━━", f"صفحه {page} از {total_pages}", ""]
    for u in page_users:
        lines.append(_format_user_card(u))
        lines.append("")

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:users_list:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin:users_list:{page + 1}"))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin:users_search")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin:users")])

    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def ask_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END
    await query.edit_message_text("🔍 جستجوی کاربر\n\nآیدی عددی یا یوزرنیم کاربر رو بنویس:")
    return AWAITING_SEARCH


async def receive_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = U.search_user((update.message.text or "").strip())
    if result is None:
        await update.message.reply_text("❌ کاربری با این مشخصات پیدا نشد. دوباره امتحان کن:")
        return AWAITING_SEARCH

    text = _format_user_card(result) + f"\n\n📅 عضویت: {result['registered_at'] or '—'}"
    rows = [
        [InlineKeyboardButton("📊 دیدن کارنامه", callback_data=f"admin:user_card:{result['user_id']}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:users")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END


def build_user_search_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_search_query, pattern=r"^admin:users_search$")],
        states={
            AWAITING_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_search_query)],
        },
        fallbacks=[CallbackQueryHandler(ask_search_query, pattern=r"^admin:users_search$")],
        name="admin_user_search_conversation",
        persistent=False,
    )


async def show_user_report_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    target_id = int(query.data.split(":", 2)[2])
    overview = U.get_user_overview(target_id)
    if overview is None:
        await query.edit_message_text("این کاربر پیدا نشد.")
        return

    breakdown = U.get_subject_breakdown(target_id)
    lines = [
        f"📊 کارنامه‌ی {overview['full_name']}", "━━━━━━━━━━━━━━━",
        f"📚 {overview['grade']} {overview['major']}",
        f"🏅 مقام: {overview['rank']}",
        f"💰 امتیاز: {overview['points']:,}",
        f"📝 تست کل: {overview['total_tests']}",
        f"🎯 درصد کلی: {overview['overall_percent']}٪",
    ]
    if breakdown:
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("📚 عملکرد درسی:")
        for b in breakdown:
            lines.append(f"{b['subject']}: {b['percent']}٪ ({b['total']} تست)")

    rows = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin:users")]]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


admin_panel_handlers = [
    CommandHandler("admin", admin_command),
    CallbackQueryHandler(back_to_admin_panel, pattern=r"^admin:panel$"),
    CallbackQueryHandler(show_users_stats, pattern=r"^admin:users$"),
    CallbackQueryHandler(users_list, pattern=r"^admin:users_list:"),
    CallbackQueryHandler(show_user_report_card, pattern=r"^admin:user_card:"),
]
