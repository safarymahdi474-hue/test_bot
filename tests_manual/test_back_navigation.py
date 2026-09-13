"""
تست ناوبری جلو/عقب با یه پیام مشترک (دقیقاً مثل تلگرام واقعی که پیام قبلی
مدام edit می‌شه، نه اینکه هر کلیک یه پیام جدید باشه).
این تست دقیقاً همون باگی رو می‌گیره که باعث شد دکمه‌ی «بازگشت» تو صفحه‌ی
«پایه‌ت رو انتخاب کن» بی‌اثر باشه: وقتی متن+کیبورد جدید با قبلی یکی باشه،
تلگرام edit رو رد می‌کنه (MessageNotModified).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")

from tests_manual.fake_telegram import (
    FakeUpdate, FakeContext, FakeUser, FakeMessage, FakeCallbackQuery,
    FakePhotoSize, MessageNotModified, run,
)

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")

from database.db import init_db
init_db()

from database import users as U, content as C, final_exams as FE
import config
config.ADMIN_IDS = [999]

STUDENT = FakeUser(111, username="ali_test")
U.get_or_create_user(111, "ali_test")
U.set_full_name(111, "علی رضایی")
U.set_grade(111, "دوازدهم")
U.set_major(111, "علوم تجربی")
U.complete_registration(111)

# محتوای لازم برای این‌که پیشروی واقعی (نه فقط پیام خطا) اتفاق بیفته
tb = C.get_or_create_test_book("دوازدهم", "علوم تجربی", "زیست", "خیلی سبز")
ch = C.get_or_create_chapter(tb["id"], "فصل ۱")
C.add_question(ch["id"], 1, "QIMG_1", correct_option=1)
FE.add_final_exam("دوازدهم", "علوم تجربی", "زیست", "نمونه", "FINAL_FILE_1")


def click(shared_message, data, ctx):
    """یه کلیک جدید روی همون پیام مشترک قبلی شبیه‌سازی می‌کنه."""
    cq = FakeCallbackQuery(data=data, message=shared_message)
    return cq


# ============================================================
# ۱) تمرین و آزمون: جلو تا آخر، بعد کاملاً برگرد عقب
# ============================================================
print("=== TEST: practice.py forward + full back navigation (shared message) ===")
from handlers import practice as P

ctx = FakeContext()
msg = FakeMessage()

try:
    cq = click(msg, "menu:practice", ctx)
    state = run(P.entry_practice(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_GRADE

    cq = click(msg, "prac:grade:دوازدهم", ctx)
    state = run(P.select_grade(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_MAJOR

    cq = click(msg, "prac:major:علوم تجربی", ctx)
    state = run(P.select_major(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_SUBJECT

    cq = click(msg, "prac:subject:زیست", ctx)
    state = run(P.select_subject(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_BOOK

    cq = click(msg, f"prac:tbook:{tb['id']}", ctx)
    state = run(P.select_book(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_CHAPTER

    cq = click(msg, f"prac:chap:{ch['id']}", ctx)
    state = run(P.select_chapter(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_RANGE
    print("forward path OK, reached SEL_RANGE")

    # حالا کاملاً برگرد عقب، قدم به قدم، روی همون پیام
    cq = click(msg, "prac:back", ctx)
    state = run(P.back_to_chapter(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_CHAPTER
    print("back: range -> chapter OK")

    cq = click(msg, "prac:back", ctx)
    state = run(P.back_to_book(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_BOOK
    print("back: chapter -> book OK")

    cq = click(msg, "prac:back", ctx)
    state = run(P.back_to_subject(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_SUBJECT
    print("back: book -> subject OK")

    cq = click(msg, "prac:back", ctx)
    state = run(P.back_to_major(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_MAJOR
    print("back: subject -> major OK")

    cq = click(msg, "prac:back", ctx)
    state = run(P.back_to_grade(FakeUpdate(STUDENT, callback_query=cq), ctx))
    assert state == P.SEL_GRADE
    print("back: major -> grade OK")

    # این همون کلیکیه که قبلاً می‌شکست: از صفحه‌ی «پایه‌ت رو انتخاب کن»
    # دوباره روی «بازگشت» بزنه -> باید بره منوی اصلی، نه اینکه دوباره
    # همون صفحه رو نشون بده (که خطای MessageNotModified می‌داد)
    cq = click(msg, "prac:back", ctx)
    state = run(P.back_to_main_menu(FakeUpdate(STUDENT, callback_query=cq), ctx))
    from telegram.ext import ConversationHandler
    assert state == ConversationHandler.END
    print("back: grade -> main menu OK (این دقیقاً همون دکمه‌ای بود که قبلاً کار نمی‌کرد)")

except MessageNotModified as e:
    print(f"❌ FAILED: {e}")
    raise

print("=== practice.py back navigation PASSED (no MessageNotModified anywhere) ===\n")

# ============================================================
# ۲) کتابخانه: مسیر رفت‌وبرگشت
# ============================================================
print("=== TEST: library.py forward + back navigation (shared message) ===")
from handlers import library as L

ctx2 = FakeContext()
msg2 = FakeMessage()

try:
    cq = click(msg2, "menu:library", ctx2)
    state = run(L.entry_library(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE

    cq = click(msg2, "lib:go", ctx2)
    state = run(L.go_to_grades(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE
    print("intro -> grades OK")

    # این همون back بود که قبلاً می‌شکست (صفحه‌ی پایه -> پایه)
    cq = click(msg2, "lib:back", ctx2)
    state = run(L.back_to_intro(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE
    print("back: grades -> intro OK (بدون خطا)")

    cq = click(msg2, "lib:go", ctx2)
    state = run(L.go_to_grades(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE

    cq = click(msg2, "lib:grade:دوازدهم", ctx2)
    state = run(L.select_grade(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_MAJOR

    cq = click(msg2, "lib:major:علوم تجربی", ctx2)
    state = run(L.select_major(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_SUBJECT
    print("grade -> major -> subject OK")

    cq = click(msg2, "lib:back", ctx2)
    state = run(L.back_to_majors(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_MAJOR
    print("back: subject -> major OK")

    cq = click(msg2, "lib:back", ctx2)
    state = run(L.go_to_grades(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE
    print("back: major -> grades OK")

except MessageNotModified as e:
    print(f"❌ FAILED: {e}")
    raise

print("=== library.py back navigation PASSED ===\n")

# ============================================================
# ۳) امتحان نهایی: مسیر رفت‌وبرگشت
# ============================================================
print("=== TEST: final_exam.py forward + back navigation (shared message) ===")
from handlers import final_exam as FX

ctx3 = FakeContext()
msg3 = FakeMessage()

try:
    cq = click(msg3, "menu:final_exam", ctx3)
    state = run(FX.entry_final_exam(FakeUpdate(STUDENT, callback_query=cq), ctx3))
    assert state == FX.SEL_GRADE

    cq = click(msg3, "fexam:grade:دوازدهم", ctx3)
    state = run(FX.select_grade(FakeUpdate(STUDENT, callback_query=cq), ctx3))
    assert state == FX.SEL_MAJOR

    cq = click(msg3, "fexam:major:علوم تجربی", ctx3)
    state = run(FX.select_major(FakeUpdate(STUDENT, callback_query=cq), ctx3))
    assert state == FX.SEL_SUBJECT
    print("grade -> major -> subject OK")

    cq = click(msg3, "fexam:back", ctx3)
    state = run(FX.back_to_major(FakeUpdate(STUDENT, callback_query=cq), ctx3))
    assert state == FX.SEL_MAJOR
    print("back: subject -> major OK")

    cq = click(msg3, "fexam:back", ctx3)
    state = run(FX.exit_to_main_menu(FakeUpdate(STUDENT, callback_query=cq), ctx3))
    from telegram.ext import ConversationHandler
    assert state == ConversationHandler.END
    print("back: major -> grade OK")

    # و از صفحه‌ی پایه، بازگشت باید بره منوی اصلی (بدون خطا)
    cq2 = click(msg3, "menu:final_exam", ctx3)
    run(FX.entry_final_exam(FakeUpdate(STUDENT, callback_query=cq2), ctx3))
    cq3_ = click(msg3, "fexam:back", ctx3)
    state = run(FX.exit_to_main_menu(FakeUpdate(STUDENT, callback_query=cq3_), ctx3))
    assert state == ConversationHandler.END
    print("back: grade -> main menu OK")

except MessageNotModified as e:
    print(f"❌ FAILED: {e}")
    raise

print("=== final_exam.py back navigation PASSED ===\n")
print("###### ALL BACK-NAVIGATION SIMULATIONS PASSED (NO MESSAGE-NOT-MODIFIED ERRORS) ######")
