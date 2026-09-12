import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")

from tests_manual.fake_telegram import FakeUpdate, FakeContext, FakeUser, FakeCallbackQuery, run

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")

from database.db import init_db
init_db()

from database import users as U, content as C, exams as E
from handlers import profile as P

STUDENT = FakeUser(111, username="ali_test")
U.get_or_create_user(111, "ali_test")
U.set_full_name(111, "علی رضایی")
U.set_grade(111, "دوازدهم")
U.set_major(111, "علوم تجربی")
U.complete_registration(111)

tb = C.get_or_create_test_book("دوازدهم", "علوم تجربی", "زیست", "خیلی سبز")
ch = C.get_or_create_chapter(tb["id"], "فصل ۱")
q1 = C.add_question(ch["id"], 1, "QIMG_1", correct_option=2, explanation_image_file_id="EXP_1")
q2 = C.add_question(ch["id"], 2, "QIMG_2", correct_option=3)  # no explanation

session = E.create_session(111, ch["id"], 1, 2, "free")
E.submit_answer(session["id"], q1["id"], 1)  # wrong (correct=2)
E.submit_answer(session["id"], q2["id"], 4)  # wrong (correct=3)
E.finish_session(session["id"])

ctx = FakeContext()
cq1 = FakeCallbackQuery(data="mistakes:page:1")
run(P.show_mistakes_page(FakeUpdate(STUDENT, callback_query=cq1), ctx))
text = cq1.edits[-1][0]
assert "تست 1" in text and "تست 2" in text
assert "پاسخ تو: گزینه 1" in text
assert "پاسخ درست: گزینه 2" in text
print("mistakes list text OK (no raw question text leaked):\n", text)

markup = cq1.edits[-1][1]
view_buttons = [b for row in markup.inline_keyboard for b in row if "mistakes:view:" in b.callback_data]
assert len(view_buttons) == 2
print("view-image buttons present for both mistakes OK")

# tap "view image" for question 1 (has explanation)
cq2 = FakeCallbackQuery(data=f"mistakes:view:{q1['id']}")
run(P.view_mistake_image(FakeUpdate(STUDENT, callback_query=cq2), ctx))
assert len(cq2.message.photos_sent) == 2
assert cq2.message.photos_sent[0][0] == "QIMG_1"
assert "گزینه 2" in cq2.message.photos_sent[0][1]
assert cq2.message.photos_sent[1][0] == "EXP_1"
print("view_mistake_image (with explanation) sent both photos OK")

# tap "view image" for question 2 (no explanation)
cq3 = FakeCallbackQuery(data=f"mistakes:view:{q2['id']}")
run(P.view_mistake_image(FakeUpdate(STUDENT, callback_query=cq3), ctx))
assert len(cq3.message.photos_sent) == 1
assert cq3.message.photos_sent[0][0] == "QIMG_2"
print("view_mistake_image (no explanation) sent only question photo OK")

print("###### MISTAKES IMAGE VIEW TESTS PASSED ######")
