"""
📚 مدیریت کتاب‌ها (سمت ادمین) — مشاهده لیست موجود/ناموجود.
افزودن فایل با فوروارد کردن فایل به همراه کپشن «پایه | رشته | درس | ناشر»
به ربات انجام می‌شه (در bot.py هندل می‌شه).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import ADMIN_IDS, BOOKS_LIST_PAGE_SIZE
from database import content as C


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def show_library_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    counts = C.count_library_books()
    text = (
        "📚 مدیریت کتاب‌ها\n━━━━━━━━━━━━━━━\n"
        f"📊 تعداد کتاب‌ها: {counts['total']}\n\n"
        f"✅ موجود: {counts['available']}\n"
        f"❌ ناموجود: {counts['unavailable']}\n"
    )
    rows = [
        [InlineKeyboardButton("📋 دیدن لیست", callback_data="admin:lib_list:1")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def show_library_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    page = int(query.data.split(":", 2)[2])
    books = C.list_all_library_books_page(page, BOOKS_LIST_PAGE_SIZE)
    counts = C.count_library_books()
    total_pages = max(1, -(-counts["total"] // BOOKS_LIST_PAGE_SIZE))
    page = max(1, min(page, total_pages))

    lines = ["📚 لیست کتاب‌ها", "━━━━━━━━━━━━━━━", f"صفحه {page} از {total_pages}", ""]
    for b in books:
        mark = "✅" if b["available"] else "❌"
        lines.append(f"{mark} {b['subject']} {b['grade']} — {b['major']} — {b['publisher']}")
    if not books:
        lines.append("کتابی ثبت نشده.")

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:lib_list:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin:lib_list:{page + 1}"))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin:library_books")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


library_admin_handlers = [
    CallbackQueryHandler(show_library_stats, pattern=r"^admin:library_books$"),
    CallbackQueryHandler(show_library_list, pattern=r"^admin:lib_list:"),
]
