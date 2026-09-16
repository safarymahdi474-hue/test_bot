"""
بخش ۸: رقابت و امتیاز.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import get_rank, POINTS_PER_INVITE
from database import users as U
from utils.helpers import safe_edit_message_text


def _format_leaderboard(rows, title: str) -> str:
    lines = [title, "━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("هنوز کسی امتیازی نگرفته.")
    for i, r in enumerate(rows, start=1):
        name = r["full_name"] or "کاربر"
        lines.append(f"{i}. {name}     {r['score']:,}")
    return "\n".join(lines)


async def show_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = U.get_user(user_id)
    rows = U.get_leaderboard(weekly=True, limit=10)
    pos = U.get_user_rank_position(user_id, weekly=True)

    text = (
        "🏆 رقابت و امتیاز\n━━━━━━━━━━━━━━━\n"
        f"💰 امتیاز تو: {user['points']:,}\n"
        f"🏅 مقام: {get_rank(user['points'])}\n\n"
        + _format_leaderboard(rows, "🥇 لیدربورد هفتگی:")
        + "\n━━━━━━━━━━━━━━━\n"
    )
    if pos:
        text += f"📍 رتبه تو: {pos[0]} از {pos[1]}\n💰 امتیاز تو: {user['weekly_points']:,}"

    rows_kb = [
        [InlineKeyboardButton("📊 لیدربورد کلی", callback_data="lb:overall")],
        [InlineKeyboardButton("👥 دعوت دوستان", callback_data="lb:invite")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")],
    ]
    await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(rows_kb))


async def show_overall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = U.get_user(user_id)
    rows = U.get_leaderboard(weekly=False, limit=10)
    pos = U.get_user_rank_position(user_id, weekly=False)

    text = _format_leaderboard(rows, "🥇 لیدربورد کلی") + "\n━━━━━━━━━━━━━━━\n"
    if pos:
        text += f"📍 رتبه تو: {pos[0]} از {pos[1]}\n💰 امتیاز تو: {user['points']:,}"

    rows_kb = [
        [InlineKeyboardButton("📊 لیدربورد هفتگی", callback_data="lb:weekly")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:leaderboard")],
    ]
    await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(rows_kb))


async def show_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = U.get_user(user_id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=invite_{user_id}"

    text = (
        "👥 دعوت دوستان\n━━━━━━━━━━━━━━━\n"
        f"هر کی با لینک تو بیاد،\n{POINTS_PER_INVITE} امتیاز می‌گیری!\n\n"
        f"🔗 لینک دعوت تو:\n{link}\n\n"
        f"👥 تا الان دعوت کردی: {user['invited_count']} نفر\n"
        f"💰 امتیاز گرفته: {user['invited_count'] * POINTS_PER_INVITE:,}"
    )
    rows_kb = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:leaderboard")]]
    await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(rows_kb))


leaderboard_handlers = [
    CallbackQueryHandler(show_weekly, pattern=r"^menu:leaderboard$"),
    CallbackQueryHandler(show_weekly, pattern=r"^lb:weekly$"),
    CallbackQueryHandler(show_overall, pattern=r"^lb:overall$"),
    CallbackQueryHandler(show_invite, pattern=r"^lb:invite$"),
]
