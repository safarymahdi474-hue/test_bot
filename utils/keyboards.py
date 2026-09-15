"""
سازنده‌های کیبورد شیشه‌ای (Inline Keyboard) قابل استفاده مجدد در کل ربات.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import GRADES, MAJORS, SUBJECTS_BY_MAJOR, TEST_BOOK_PUBLISHERS

# ==================== کال‌بک‌های عمومی ====================
BACK = "back"
CANCEL = "cancel"


def back_button(callback_data: str = BACK) -> InlineKeyboardButton:
    return InlineKeyboardButton("🔙 بازگشت", callback_data=callback_data)


def single_back_row(callback_data: str = BACK) -> list[list[InlineKeyboardButton]]:
    return [[back_button(callback_data)]]


def with_back(rows: list[list[InlineKeyboardButton]],
              callback_data: str = BACK) -> InlineKeyboardMarkup:
    rows = rows + [[back_button(callback_data)]]
    return InlineKeyboardMarkup(rows)


# ==================== انتخاب پایه / رشته / درس / کتاب ====================
# نکته‌ی مهم: دکمه‌ی «بازگشت» این کیبوردها به‌جای callback_data ثابت "back"،
# پیش‌فرض f"{prefix}:back" می‌گیره. اگه چند مکالمه‌ی مستقل (تمرین، کتابخانه،
# امتحان نهایی، ...) همه از یه callback_data یکسان مثل "back" استفاده کنن،
# وقتی کاربر توی یکی از اون‌ها state قدیمی/گیرکرده داشته باشه، همون مکالمه
# کلیک "بازگشت" مکالمه‌ی دیگه رو هم می‌قاپه (چون توی صف بررسی handlerها
# زودتره). پیشوند دار کردن این مشکل رو کاملاً حذف می‌کنه.

def grades_keyboard(prefix: str, with_back_button: bool = True,
                     back_callback_data: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(g, callback_data=f"{prefix}:grade:{g}")] for g in GRADES]
    if not with_back_button:
        return InlineKeyboardMarkup(rows)
    return with_back(rows, callback_data=back_callback_data or f"{prefix}:back")


def majors_keyboard(prefix: str, with_back_button: bool = True,
                     back_callback_data: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(m, callback_data=f"{prefix}:major:{m}")] for m in MAJORS]
    if not with_back_button:
        return InlineKeyboardMarkup(rows)
    return with_back(rows, callback_data=back_callback_data or f"{prefix}:back")


def subjects_keyboard(prefix: str, grade: str, major: str,
                       back_callback_data: str | None = None) -> InlineKeyboardMarkup:
    from config import get_subjects
    subjects = get_subjects(grade, major)
    rows = [[InlineKeyboardButton(s, callback_data=f"{prefix}:subject:{s}")] for s in subjects]
    return with_back(rows, callback_data=back_callback_data or f"{prefix}:back")


def test_book_publishers_keyboard(prefix: str, available_names: list[str] | None = None,
                                   back_callback_data: str | None = None) -> InlineKeyboardMarkup:
    names = available_names if available_names is not None else TEST_BOOK_PUBLISHERS
    rows = [[InlineKeyboardButton(n, callback_data=f"{prefix}:book:{n}")] for n in names]
    return with_back(rows, callback_data=back_callback_data or f"{prefix}:back")


def confirm_keyboard(yes_data: str, no_data: str,
                      yes_text: str = "✅ بله", no_text: str = "✏️ ویرایش") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes_text, callback_data=yes_data)],
        [InlineKeyboardButton(no_text, callback_data=no_data)],
    ])


# ==================== منوی اصلی ====================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 تمرین و آزمون", callback_data="menu:practice")],
        [InlineKeyboardButton("📝 امتحان نهایی", callback_data="menu:final_exam")],
        [InlineKeyboardButton("📊 کارنامه من", callback_data="menu:report_card")],
        [InlineKeyboardButton("📚 کتابخانه", callback_data="menu:library")],
        [InlineKeyboardButton("🏆 رقابت و امتیاز", callback_data="menu:leaderboard")],
        [InlineKeyboardButton("👤 پروفایل من", callback_data="menu:profile")],
        [InlineKeyboardButton("📢 کانال اخبار", callback_data="menu:news")],
    ])


def to_main_menu_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")]])


# ==================== صفحه‌بندی عمومی ====================

def pagination_row(prefix: str, page: int, has_prev: bool, has_next: bool) -> list[InlineKeyboardButton]:
    row = []
    if has_prev:
        row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"{prefix}:page:{page - 1}"))
    if has_next:
        row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"{prefix}:page:{page + 1}"))
    return row


# ==================== گزینه‌های تست (۱ تا ۴) ====================

def plain_options_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """کیبورد ۴ گزینه‌ی بدون متن (چون خود گزینه‌ها داخل عکس سوال چاپ شدن)."""
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    rows = [[InlineKeyboardButton(emojis[i], callback_data=f"{prefix}:answer:{i + 1}")]
            for i in range(4)]
    return InlineKeyboardMarkup(rows)


def options_keyboard(prefix: str, option_labels: list[str]) -> InlineKeyboardMarkup:
    """option_labels باید دقیقاً ۴ آیتم باشه (متن گزینه‌ها)."""
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    rows = [[InlineKeyboardButton(f"{emojis[i]} {option_labels[i]}",
                                   callback_data=f"{prefix}:answer:{i + 1}")]
            for i in range(4)]
    return InlineKeyboardMarkup(rows)
