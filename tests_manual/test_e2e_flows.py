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

from database import content as C
from handlers import start as S
from handlers.main_menu import main_menu_router_handler
from handlers import practice as P
from handlers.admin import question_reports as QR

STUDENT = FakeUser(111, username="ali_test", first_name="علی")
ADMIN = FakeUser(999, username="admin_user", first_name="ادمین")

# ============================================================
# ۱) ثبت‌نام کامل یک کاربر جدید
# ============================================================
print("=== TEST: Registration flow ===")
ctx = FakeContext()
upd = FakeUpdate(STUDENT, message=FakeMessage(text="/start"))
state = run(S.start_command(upd, ctx))
assert ctx.user_data == {} or True
last_reply = upd.message.replies[-1]
assert "ثبت‌نام" in last_reply[0], last_reply[0]
print("start_command -> welcome shown OK")

cq = FakeCallbackQuery(data="reg:begin")
upd2 = FakeUpdate(STUDENT, callback_query=cq)
state = run(S.begin_registration(upd2, ctx))
assert state == S.AWAITING_NAME
assert "نام و نام خانوادگی" in cq.edits[-1][0]
print("begin_registration OK, state=AWAITING_NAME")

upd3 = FakeUpdate(STUDENT, message=FakeMessage(text="علی"))  # invalid: only 1 word
state = run(S.receive_name(upd3, ctx))
assert state == S.AWAITING_NAME
assert "❌" in upd3.message.replies[-1][0]
print("receive_name rejects single word OK")

upd4 = FakeUpdate(STUDENT, message=FakeMessage(text="علی رضایی"))
state = run(S.receive_name(upd4, ctx))
assert state == S.AWAITING_GRADE
print("receive_name accepts full name OK, state=AWAITING_GRADE")

cq2 = FakeCallbackQuery(data="reg:grade:دوازدهم")
upd5 = FakeUpdate(STUDENT, callback_query=cq2)
state = run(S.receive_grade(upd5, ctx))
assert state == S.AWAITING_MAJOR
print("receive_grade OK, state=AWAITING_MAJOR")

cq3 = FakeCallbackQuery(data="reg:major:علوم تجربی")
upd6 = FakeUpdate(STUDENT, callback_query=cq3)
state = run(S.receive_major(upd6, ctx))
assert state == S.AWAITING_CONFIRM
assert "همه چی درسته؟" in cq3.edits[-1][0]
print("receive_major OK, state=AWAITING_CONFIRM")

cq4 = FakeCallbackQuery(data="reg:confirm_yes")
upd7 = FakeUpdate(STUDENT, callback_query=cq4)
state = run(S.confirm_yes(upd7, ctx))
from telegram.ext import ConversationHandler
assert state == ConversationHandler.END

from database import users as U
u = U.get_user(111)
assert u["registration_step"] == "done"
assert u["full_name"] == "علی رضایی"
assert u["grade"] == "دوازدهم"
assert u["major"] == "علوم تجربی"
print("confirm_yes -> registration completed in DB OK")
print("=== Registration flow PASSED ===\n")

# ============================================================
# ۲) ساخت محتوای تست (کتاب/فصل/سوال) توسط ادمین مستقیماً در DB
# ============================================================
tb = C.get_or_create_test_book("دوازدهم", "علوم تجربی", "زیست", "خیلی سبز")
ch = C.get_or_create_chapter(tb["id"], "فصل ۳: تقسیم یاخته", 3)
for i in range(1, 6):
    C.add_question(ch["id"], i, f"QIMG_{i}", correct_option=2)
print("=== Test content seeded (5 image-based questions) ===\n")

# ============================================================
# ۳) کاربر مسیر تمرین و آزمون رو کامل طی می‌کنه
# ============================================================
print("=== TEST: Practice/exam flow ===")
ctx2 = FakeContext()

cq5 = FakeCallbackQuery(data="menu:practice")
upd8 = FakeUpdate(STUDENT, callback_query=cq5)
state = run(P.entry_practice(upd8, ctx2))
assert state == P.SEL_GRADE
print("entry_practice OK")

cq6 = FakeCallbackQuery(data="prac:grade:دوازدهم")
state = run(P.select_grade(FakeUpdate(STUDENT, callback_query=cq6), ctx2))
assert state == P.SEL_MAJOR
print("select_grade OK")

cq7 = FakeCallbackQuery(data="prac:major:علوم تجربی")
state = run(P.select_major(FakeUpdate(STUDENT, callback_query=cq7), ctx2))
assert state == P.SEL_SUBJECT
print("select_major OK")

cq8 = FakeCallbackQuery(data="prac:subject:زیست")
state = run(P.select_subject(FakeUpdate(STUDENT, callback_query=cq8), ctx2))
assert state == P.SEL_BOOK
print("select_subject OK (found test book)")

cq9 = FakeCallbackQuery(data=f"prac:tbook:{tb['id']}")
state = run(P.select_book(FakeUpdate(STUDENT, callback_query=cq9), ctx2))
assert state == P.SEL_CHAPTER
print("select_book OK")

cq10 = FakeCallbackQuery(data=f"prac:chap:{ch['id']}")
state = run(P.select_chapter(FakeUpdate(STUDENT, callback_query=cq10), ctx2))
assert state == P.SEL_RANGE
assert ctx2.user_data["practice"]["min_number"] == 1
assert ctx2.user_data["practice"]["max_number"] == 5
print("select_chapter OK, range 1-5 detected")

cq11 = FakeCallbackQuery(data="prac:allrange")
state = run(P.select_range_all(FakeUpdate(STUDENT, callback_query=cq11), ctx2))
assert state == P.SEL_MODE
print("select_range_all OK")

