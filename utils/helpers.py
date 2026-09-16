"""
توابع کمکی مشترک بین handlerها.
"""
from database.misc import list_forced_channels

_MEMBER_STATUSES = {"member", "administrator", "creator"}


async def get_unjoined_channels(bot, user_id: int) -> list[dict]:
    """
    لیست کانال‌های اجباری‌ای که کاربر هنوز عضوشون نشده رو برمی‌گردونه.
    اگه لیست خالی باشه یعنی کاربر همه رو عضو شده (یا اصلاً کانالی تنظیم نشده).
    نوع bot عمداً annotate نشده تا این ماژول بدون نصب بودن python-telegram-bot
    هم قابل import و تست باشه (import کتابخونه تلگرام lazy انجام می‌شه).
    """
    from telegram.error import TelegramError

    channels = list_forced_channels()
    unjoined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status not in _MEMBER_STATUSES:
                unjoined.append(dict(ch))
        except TelegramError:
            # اگه ربات ادمین کانال نباشه یا کانال در دسترس نباشه، برای احتیاط
            # کاربر رو ملزم به عضویت در نظر می‌گیریم تا خطا بی‌صدا رد نشه
            unjoined.append(dict(ch))
    return unjoined


def validate_full_name(text: str) -> tuple[bool, str]:
    """
    اعتبارسنجی نام و نام خانوادگی: حداقل ۲ کلمه‌ی معنادار.
    برمی‌گردونه (معتبر_است, متن_تمیزشده).
    """
    cleaned = " ".join(text.strip().split())
    words = [w for w in cleaned.split(" ") if w]
    if len(words) < 2:
        return False, cleaned
    return True, cleaned


def parse_referral_arg(args: list[str] | None) -> int | None:
    """
    از آرگومان دیپ‌لینک (مثل invite_123456) آیدی معرف رو استخراج می‌کنه.
    """
    if not args:
        return None
    arg = args[0]
    if arg.startswith("invite_"):
        candidate = arg[len("invite_"):]
        if candidate.isdigit():
            return int(candidate)
    return None


def parse_range_input(text: str, min_number: int, max_number: int) -> tuple[bool, int, int, str]:
    """
    ورودی محدوده‌ی تست به فرمت "شروع-پایان" (مثل 1-37) رو پارس و اعتبارسنجی می‌کنه.
    برمی‌گردونه (معتبر_است, شروع, پایان, پیام_خطا).
    """
    cleaned = text.strip().replace(" ", "")
    # پشتیبانی از اعداد فارسی/عربی هم
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    for i in range(10):
        cleaned = cleaned.replace(persian_digits[i], str(i)).replace(arabic_digits[i], str(i))

    for sep in ["-", "_", "تا", "to"]:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            break
    else:
        return False, 0, 0, "❌ فرمت اشتباهه. مثال درست: 1-37"

    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return False, 0, 0, "❌ فرمت اشتباهه. مثال درست: 1-37"

    start, end = int(parts[0]), int(parts[1])
    if start > end:
        return False, 0, 0, "❌ نادرست! شماره‌ی شروع باید کوچیک‌تر یا مساوی پایان باشه."
    if start < min_number or end > max_number:
        return False, 0, 0, f"❌ این فصل فقط تست {min_number} تا {max_number} داره."
    return True, start, end, ""


async def safe_edit_message_text(query, text: str, reply_markup=None, **kwargs) -> None:
    """
    مثل query.edit_message_text، ولی اگه محتوای جدید دقیقاً با پیام فعلی یکی
    باشه (که تلگرام باهاش خطای «Message is not modified» می‌ده)، به‌جای
    ترکیدن، فقط بی‌صدا رد می‌شه. این جلوی گیر کردن دکمه‌هایی رو می‌گیره که
    گاهی (مثلاً با دوبار سریع لمس کردن، یا وقتی محتوا از آخرین بار عوض نشده)
    قراره دقیقاً همون صفحه رو دوباره نشون بدن.
    """
    from telegram.error import BadRequest
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise
