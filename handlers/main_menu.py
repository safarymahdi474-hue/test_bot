"""
بخش ۲: پنل اصلی.
"""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from database import users as U
from database.db import get_connection
from utils.keyboards import main_menu_keyboard


def _tests_today_count(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM exam_answers ea
               JOIN exam_sessions es ON ea.session_id = es.id
               WHERE es.user_id = ? AND date(ea.answered_at) = date('now')
               AND ea.selected_option IS NOT NULL""",
            (user_id,),
        ).fetchone()
        return row["c"]


def _menu_text(full_name: str, tests_today: int) -> str:
    first_name = full_name.split()[0] if full_name else "دوست من"
    if tests_today == 0:
        return f"سلام {first_name} 👋\nامروز ۰ تست زدی — بریم شروع کنیم؟"
    return f"سلام {first_name} 👋\nامروز {tests_today} تست زدی — همینطوری ادامه بده 🔥"


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = U.get_user(user_id)
    tests_today = _tests_today_count(user_id)
    text = _menu_text(user["full_name"] if user else "دوست من", tests_today)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await send_main_menu(update, context)


main_menu_router_handler = CallbackQueryHandler(main_menu_callback, pattern=r"^menu:main$")
