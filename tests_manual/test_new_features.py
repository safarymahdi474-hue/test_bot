import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")

from tests_manual.fake_telegram import FakeUpdate, FakeContext, FakeUser, FakeMessage, FakeCallbackQuery, run

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")

from database.db import init_db
init_db()

import config
config.ADMIN_IDS = [999]

STUDENT = FakeUser(111, username="ali_test", first_name="علی")
ADMIN = FakeUser(999, username="admin_user", first_name="ادمین")

from telegram.ext import ConversationHandler


class FakeDocument:
    def __init__(self, file_id):
        self.file_id = file_id


# ============================================================
# ۱) ادمین یک امتحان نهایی آپلود می‌کنه
# ============================================================
print("=== TEST: Admin uploads a final exam ===")
from handlers.admin import final_exam_admin as FEA

ctx = FakeContext()
cq1 = FakeCallbackQuery(data="admin:add_fexam")
state = run(FEA.start_add(FakeUpdate(ADMIN, callback_query=cq1), ctx))
assert state == FEA.SEL_GRADE
print("start_add OK")

cq2 = FakeCallbackQuery(data="fexadd:grade:دوازدهم")
state = run(FEA.select_grade(FakeUpdate(ADMIN, callback_query=cq2), ctx))
assert state == FEA.SEL_MAJOR

cq3 = FakeCallbackQuery(data="fexadd:major:علوم تجربی")
state = run(FEA.select_major(FakeUpdate(ADMIN, callback_query=cq3), ctx))
assert state == FEA.SEL_SUBJECT

cq4 = FakeCallbackQuery(data="fexadd:subject:زیست")
state = run(FEA.select_subject(FakeUpdate(ADMIN, callback_query=cq4), ctx))
assert state == FEA.AWAITING_TITLE
print("grade/major/subject selection OK")

upd_title = FakeUpdate(ADMIN, message=FakeMessage(text="نوبت دوم - خرداد ۱۴۰۲"))
state = run(FEA.receive_title(upd_title, ctx))
assert state == FEA.AWAITING_FILE
print("receive_title OK")

# try sending text instead of file -> should be rejected and stay in AWAITING_FILE
upd_bad = FakeUpdate(ADMIN, message=FakeMessage(text="این یه فایل نیست", document=None))
state = run(FEA.receive_file(upd_bad, ctx))
assert state == FEA.AWAITING_FILE
print("receive_file rejects non-file OK")

upd_file = FakeUpdate(ADMIN, message=FakeMessage(document=FakeDocument("FINAL_EXAM_FILE_123")))
state = run(FEA.receive_file(upd_file, ctx))
assert state == ConversationHandler.END
assert "اضافه شد" in upd_file.message.replies[0][0]
print("receive_file stores exam OK:", upd_file.message.replies[0][0])

from database import final_exams as FE
exams = FE.list_final_exams("دوازدهم", "علوم تجربی", "زیست")
assert len(exams) == 1
assert exams[0]["file_id"] == "FINAL_EXAM_FILE_123"
assert exams[0]["title"] == "نوبت دوم - خرداد ۱۴۰۲"
print("DB confirms final exam stored correctly")
print("=== Admin upload PASSED ===\n")

# ============================================================
# ۲) دانش‌آموز امتحان نهایی رو پیدا و دانلود می‌کنه
# ============================================================
print("=== TEST: Student browses and downloads final exam ===")
from handlers import final_exam as FX

ctx2 = FakeContext()
cq5 = FakeCallbackQuery(data="menu:final_exam")
state = run(FX.entry_final_exam(FakeUpdate(STUDENT, callback_query=cq5), ctx2))
assert state == FX.SEL_GRADE

cq6 = FakeCallbackQuery(data="fexam:grade:دوازدهم")
state = run(FX.select_grade(FakeUpdate(STUDENT, callback_query=cq6), ctx2))
assert state == FX.SEL_MAJOR

cq7 = FakeCallbackQuery(data="fexam:major:علوم تجربی")
state = run(FX.select_major(FakeUpdate(STUDENT, callback_query=cq7), ctx2))
assert state == FX.SEL_SUBJECT

