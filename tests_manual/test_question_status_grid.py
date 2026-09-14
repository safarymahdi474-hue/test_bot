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
from handlers import practice as P

STUDENT = FakeUser(111, username="ali_test")
U.get_or_create_user(111, "ali_test")
U.set_full_name(111, "علی رضایی")
U.set_grade(111, "دوازدهم")
U.set_major(111, "علوم تجربی")
U.complete_registration(111)

tb = C.get_or_create_test_book("دوازدهم", "علوم تجربی", "زیست", "خیلی سبز")
ch = C.get_or_create_chapter(tb["id"], "فصل ۱")
for i in range(1, 6):
    C.add_question(ch["id"], i, f"QIMG_{i}", correct_option=2)

# کاربر یه بار قبلاً تست ۱ (درست) و ۲ (غلط) رو زده؛ ۳،۴،۵ رو نزده
session = E.create_session(111, ch["id"], 1, 5, "free")
qs = E.get_session_questions_ordered(session["id"])
E.submit_answer(session["id"], qs[0]["id"], 2)  # correct
E.submit_answer(session["id"], qs[1]["id"], 1)  # wrong

# ============================================================
# صفحه‌ی انتخاب محدوده باید تیک/ضربدر رو نشون بده
# ============================================================
print("=== TEST: question status grid on range screen ===")
ctx = FakeContext()
ud = ctx.user_data.setdefault("practice", {})
ud["chapter_id"] = ch["id"]
ud["min_number"], ud["max_number"] = 1, 5

cq = FakeCallbackQuery(data="prac:chap:x")
state = run(P._render_range_screen(FakeUpdate(STUDENT, callback_query=cq), ctx))
assert state == P.SEL_RANGE
text = cq.message.edits[-1][0]
print(text)

assert "1✅" in text
assert "2❌" in text
# سوالات نزده نباید هیچ علامتی داشته باشن (نه ✅ نه ❌ بعد از عدد)
assert "3✅" not in text and "3❌" not in text
assert "4✅" not in text and "4❌" not in text
assert "5✅" not in text and "5❌" not in text
# ولی خود شماره‌ها باید باشن
import re
assert re.search(r"\b3\b", text)
assert re.search(r"\b4\b", text)
assert re.search(r"\b5\b", text)
print("grid correctly shows ✅ for q1, ❌ for q2, nothing for q3/4/5")

# ============================================================
# تست تابع فرمت‌کننده به‌تنهایی، برای محدوده‌ی بزرگ‌تر (چیدمان ۱۰تایی)
# ============================================================
status = {1: True, 5: False, 12: True}
grid = P._format_question_grid(1, 15, status)
lines = grid.split("\n")
assert len(lines) == 2  # ۱۰ تا در خط اول، ۵ تا در خط دوم
assert "1✅" in lines[0]
assert "5❌" in lines[0]
assert "12✅" in lines[1]
print("10-per-row wrapping OK:\n" + grid)

print("###### QUESTION STATUS GRID TESTS PASSED ######")
