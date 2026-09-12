"""
تست ساختاری: مطمئن می‌شه هیچ ConversationHandler ای بدون راه فرار نمونده.

باگ واقعی که این تست جلوشو می‌گیره:
اگه کاربر وسط یه مکالمه (مثلاً انتخاب پایه/رشته) ول کنه و بعداً دوباره
همون دکمه‌ی منو رو بزنه، چون python-telegram-bot موقع وجود «state» قبلی
دیگه entry_points رو چک نمی‌کنه (فقط state فعلی + fallbacks)، اگه الگوی
همون دکمه‌ی ورودی توی fallbacks هم نباشه، کلیک کاربر کاملاً بی‌صدا نادیده
گرفته می‌شه — یعنی دکمه «باز نمی‌شه».

این تست چک می‌کنه که برای هر ConversationHandler، حداقل یکی از entry_points
(الگوی دکمه‌ی اصلی ورودی) توی fallbacks هم تکرار شده باشه.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.ADMIN_IDS = [999]
config.BOT_TOKEN = "dummy"

from database.db import init_db
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")
init_db()

from handlers.start import build_registration_conversation
from handlers.practice import build_practice_conversation
from handlers.library import build_library_conversation
from handlers.final_exam import build_final_exam_conversation
from handlers.profile import build_feedback_conversation
from handlers.admin.panel import build_user_search_conversation
from handlers.admin.broadcast import build_broadcast_conversation
from handlers.admin.channels import build_add_channel_conversation
from handlers.admin.final_exam_admin import build_add_final_exam_conversation
from handlers.admin.news_settings import build_news_settings_conversation
from handlers.admin.test_management import (
    build_add_book_conversation, build_add_test_conversation, build_excel_upload_conversation,
)
from handlers.admin.question_reports import build_question_reports_conversation
from handlers.admin.reports_and_feedback import (
    build_book_request_conversation, build_feedback_reply_conversation,
)

CONVERSATIONS = [
    ("registration", build_registration_conversation()),
    ("practice", build_practice_conversation()),
    ("library", build_library_conversation()),
    ("final_exam", build_final_exam_conversation()),
    ("feedback", build_feedback_conversation()),
    ("admin_user_search", build_user_search_conversation()),
    ("admin_broadcast", build_broadcast_conversation()),
    ("admin_add_channel", build_add_channel_conversation()),
    ("admin_add_final_exam", build_add_final_exam_conversation()),
    ("admin_news_settings", build_news_settings_conversation()),
    ("admin_add_book", build_add_book_conversation()),
    ("admin_add_test", build_add_test_conversation()),
    ("admin_bulk_upload", build_excel_upload_conversation()),
    ("admin_question_reports", build_question_reports_conversation()),
    ("admin_book_request", build_book_request_conversation()),
    ("admin_feedback_reply", build_feedback_reply_conversation()),
]


def _callback_patterns(handlers):
    """فقط pattern های CallbackQueryHandler رو برمی‌گردونه (CommandHandlerها جدا چک می‌شن)."""
    return [h.pattern for h in handlers if getattr(h, "pattern", None) is not None]


def _commands(handlers):
    return [h.command for h in handlers if hasattr(h, "command")]


failures = []

for name, conv in CONVERSATIONS:
    entry_patterns = _callback_patterns(conv.entry_points)
    fallback_patterns = _callback_patterns(conv.fallbacks)
    entry_commands = _commands(conv.entry_points)
    fallback_commands = _commands(conv.fallbacks)

    # حداقل یکی از الگوهای callback ورودی، دقیقاً هم توی fallbacks باشه
    callback_ok = bool(entry_patterns) and any(p in fallback_patterns for p in entry_patterns)
    # یا حداقل یکی از دستورات ورودی (مثل /start) توی fallbacks هم باشه
    command_ok = bool(entry_commands) and any(c in fallback_commands for c in entry_commands)

    if entry_patterns and not callback_ok and not (entry_commands and command_ok):
        # اگه هیچ‌کدوم از این دو راه برقرار نبود، یعنی این مکالمه اگه یه‌جا گیر
        # کنه، دیگه با کلیک دوباره روی دکمه‌ی خودش باز نمی‌شه.
        failures.append(
            f"{name}: هیچ‌کدوم از entry_points ({entry_patterns + entry_commands}) "
            f"توی fallbacks ({fallback_patterns + fallback_commands}) نیست"
        )
    else:
        print(f"OK  {name}: self-heal fallback موجوده")

if failures:
    print("\n❌ مشکلات پیدا شده:")
    for f in failures:
        print(" -", f)
    raise SystemExit(1)

print("\n###### ALL CONVERSATIONS HAVE SELF-HEAL FALLBACKS ######")

# ============================================================
# بررسی دوم: هیچ دو مکالمه‌ی مستقلی نباید یه callback_data پیشوندنشده
# (مثل یه "back" ثابت) رو مشترک داشته باشن، وگرنه هر کدوم که توی صف
# handlerها زودتر باشه و state باقی‌مونده داشته باشه، کلیک اون یکی رو می‌قاپه.
# ============================================================
print("\n--- بررسی تداخل الگوهای callback بین مکالمه‌های مختلف ---")

pattern_owners: dict[str, list[str]] = {}
for name, conv in CONVERSATIONS:
    all_handlers = list(conv.entry_points) + list(conv.fallbacks)
    for state_handlers in (conv.states or {}).values():
        all_handlers.extend(state_handlers)
    for p in _callback_patterns(all_handlers):
        pattern_owners.setdefault(p, []).append(name)

collisions = {p: owners for p, owners in pattern_owners.items()
              if len(set(owners)) > 1 and p != r"^menu:main$"}
# نکته: "^menu:main$" عمداً تو چند مکالمه تکرار شده. چون همیشه توسط
# main_menu_router_handler (که زودتر از همه ثبت می‌شه) گرفته می‌شه، این
# نسخه‌های داخلی هرگز واقعاً اجرا نمی‌شن؛ فقط برای این نگه داشته شدن که اگه
# یه‌جا ترتیب ثبت handlerها عوض شد، state داخلیِ همون مکالمه هم درست پاک بشه.
# چون خروجی‌شون همیشه یکسانه (نمایش منو + پایان مکالمه)، اشتراکش بی‌خطره.
if collisions:
    print("❌ الگوهای callback مشترک بین چند مکالمه‌ی مستقل:")
    for p, owners in collisions.items():
        print(f"   {p}: {sorted(set(owners))}")
    raise SystemExit(1)

print("###### NO CROSS-CONVERSATION CALLBACK PATTERN COLLISIONS ######")
