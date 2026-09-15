import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")

from tests_manual.fake_telegram import FakeUpdate, FakeContext, FakeUser, FakeCallbackQuery, run

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")

from database.db import init_db
init_db()

from database import users as U
STUDENT = FakeUser(111, username="ali_test")
U.get_or_create_user(111, "ali_test")
U.complete_registration(111)

from handlers import practice as P


def subject_buttons(markup):
    return [b.text for row in markup.inline_keyboard for b in row]


print("=== TEST: grade-specific subjects through select_major handler ===")

for grade, expected_present, expected_absent in [
    ("دهم", [], ["آمار", "گسسته"]),
    ("یازدهم", ["آمار"], ["گسسته"]),
    ("دوازدهم", ["گسسته"], ["آمار"]),
]:
    ctx = FakeContext()
    ctx.user_data["practice"] = {"grade": grade}
    cq = FakeCallbackQuery(data="prac:major:ریاضی و فیزیک")
    state = run(P.select_major(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_SUBJECT
    buttons = subject_buttons(cq.message.edits[-1][1])
    assert "هندسه" in buttons, f"{grade}: هندسه باید همیشه باشه"
    for name in expected_present:
        assert name in buttons, f"{grade}: {name} باید باشه ولی نیست: {buttons}"
    for name in expected_absent:
        assert name not in buttons, f"{grade}: {name} نباید باشه ولی هست: {buttons}"
    print(f"{grade}: {buttons}  OK")

print("###### GRADE-SPECIFIC SUBJECTS (end-to-end) PASSED ######")
