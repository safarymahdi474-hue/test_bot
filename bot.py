"""
نقطه‌ی ورود اصلی ربات. تمام handlerها اینجا به هم وصل می‌شن.
اجرا: python bot.py
نیازمند متغیرهای محیطی BOT_TOKEN و ADMIN_IDS (توی config.py خونده می‌شن).
"""
import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from config import BOT_TOKEN, ADMIN_IDS
from database.db import init_db
from database.users import reset_weekly_points
from database.content import upsert_library_book_file

from handlers.start import build_registration_conversation, join_check_handler
from handlers.main_menu import main_menu_router_handler
from handlers.practice import build_practice_conversation
from handlers.library import build_library_conversation
from handlers.final_exam import build_final_exam_conversation
from handlers.news import news_handler
from handlers.leaderboard import leaderboard_handlers
from handlers.profile import (
    profile_handlers, build_feedback_conversation,
)
from handlers.admin.panel import admin_panel_handlers, build_user_search_conversation
from handlers.admin.broadcast import build_broadcast_conversation
from handlers.admin.channels import channel_handlers, build_add_channel_conversation
from handlers.admin.library_admin import library_admin_handlers
from handlers.admin.final_exam_admin import final_exam_admin_handlers, build_add_final_exam_conversation
from handlers.admin.news_settings import build_news_settings_conversation
from handlers.admin.test_management import (
    test_management_handlers, build_add_book_conversation,
    build_add_test_conversation, build_excel_upload_conversation,
)
from handlers.admin.question_reports import build_question_reports_conversation
from handlers.admin.reports_and_feedback import (
    reports_feedback_entry_handlers, build_book_request_conversation,
    build_feedback_reply_conversation,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ==================== آپلود فایل کتابخانه توسط ادمین ====================
# ادمین یک فایل (PDF/...) رو با کپشنی به فرمت «پایه | رشته | درس» فوروارد/ارسال می‌کنه.

async def admin_library_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return  # کاربر عادی؛ این پیام مربوط به هیچ handler دیگه‌ای هم نیست، نادیده گرفته می‌شه

    caption = (update.message.caption or "").strip()
    if not caption or "|" not in caption:
        return  # فایلی که کپشن استاندارد نداره، مربوط به این قابلیت نیست

    parts = [p.strip() for p in caption.split("|")]
    if len(parts) != 3:
        await update.message.reply_text(
            "❌ فرمت کپشن باید «پایه | رشته | درس» باشه. مثال:\nدهم | علوم تجربی | ریاضی"
        )
        return

    from config import GRADES, MAJORS
    grade, major, subject = parts
    if grade not in GRADES or major not in MAJORS:
        await update.message.reply_text(
            f"❌ پایه یا رشته نامعتبره.\nپایه‌ها: {', '.join(GRADES)}\nرشته‌ها: {', '.join(MAJORS)}"
        )
        return

    file_id = update.message.document.file_id
    upsert_library_book_file(grade, major, subject, file_id)
    await update.message.reply_text(f"✅ فایل کتابخانه ثبت شد: {subject} {grade} ({major})")


# ==================== زمان‌بندی ریست هفتگی لیدربورد ====================

async def weekly_leaderboard_reset_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    reset_weekly_points()
    logger.info("امتیاز هفتگی همه‌ی کاربران ریست شد.")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "متغیر محیطی BOT_TOKEN تنظیم نشده. قبل از اجرا: export BOT_TOKEN=... را وارد کن."
        )

    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # ---------- ثبت‌نام و جوین اجباری ----------
    application.add_handler(build_registration_conversation())
    application.add_handler(join_check_handler)

    # ---------- منوی اصلی ----------
    application.add_handler(main_menu_router_handler)

    # ---------- تمرین و آزمون ----------
    application.add_handler(build_practice_conversation())

    # ---------- کتابخانه ----------
    application.add_handler(build_library_conversation())

    # ---------- امتحان نهایی ----------
    application.add_handler(build_final_exam_conversation())

    # ---------- کانال اخبار ----------
    application.add_handler(news_handler)

    # ---------- رقابت و امتیاز ----------
    for h in leaderboard_handlers:
        application.add_handler(h)

    # ---------- پروفایل، کارنامه، پشتیبانی، انتقاد/پیشنهاد ----------
    for h in profile_handlers:
        application.add_handler(h)
    application.add_handler(build_feedback_conversation())

    # ---------- پنل مدیریت ----------
    for h in admin_panel_handlers:
        application.add_handler(h)
    application.add_handler(build_user_search_conversation())
    application.add_handler(build_broadcast_conversation())

    for h in channel_handlers:
        application.add_handler(h)
    application.add_handler(build_add_channel_conversation())

    for h in library_admin_handlers:
        application.add_handler(h)

    for h in final_exam_admin_handlers:
        application.add_handler(h)
    application.add_handler(build_add_final_exam_conversation())

    application.add_handler(build_news_settings_conversation())

    for h in test_management_handlers:
        application.add_handler(h)
    application.add_handler(build_add_book_conversation())
    application.add_handler(build_add_test_conversation())
    # این باید قبل از هندلر عمومی «آپلود فایل کتابخانه» ثبت بشه، وگرنه وقتی
    # ادمین وسط مکالمه‌ی آپلود اکسل یه فایل می‌فرسته، هندلر عمومی زودتر
    # قاپش می‌زنه و ConversationHandler هیچ‌وقت فایل اکسل رو نمی‌بینه.
    application.add_handler(build_excel_upload_conversation())
    application.add_handler(build_question_reports_conversation())

    # هندلر عمومی «آپلود فایل کتابخانه» — باید بعد از مکالمه‌ی آپلود اکسل ثبت بشه
    application.add_handler(
        MessageHandler(filters.Document.ALL, admin_library_file_upload)
    )

    for h in reports_feedback_entry_handlers:
        application.add_handler(h)
    application.add_handler(build_book_request_conversation())
    application.add_handler(build_feedback_reply_conversation())

    # ---------- کار زمان‌بندی‌شده: ریست امتیاز هفتگی هر جمعه ساعت ۲۳:۵۹ ----------
    if application.job_queue is not None:
        from datetime import time as dt_time
        application.job_queue.run_daily(
            weekly_leaderboard_reset_job,
            time=dt_time(hour=23, minute=59),
            days=(4,),  # ۰=دوشنبه ... در APScheduler/PTB: 4 = جمعه (چون شمارش از دوشنبه=0 شروع می‌شه)
            name="weekly_leaderboard_reset",
        )

    logger.info("ربات در حال اجراست...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
