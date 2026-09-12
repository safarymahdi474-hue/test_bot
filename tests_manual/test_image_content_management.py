import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/home/claude/mock_pkgs")

from tests_manual.fake_telegram import (
    FakeUpdate, FakeContext, FakeUser, FakeMessage, FakeCallbackQuery,
    FakePhotoSize, FakeBot, run,
)

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("bot_data.db"):
    os.remove("bot_data.db")

from database.db import init_db
init_db()

import config
config.ADMIN_IDS = [999]

ADMIN = FakeUser(999, username="admin_user", first_name="ادمین")
from telegram.ext import ConversationHandler


class FakeDocument:
    def __init__(self, file_id, file_name="file.zip"):
        self.file_id = file_id
        self.file_name = file_name
        self._path = None

    async def get_file(self):
        return self

    async def download_to_drive(self, path):
        import shutil
        shutil.copy(self._path, path)


# ============================================================
# ۱) افزودن تست تکی با عکس (بدون توضیح)
# ============================================================
print("=== TEST: Single test add with image (no explanation) ===")
from handlers.admin import test_management as TM

ctx = FakeContext()
cq1 = FakeCallbackQuery(data="admin:add_test")
state = run(TM.start_add_test(FakeUpdate(ADMIN, callback_query=cq1), ctx))
assert state == TM.AWAITING_TEST_STEP

steps = [("دوازدهم", "grade"), ("تجربی", "major"), ("زیست", "subject"),
         ("خیلی سبز", "book"), ("فصل ۱", "chapter"), ("7", "number")]
for text, _ in steps:
    upd = FakeUpdate(ADMIN, message=FakeMessage(text=text))
    state = run(TM.receive_test_step(upd, ctx))
print("all text steps accepted, state =", state)
assert state == TM.AWAITING_QUESTION_IMAGE

upd_img = FakeUpdate(ADMIN, message=FakeMessage(photo=[FakePhotoSize("QIMG_MANUAL_7")]))
state = run(TM.receive_question_image(upd_img, ctx))
assert state == TM.AWAITING_CORRECT_OPTION
print("question image received OK")

upd_correct = FakeUpdate(ADMIN, message=FakeMessage(text="4"))
state = run(TM.receive_correct_option(upd_correct, ctx))
assert state == TM.AWAITING_EXPLANATION_CHOICE
print("correct option received OK")

cq_no = FakeCallbackQuery(data="addtest:exp_no")
state = run(TM.explanation_choice(FakeUpdate(ADMIN, callback_query=cq_no), ctx))
assert state == ConversationHandler.END
assert "اضافه شد" in cq_no.edits[-1][0]
print("explanation skipped, question saved OK:", cq_no.edits[-1][0])

from database import content as C
tb = C.get_or_create_test_book("دوازدهم", "علوم تجربی", "زیست", "خیلی سبز")
ch = C.get_or_create_chapter(tb["id"], "فصل ۱")
q = C.get_questions_in_range(ch["id"], 7, 7)[0]
assert q["question_image_file_id"] == "QIMG_MANUAL_7"
assert q["correct_option"] == 4
assert q["explanation_image_file_id"] is None
print("DB confirms question 7 stored correctly (no explanation)")
print("=== Single add (no explanation) PASSED ===\n")

# ============================================================
# ۲) افزودن تست تکی با عکس + توضیح
# ============================================================
print("=== TEST: Single test add with image + explanation ===")
ctx2 = FakeContext()
cq2 = FakeCallbackQuery(data="admin:add_test")
run(TM.start_add_test(FakeUpdate(ADMIN, callback_query=cq2), ctx2))
for text, _ in steps[:-1]:
    run(TM.receive_test_step(FakeUpdate(ADMIN, message=FakeMessage(text=text)), ctx2))
run(TM.receive_test_step(FakeUpdate(ADMIN, message=FakeMessage(text="8")), ctx2))
run(TM.receive_question_image(FakeUpdate(ADMIN, message=FakeMessage(photo=[FakePhotoSize("QIMG_MANUAL_8")])), ctx2))
run(TM.receive_correct_option(FakeUpdate(ADMIN, message=FakeMessage(text="1")), ctx2))

