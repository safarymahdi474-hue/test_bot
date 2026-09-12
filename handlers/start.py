"""
بخش ۱: پنل ورودی — جوین اجباری + ثبت‌نام کاربر جدید.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)

from database import users as U
from utils.helpers import get_unjoined_channels, validate_full_name, parse_referral_arg
from utils.keyboards import grades_keyboard, majors_keyboard, confirm_keyboard, main_menu_keyboard

# ==================== وضعیت‌های گفتگو ====================
AWAITING_NAME, AWAITING_GRADE, AWAITING_MAJOR, AWAITING_CONFIRM, AWAITING_EDIT_CHOICE = range(5)

PENDING_REFERRAL_KEY = "pending_referrer_id"


def _welcome_text(full_name: str) -> str:
    return (
        f"سلام {full_name} 👋\n"
        "به ربات تست و کنکور خوش اومدی\n\n"
        "اینجا می‌تونی:\n"
        "🎯 تست کنکور بزنی\n"
        "📝 برای امتحان نهایی آماده شی\n"
        "📚 کتاب‌های درسی رو دانلود کنی\n\n"
        "بریم ثبت‌نام کنیم؟"
    )


async def _show_join_prompt(update: Update, unjoined: list[dict]) -> None:
    rows = [[InlineKeyboardButton(f"📢 عضویت در {ch['title']}", url=ch["invite_link"])]
            for ch in unjoined]
    rows.append([InlineKeyboardButton("✅ عضو شدم", callback_data="joincheck")])
    text = "📢 برای استفاده از ربات، اول در کانال(های) زیر عضو شو:"
    markup = InlineKeyboardMarkup(rows)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_user = update.effective_user
    U.get_or_create_user(tg_user.id, tg_user.username)
    U.touch_last_active(tg_user.id)

    referrer_id = parse_referral_arg(context.args)
    if referrer_id:
        context.user_data[PENDING_REFERRAL_KEY] = referrer_id

    unjoined = await get_unjoined_channels(context.bot, tg_user.id)
    if unjoined:
        await _show_join_prompt(update, unjoined)
        return ConversationHandler.END

    return await _after_join_check(update, context)


async def join_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    unjoined = await get_unjoined_channels(context.bot, tg_user.id)
    if unjoined:
        await query.answer("❌ هنوز عضو نشدی! اول عضو شو بعد دکمه رو بزن.", show_alert=True)
        return ConversationHandler.END

    return await _after_join_check(update, context)


async def _after_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_user = update.effective_user
    user_row = U.get_user(tg_user.id)

    if user_row and user_row["registration_step"] == "done":
        from handlers.main_menu import send_main_menu
        await send_main_menu(update, context)
        return ConversationHandler.END

    text = _welcome_text(tg_user.first_name or "دوست من")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ شروع ثبت‌نام", callback_data="reg:begin")]])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return ConversationHandler.END


# ==================== شروع مکالمه‌ی ثبت‌نام ====================

async def begin_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    U.set_registration_step(user_id, "awaiting_name")
    await query.edit_message_text(
        "نام و نام خانوادگیت رو بنویس:\n(مثال: علی رضایی)"
    )
    return AWAITING_NAME


async def _show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user = U.get_user(user_id)
    text = (
        "یه بار چک کن:\n\n"
        f"👤 نام: {user['full_name']}\n"
        f"📚 پایه: {user['grade']}\n"
        f"🎓 رشته: {user['major']}\n\n"
        "همه چی درسته؟"
    )
    markup = confirm_keyboard(
        yes_data="reg:confirm_yes", no_data="reg:confirm_edit",
        yes_text="✅ بله، درسته", no_text="✏️ ویرایش",
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return AWAITING_CONFIRM


async def confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_before = U.get_user(user_id)
    was_already_registered = user_before is not None and user_before["registration_step"] == "done"

    if not was_already_registered:
        U.complete_registration(user_id)
        referrer_id = context.user_data.pop(PENDING_REFERRAL_KEY, None)
        if referrer_id:
            U.set_referrer(user_id, referrer_id)

    user = U.get_user(user_id)

    if was_already_registered:
        await query.edit_message_text("✅ اطلاعاتت با موفقیت به‌روز شد.")
        from handlers.main_menu import send_main_menu
        await send_main_menu(update, context)
        return ConversationHandler.END

    major_label = user["major"].replace("علوم ", "") if user["major"] else ""
    text = (
        f"🎉 ثبت‌نامت کامل شد {user['full_name'].split()[0]}!\n\n"
        f"{user['grade']} {major_label}؟ آفرین 💪\n"
        "امسال بهترین سالت می‌شه.\n\n"
        "حالا بریم شروع کنیم:"
    )
    await query.edit_message_text(text)
    from handlers.main_menu import send_main_menu
    await send_main_menu(update, context)
    return ConversationHandler.END


async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    rows = [
        [InlineKeyboardButton("👤 اسم", callback_data="reg:edit_name")],
        [InlineKeyboardButton("📚 پایه", callback_data="reg:edit_grade")],
        [InlineKeyboardButton("🎓 رشته", callback_data="reg:edit_major")],
    ]
    await query.edit_message_text(
        "الان کدوم رو می‌خوای تغییر بدی؟", reply_markup=InlineKeyboardMarkup(rows)
    )
    return AWAITING_EDIT_CHOICE


async def edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "edit_name":
        await query.edit_message_text("نام و نام خانوادگی جدیدت رو بنویس:")
        return AWAITING_NAME
    if choice == "edit_grade":
        await query.edit_message_text(
            "پایه جدیدت رو انتخاب کن:",
            reply_markup=grades_keyboard(prefix="reg", with_back_button=False),
        )
        return AWAITING_GRADE
    if choice == "edit_major":
        await query.edit_message_text(
            "رشته جدیدت رو انتخاب کن:",
            reply_markup=majors_keyboard(prefix="reg", with_back_button=False),
        )
        return AWAITING_MAJOR
    return AWAITING_EDIT_CHOICE


# توجه: چون بعد از ویرایش اسم (متن) باید دوباره تأیید نشون داده بشه نه سوال پایه،
# در receive_name تشخیص می‌دیم که کاربر تازه ثبت‌نام می‌کنه یا داره ویرایش می‌کنه؛
# این کار با چک‌کردن اینکه grade/major از قبل پر شده یا نه انجام می‌شه.
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    valid, cleaned = validate_full_name(update.message.text or "")
    if not valid:
        await update.message.reply_text(
            "❌ لطفاً نام و نام خانوادگیت رو کامل بنویس.\n(مثال: علی رضایی)"
        )
        return AWAITING_NAME

    user_id = update.effective_user.id
    U.set_full_name(user_id, cleaned)
    user = U.get_user(user_id)

    if user["grade"] and user["major"]:
        # این ویرایش اسم بعد از تکمیل قبلی پایه/رشته‌ست -> برو مستقیم به تأیید
        return await _show_confirmation(update, context)

    U.set_registration_step(user_id, "awaiting_grade")
    await update.message.reply_text(
        f"{cleaned} جان، پایه‌ت چیه؟",
        reply_markup=grades_keyboard(prefix="reg", with_back_button=False),
    )
    return AWAITING_GRADE


# مشابه، بعد از ویرایش پایه یا رشته هم باید به تأیید برگردیم نه مرحله‌ی بعدی ثبت‌نام اولیه.
async def receive_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    grade = query.data.split(":", 2)[2]
    user_id = update.effective_user.id
    U.set_grade(user_id, grade)
    user = U.get_user(user_id)

    if user["full_name"] and user["major"]:
        return await _show_confirmation(update, context)

    U.set_registration_step(user_id, "awaiting_major")
    await query.edit_message_text(
        "رشته‌ت چیه؟",
        reply_markup=majors_keyboard(prefix="reg", with_back_button=False),
    )
    return AWAITING_MAJOR


async def receive_major(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    major = query.data.split(":", 2)[2]
    user_id = update.effective_user.id
    U.set_major(user_id, major)
    return await _show_confirmation(update, context)


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("ثبت‌نام لغو شد. هر وقت خواستی با /start دوباره شروع کن.")
    return ConversationHandler.END


def build_registration_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(begin_registration, pattern=r"^reg:begin$"),
            # ورود مستقیم به «ویرایش اطلاعات» از داخل پروفایل کاربر ثبت‌نام‌شده
            CallbackQueryHandler(confirm_edit, pattern=r"^profile:edit$"),
        ],
        states={
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_GRADE: [CallbackQueryHandler(receive_grade, pattern=r"^reg:grade:")],
            AWAITING_MAJOR: [CallbackQueryHandler(receive_major, pattern=r"^reg:major:")],
            AWAITING_CONFIRM: [
                CallbackQueryHandler(confirm_yes, pattern=r"^reg:confirm_yes$"),
                CallbackQueryHandler(confirm_edit, pattern=r"^reg:confirm_edit$"),
            ],
            AWAITING_EDIT_CHOICE: [
                CallbackQueryHandler(edit_choice, pattern=r"^reg:edit_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_registration)],
        name="registration_conversation",
        persistent=False,
    )


# هندلر مستقل برای دکمه‌ی «✅ عضو شدم» (خارج از ConversationHandler ثبت‌نام)
join_check_handler = CallbackQueryHandler(join_check_callback, pattern=r"^joincheck$")