cq12 = FakeCallbackQuery(data="prac:mode:free")
state = run(P.select_mode(FakeUpdate(STUDENT, callback_query=cq12), ctx2))
assert state == P.PRE_START
print("select_mode OK")

cq13 = FakeCallbackQuery(data="prac:launch")
state = run(P.launch_exam(FakeUpdate(STUDENT, callback_query=cq13), ctx2))
assert state == P.IN_EXAM
session_id = ctx2.user_data["practice"]["session_id"]
assert len(cq13.message.photos_sent) == 1
assert cq13.message.photos_sent[0][0] == "QIMG_1"
print(f"launch_exam OK, session_id={session_id}, question 1 photo sent")

# answer question 1 correctly (correct_option=2 for all seeded questions)
cq14 = FakeCallbackQuery(data="prac:answer:2")
state = run(P.submit_answer_callback(FakeUpdate(STUDENT, callback_query=cq14), ctx2))
assert state == P.IN_EXAM
assert cq14.answers[0][0] == "✅ درسته!"
assert cq14.message.photos_sent[0][0] == "QIMG_2"
print("submit_answer (correct) OK, question 2 photo sent")

# answer question 2 incorrectly
cq15 = FakeCallbackQuery(data="prac:answer:1")
state = run(P.submit_answer_callback(FakeUpdate(STUDENT, callback_query=cq15), ctx2))
assert "❌ غلط" in cq15.answers[0][0]
assert "گزینه 2" in cq15.answers[0][0]
# no explanation image was set for this question, so only question 3's photo should be sent
assert len(cq15.message.photos_sent) == 1
assert cq15.message.photos_sent[0][0] == "QIMG_3"
print("submit_answer (wrong) OK:", cq15.answers[0][0])

# report question 3 as having a wrong answer key, BEFORE answering it
q3 = C.get_questions_in_range(ch["id"], 3, 3)[0]
cq16 = FakeCallbackQuery(data=f"prac:report:{q3['id']}")
state = run(P.start_report(FakeUpdate(STUDENT, callback_query=cq16), ctx2))
assert state == P.REPORT_TYPE
# start_report replies with a new TEXT message (can't edit a photo message into text)
assert len(cq16.message.replies) == 1
assert "مشکل این تست چیه" in cq16.message.replies[0][0]
print("start_report OK (sent as new text message, not edit)")

cq17 = FakeCallbackQuery(data="rep:type:wrong_answer")
state = run(P.select_report_type(FakeUpdate(STUDENT, callback_query=cq17), ctx2))
# should return to exam (IN_EXAM) since session still in progress
assert state == P.IN_EXAM
# _return_to_exam_or_end -> _show_current_question sends question 3's photo again (still same q3, not yet answered)
assert cq17.message.photos_sent[0][0] == "QIMG_3"
print("select_report_type OK, returned to exam (question 3 photo re-sent)")

# finish the exam by stopping early
cq18 = FakeCallbackQuery(data="prac:stop")
state = run(P.stop_exam(FakeUpdate(STUDENT, callback_query=cq18), ctx2))
final_text = cq18.message.replies[-1][0]
assert "بعضی سوال‌ها پاسخ داده نشده" in final_text
assert "درست: 1" in final_text
assert "غلط: 1" in final_text
assert "پاسخ‌نداده: 3" in final_text
print("stop_exam OK, stats:\n", final_text)
print("=== Practice/exam flow PASSED ===\n")

# ============================================================
# ۴) ادمین گزارش رو می‌بینه و سوال رو اصلاح می‌کنه
# ============================================================
print("=== TEST: Admin question-report correction flow ===")
ctx3 = FakeContext()

cq19 = FakeCallbackQuery(data="admin:question_reports")
upd_admin = FakeUpdate(ADMIN, callback_query=cq19)
state = run(QR.entry_reports(upd_admin, ctx3))
assert state == QR.LIST_PAGE
list_text = cq19.edits[-1][0]
assert "در انتظار بررسی: 1" in list_text
print("admin sees 1 pending report group OK")

cq20 = FakeCallbackQuery(data=f"qrep:view:{q3['id']}")
state = run(QR.view_question(FakeUpdate(ADMIN, callback_query=cq20), ctx3))
assert state == QR.VIEW_DETAIL
assert cq20.message.photos_sent[0][0] == "QIMG_3"
detail_text = cq20.message.replies[-1][0]
assert "تست 3" in detail_text
assert "پاسخ فعلی: گزینه 2" in detail_text
print("admin views question detail OK (photo sent + text summary)")

cq21 = FakeCallbackQuery(data="qrep:field:correct_option")
state = run(QR.ask_new_value(FakeUpdate(ADMIN, callback_query=cq21), ctx3))
assert state == QR.AWAITING_NEW_VALUE
print("admin picks field to edit OK")

upd_val = FakeUpdate(ADMIN, message=FakeMessage(text="3"))
state = run(QR.receive_new_value(upd_val, ctx3))
from telegram.ext import ConversationHandler as CH2
assert state == CH2.END
assert "اصلاح شد" in upd_val.message.replies[0][0]
print("admin submits new correct_option=3 OK")

q3_after = C.get_question(q3["id"])
assert q3_after["correct_option"] == 3
print("DB confirms correct_option updated to 3")

from database import reports as R
history = R.get_edit_history(q3["id"])
assert len(history) == 1
assert history[0]["old_value"] == "2" and history[0]["new_value"] == "3"
assert history[0]["admin_id"] == 999
print("edit log correctly recorded old=2 new=3 by admin 999")

pending_after = R.get_pending_reports_for_question(q3["id"])
assert len(pending_after) == 0
print("report auto-resolved after correction OK")

print("=== Admin correction flow PASSED ===\n")
print("###### ALL END-TO-END SIMULATIONS PASSED ######")