cq_yes = FakeCallbackQuery(data="addtest:exp_yes")
state = run(TM.explanation_choice(FakeUpdate(ADMIN, callback_query=cq_yes), ctx2))
assert state == TM.AWAITING_EXPLANATION_IMAGE
print("explanation=yes -> asked for image OK")

upd_exp_img = FakeUpdate(ADMIN, message=FakeMessage(photo=[FakePhotoSize("EXP_IMG_8")]))
state = run(TM.receive_explanation_image(upd_exp_img, ctx2))
assert state == ConversationHandler.END
assert "اضافه شد" in upd_exp_img.message.replies[0][0]
print("explanation image saved OK")

q8 = C.get_questions_in_range(ch["id"], 8, 8)[0]
assert q8["question_image_file_id"] == "QIMG_MANUAL_8"
assert q8["explanation_image_file_id"] == "EXP_IMG_8"
assert q8["correct_option"] == 1
print("DB confirms question 8 stored correctly (with explanation)")
print("=== Single add (with explanation) PASSED ===\n")

# ============================================================
# ۳) آپلود دسته‌جمعی (ZIP)
# ============================================================
print("=== TEST: Bulk ZIP upload ===")
import tempfile, zipfile, openpyxl

work_dir = tempfile.mkdtemp(prefix="bulk_test_")

# create manifest.xlsx
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["پایه", "رشته", "درس", "کتاب", "فصل", "شماره", "پاسخ", "فایل_سوال", "فایل_توضیح"])
ws.append(["دوازدهم", "تجربی", "شیمی", "گاج", "فصل ۲", 1, 2, "q1.jpg", "exp1.jpg"])
ws.append(["دوازدهم", "تجربی", "شیمی", "گاج", "فصل ۲", 2, 3, "q2.jpg", ""])
ws.append(["یازدهم", "بدرشته", "فیزیک", "میکرو", "فصل ۱", 1, 1, "q3.jpg", ""])  # invalid major
ws.append(["دوازدهم", "تجربی", "شیمی", "گاج", "فصل ۲", 4, 2, "missing.jpg", ""])  # missing image file
manifest_path = os.path.join(work_dir, "manifest.xlsx")
wb.save(manifest_path)

# create fake image files
for name in ["q1.jpg", "q2.jpg", "exp1.jpg"]:
    with open(os.path.join(work_dir, name), "wb") as f:
        f.write(b"FAKEJPEGDATA_" + name.encode())

zip_path = os.path.join(work_dir, "bundle.zip")
with zipfile.ZipFile(zip_path, "w") as zf:
    zf.write(manifest_path, "manifest.xlsx")
    for name in ["q1.jpg", "q2.jpg", "exp1.jpg"]:
        zf.write(os.path.join(work_dir, name), name)

extract_dir = os.path.join(work_dir, "extracted")
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(extract_dir)

fake_bot = FakeBot()
added, errors = run(TM._import_bulk_zip(extract_dir, fake_bot, admin_id=999))
print("added:", added)
print("errors:", errors)
assert added == 2, added
assert len(errors) == 2, errors
assert any("بدرشته" in e or "نامعتبر" in e for e in errors)
assert any("missing.jpg" in e for e in errors)
print("bulk import counts OK (2 added, 2 errors)")

tb2 = C.get_or_create_test_book("دوازدهم", "علوم تجربی", "شیمی", "گاج")
ch2 = C.get_or_create_chapter(tb2["id"], "فصل ۲")
bq1 = C.get_questions_in_range(ch2["id"], 1, 1)[0]
bq2 = C.get_questions_in_range(ch2["id"], 2, 2)[0]
assert bq1["correct_option"] == 2
assert bq1["explanation_image_file_id"] is not None
assert "q1.jpg" in bq1["question_image_file_id"]
assert bq2["explanation_image_file_id"] is None
assert "q2.jpg" in bq2["question_image_file_id"]
print("DB confirms bulk-imported questions have correct data + real 'uploaded' file_ids")
print("sent photos to fake bot:", fake_bot.sent_photos)

print("=== Bulk ZIP upload PASSED ===\n")
print("###### ALL IMAGE-CONTENT-MANAGEMENT SIMULATIONS PASSED ######")
