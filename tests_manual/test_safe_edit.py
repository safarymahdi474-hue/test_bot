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
U.set_full_name(111, "علی رضایی")
U.set_grade(111, "دوازدهم")
U.set_major(111, "علوم تجربی")
U.complete_registration(111)

from handlers import profile as P
from handlers import leaderboard as L


def click(shared_message, data):
    return FakeCallbackQuery(data=data, message=shared_message)


print("=== TEST: repeated identical render does not crash (profile) ===")
ctx = FakeContext()
cq1 = click(None, "menu:profile")
run(P.show_profile(FakeUpdate(STUDENT, callback_query=cq1), ctx))
msg = cq1.message  # همون پیامی که ادیت شد رو نگه می‌داریم

# دوباره، روی همون پیام، دقیقاً همون صفحه رو رندر کن (بدون هیچ تغییری در داده)
cq2 = click(msg, "menu:profile")
run(P.show_profile(FakeUpdate(STUDENT, callback_query=cq2), ctx))
print("second identical render of profile did NOT raise — OK")

print("=== TEST: repeated identical render does not crash (leaderboard) ===")
ctx2 = FakeContext()
cq3 = click(None, "menu:leaderboard")
run(L.show_weekly(FakeUpdate(STUDENT, callback_query=cq3), ctx2))
msg2 = cq3.message

cq4 = click(msg2, "menu:leaderboard")
run(L.show_weekly(FakeUpdate(STUDENT, callback_query=cq4), ctx2))
print("second identical render of leaderboard did NOT raise — OK")

print("###### SAFE-EDIT REGRESSION TESTS PASSED ######")