cq8 = FakeCallbackQuery(data="fexam:subject:زیست")
state = run(FX.select_subject(FakeUpdate(STUDENT, callback_query=cq8), ctx2))
assert state == FX.SEL_SUBJECT
list_text = cq8.edits[-1][0]
assert "امتحان‌های نهایی زیست دوازدهم" in list_text
print("student sees exam list OK:", list_text)

exam_id = exams[0]["id"]
cq9 = FakeCallbackQuery(data=f"fexam:dl:{exam_id}")
upd9 = FakeUpdate(STUDENT, callback_query=cq9)
state = run(FX.download_exam(upd9, ctx2))
assert state == FX.SEL_SUBJECT
assert len(cq9.message.documents_sent) == 1
assert cq9.message.documents_sent[0][0] == "FINAL_EXAM_FILE_123"
print("download_exam OK, file sent:", cq9.message.documents_sent[0])

# non-existent subject with no exams should show "not uploaded yet"
cq10 = FakeCallbackQuery(data="fexam:subject:فیزیک")
state = run(FX.select_subject(FakeUpdate(STUDENT, callback_query=cq10), ctx2))
assert "هنوز امتحان نهایی‌ای" in cq10.edits[-1][0]
print("empty-subject message OK")
print("=== Student browse/download PASSED ===\n")

# ============================================================
# ۳) کانال اخبار
# ============================================================
print("=== TEST: News channel ===")
from handlers import news as NEWS
from database.settings import set_news_channel

ctx3 = FakeContext()
cq11 = FakeCallbackQuery(data="menu:news")
run(NEWS.show_news_channel(FakeUpdate(STUDENT, callback_query=cq11), ctx3))
assert "هنوز کانال اخباری تنظیم نشده" in cq11.edits[-1][0]
print("news channel not-configured message OK")

set_news_channel("کانال اخبار ما", "https://t.me/our_news")
cq12 = FakeCallbackQuery(data="menu:news")
run(NEWS.show_news_channel(FakeUpdate(STUDENT, callback_query=cq12), ctx3))
text, markup = cq12.edits[-1]
assert "کانال اخبار ما" in markup.inline_keyboard[0][0].text
assert markup.inline_keyboard[0][0].url == "https://t.me/our_news"
print("news channel configured message OK:", markup.inline_keyboard[0][0].text)
print("=== News channel PASSED ===\n")

# ============================================================
# ۴) تنظیم کانال اخبار توسط ادمین (تست فرمت ورودی)
# ============================================================
print("=== TEST: Admin sets news channel via conversation ===")
from handlers.admin import news_settings as NS

ctx4 = FakeContext()
cq13 = FakeCallbackQuery(data="admin:news_settings")
state = run(NS.entry_news_settings(FakeUpdate(ADMIN, callback_query=cq13), ctx4))
assert state == NS.AWAITING_INPUT

# bad format (no pipe)
upd_bad2 = FakeUpdate(ADMIN, message=FakeMessage(text="یه چیز بی‌فرمت"))
state = run(NS.receive_input(upd_bad2, ctx4))
assert state == NS.AWAITING_INPUT
assert "❌" in upd_bad2.message.replies[0][0]
print("bad format rejected OK")

# bad link (doesn't start with http)
upd_bad3 = FakeUpdate(ADMIN, message=FakeMessage(text="عنوان | ftp://bad"))
state = run(NS.receive_input(upd_bad3, ctx4))
assert state == NS.AWAITING_INPUT
print("bad link rejected OK")

upd_good = FakeUpdate(ADMIN, message=FakeMessage(text="کانال رسمی | https://t.me/official"))
state = run(NS.receive_input(upd_good, ctx4))
assert state == ConversationHandler.END
print("good input accepted OK:", upd_good.message.replies[0][0])

from database.settings import get_news_channel
nc = get_news_channel()
assert nc == {"title": "کانال رسمی", "link": "https://t.me/official"}
print("DB confirms news channel updated")

# non-admin should be rejected
NON_ADMIN = FakeUser(222, username="regular")
ctx5 = FakeContext()
cq14 = FakeCallbackQuery(data="admin:news_settings")
state = run(NS.entry_news_settings(FakeUpdate(NON_ADMIN, callback_query=cq14), ctx5))
assert state == ConversationHandler.END
assert cq14.answers[-1][1] == True  # show_alert
print("non-admin correctly rejected")
print("=== Admin news settings PASSED ===\n")

print("###### ALL NEW-FEATURE SIMULATIONS PASSED ######")
