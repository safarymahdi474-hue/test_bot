import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")

from tests_manual.fake_telegram import (
    FakeUpdate, FakeContext, FakeUser, FakeMessage, FakeCallbackQuery,
    MessageNotModified, run,
)

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")

from database.db import init_db
init_db()

import config
config.ADMIN_IDS = [999]

STUDENT = FakeUser(111, username="ali_test")
ADMIN = FakeUser(999, username="admin_user")
from telegram.ext import ConversationHandler

from database import users as U
U.get_or_create_user(111, "ali_test")
U.set_full_name(111, "علی رضایی")
U.set_grade(111, "دوازدهم")
U.set_major(111, "علوم تجربی")
U.complete_registration(111)


class FakeDocument:
    def __init__(self, file_id):
        self.file_id = file_id


def click(shared_message, data):
    return FakeCallbackQuery(data=data, message=shared_message)


# ============================================================
# ۱) ادمین با کپشن ۴ بخشی، دو ناشر برای یه درس آپلود می‌کنه
# ============================================================
print("=== TEST: admin uploads library books with publisher caption ===")
import bot as BOT

ctx = FakeContext()

msg1 = FakeMessage(caption="دوازدهم | علوم تجربی | فیزیک | خیلی سبز",
                    document=FakeDocument("FILE_KHEILI_SABZ"))
run(BOT.admin_library_file_upload(FakeUpdate(ADMIN, message=msg1), ctx))
assert "ثبت شد" in msg1.replies[0][0]
print("upload 1 OK:", msg1.replies[0][0])

msg2 = FakeMessage(caption="دوازدهم | علوم تجربی | فیزیک | گاج",
                    document=FakeDocument("FILE_GAJ"))
run(BOT.admin_library_file_upload(FakeUpdate(ADMIN, message=msg2), ctx))
assert "ثبت شد" in msg2.replies[0][0]
print("upload 2 OK:", msg2.replies[0][0])

# فرمت قدیمی (۳ بخشی) باید رد بشه
msg_bad = FakeMessage(caption="دوازدهم | علوم تجربی | فیزیک",
                       document=FakeDocument("FILE_X"))
run(BOT.admin_library_file_upload(FakeUpdate(ADMIN, message=msg_bad), ctx))
assert "❌" in msg_bad.replies[0][0]
print("old 3-field format correctly rejected:", msg_bad.replies[0][0])

# غیرادمین نباید بتونه
NON_ADMIN = FakeUser(222)
msg_non = FakeMessage(caption="دوازدهم | علوم تجربی | فیزیک | خیلی سبز",
                       document=FakeDocument("FILE_Y"))
run(BOT.admin_library_file_upload(FakeUpdate(NON_ADMIN, message=msg_non), ctx))
assert len(msg_non.replies) == 0
print("non-admin silently ignored OK")

from database import content as C
books = C.list_library_books_for_subject("دوازدهم", "علوم تجربی", "فیزیک")
assert len(books) == 2
publishers = sorted(b["publisher"] for b in books)
assert publishers == ["خیلی سبز", "گاج"]
print("DB confirms 2 publishers stored:", publishers)
print("=== Admin upload PASSED ===\n")

# ============================================================
# ۲) دانش‌آموز مسیر کامل رو با یه پیام مشترک طی می‌کنه (رفت + برگشت)
# ============================================================
print("=== TEST: student browses publishers + back navigation (shared message) ===")
from handlers import library as L

ctx2 = FakeContext()
msg = FakeMessage()

try:
    cq = click(msg, "menu:library")
    state = run(L.entry_library(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE

    cq = click(msg, "lib:go")
    state = run(L.go_to_grades(FakeUpdate(STUDENT, callback_query=cq), ctx2))

    cq = click(msg, "lib:grade:دوازدهم")
    state = run(L.select_grade(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_MAJOR

    cq = click(msg, "lib:major:علوم تجربی")
    state = run(L.select_major(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_SUBJECT

    cq = click(msg, "lib:subj:فیزیک")
    state = run(L.select_subject(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_PUBLISHER
    publisher_text = cq.message.edits[-1][0]
    assert "کدوم ناشر" in publisher_text
    print("subject -> publisher list shown OK")

    book_khs = [b for b in books if b["publisher"] == "خیلی سبز"][0]
    cq = click(msg, f"lib:pub:{book_khs['id']}")
    state = run(L.select_publisher(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_PUBLISHER
    assert len(cq.message.documents_sent) == 1
    assert cq.message.documents_sent[0][0] == "FILE_KHEILI_SABZ"
    print("download publisher 1 OK:", cq.message.documents_sent[0])

    # برگرد به لیست ناشرها و ناشر دوم رو دانلود کن
    cq = click(msg, "lib:back_pub")
    state = run(L.back_to_publishers(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_PUBLISHER
    print("back to publisher list OK")

    book_gaj = [b for b in books if b["publisher"] == "گاج"][0]
    cq = click(msg, f"lib:pub:{book_gaj['id']}")
    state = run(L.select_publisher(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert cq.message.documents_sent[-1][0] == "FILE_GAJ"
    print("download publisher 2 OK:", cq.message.documents_sent[-1])

    # حالا کامل برگرد عقب: ناشر -> درس -> رشته -> پایه -> منوی اصلی
    cq = click(msg, "lib:back")
    state = run(L.back_to_subjects(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_SUBJECT
    print("back: publisher -> subject OK")

    cq = click(msg, "lib:back")
    state = run(L.back_to_majors(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_MAJOR
    print("back: subject -> major OK")

    cq = click(msg, "lib:back")
    state = run(L.go_to_grades(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE
    print("back: major -> grade OK")

    cq = click(msg, "lib:back")
    state = run(L.back_to_intro(FakeUpdate(STUDENT, callback_query=cq), ctx2))
    assert state == L.SEL_GRADE
    print("back: grade -> intro OK (بدون خطای MessageNotModified)")

except MessageNotModified as e:
    print(f"❌ FAILED: {e}")
    raise

print("=== Student publisher flow + full back navigation PASSED ===\n")

# ============================================================
# ۳) درسی که هیچ ناشری براش ثبت نشده -> گزارش به مدیر
# ============================================================
print("=== TEST: subject with zero publishers -> report flow ===")
ctx3 = FakeContext()
msg3 = FakeMessage()
cq = click(msg3, "menu:library")
run(L.entry_library(FakeUpdate(STUDENT, callback_query=cq), ctx3))
cq = click(msg3, "lib:go")
run(L.go_to_grades(FakeUpdate(STUDENT, callback_query=cq), ctx3))
cq = click(msg3, "lib:grade:دهم")
run(L.select_grade(FakeUpdate(STUDENT, callback_query=cq), ctx3))
cq = click(msg3, "lib:major:علوم تجربی")
run(L.select_major(FakeUpdate(STUDENT, callback_query=cq), ctx3))
cq = click(msg3, "lib:subj:شیمی")
state = run(L.select_subject(FakeUpdate(STUDENT, callback_query=cq), ctx3))
assert state == L.SEL_SUBJECT  # چون هیچ ناشری نداره، تو همون subject می‌مونه
assert "فایلی برای این درس ثبت نشده" in cq.message.edits[-1][0]
print("empty-publisher message shown OK")

cq = click(msg3, "lib:report")
state = run(L.report_missing_book(FakeUpdate(STUDENT, callback_query=cq), ctx3))
assert state == ConversationHandler.END
print("report_missing_book OK:", cq.message.edits[-1][0])

from database.misc import count_pending_book_requests
assert count_pending_book_requests() == 1
print("DB confirms book_request created")
print("=== Zero-publisher report flow PASSED ===\n")

print("###### ALL LIBRARY PUBLISHER TESTS PASSED ######")
