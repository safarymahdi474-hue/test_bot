"""
📝 مدیریت تست‌ها — افزودن کتاب تست، افزودن تست تکی (با عکس)، آپلود دسته‌جمعی (ZIP)، لیست.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import ADMIN_IDS, GRADES, MAJORS
from database import content as C

(AWAITING_BOOK_LINE, AWAITING_TEST_STEP, AWAITING_QUESTION_IMAGE,
 AWAITING_CORRECT_OPTION, AWAITING_EXPLANATION_CHOICE, AWAITING_EXPLANATION_IMAGE,
 AWAITING_BULK_ZIP) = range(7)

# مراحل متنی قبل از عکس (پایه/رشته/درس/کتاب/فصل/شماره)
TEST_STEP_FIELDS = [
    ("grade", "پایه", GRADES),
    ("major", "رشته", MAJORS),
    ("subject", "درس", None),
    ("book", "کتاب (نام ناشر)", None),
    ("chapter", "فصل", None),
    ("number", "شماره تست", None),
]


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _extract_image_file_id(message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        return message.document.file_id
    return None


async def entry_test_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return

    total_questions = C.count_total_questions()
    books = C.list_all_test_books_summary()
    lines = [
        "📝 مدیریت تست‌ها", "━━━━━━━━━━━━━━━",
        f"📊 تعداد تست‌ها: {total_questions}", "",
        "📚 کتاب‌های ثبت‌شده:",
    ]
    for b in books[:10]:
        lines.append(f"• {b['name']} — {b['subject']} {b['grade']} ({b['question_count']} تست)")
    if not books:
        lines.append("هنوز کتابی ثبت نشده.")

    rows = [
        [InlineKeyboardButton("➕ افزودن کتاب تست", callback_data="admin:add_book")],
        [InlineKeyboardButton("➕ افزودن تست (با عکس)", callback_data="admin:add_test")],
        [InlineKeyboardButton("📤 آپلود دسته‌جمعی (ZIP)", callback_data="admin:upload_bulk")],
        [InlineKeyboardButton("⚠️ گزارش‌های اشکال تست", callback_data="admin:question_reports")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel")],
    ]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


# ==================== افزودن کتاب تست ====================

async def ask_book_line(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END
    await query.edit_message_text(
        "➕ افزودن کتاب تست\n\n"
        "فرمت ارسال کن:\nپایه | رشته | درس | نام کتاب\n\n"
        "مثال:\nدوازدهم | تجربی | زیست | خیلی سبز"
    )
    return AWAITING_BOOK_LINE


async def receive_book_line(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parts = [p.strip() for p in (update.message.text or "").split("|")]
    if len(parts) != 4 or not all(parts):
        await update.message.reply_text(
            "❌ فرمت اشتباهه. دوباره بفرست:\nپایه | رشته | درس | نام کتاب"
        )
        return AWAITING_BOOK_LINE

    grade, major_short, subject, name = parts
    major_full = next((m for m in MAJORS if major_short in m), None)
    if grade not in GRADES or major_full is None:
        await update.message.reply_text(
            f"❌ پایه یا رشته نامعتبره.\nپایه‌ها: {', '.join(GRADES)}\nرشته‌ها: {', '.join(MAJORS)}"
        )
        return AWAITING_BOOK_LINE

    book = C.get_or_create_test_book(grade, major_full, subject, name)
    await update.message.reply_text(f"✅ کتاب اضافه شد!\n({book['name']} — {subject} — {grade})")
    return ConversationHandler.END


# ==================== افزودن تست تکی (گام‌به‌گام + عکس) ====================

async def start_add_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END
    context.user_data["new_test"] = {"_step": 0}
    await query.edit_message_text(
        "➕ افزودن تست\n\nاطلاعات رو یکی‌یکی بفرست.\n\n۱. پایه:"
    )
    return AWAITING_TEST_STEP


async def receive_test_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    state = context.user_data.setdefault("new_test", {"_step": 0})
    step_idx = state["_step"]
    field_key, field_label, choices = TEST_STEP_FIELDS[step_idx]
    raw = (update.message.text or "").strip()

    if field_key == "grade" and raw not in GRADES:
        await update.message.reply_text(f"❌ پایه باید یکی از این‌ها باشه: {', '.join(GRADES)}\n۱. پایه:")
        return AWAITING_TEST_STEP
    if field_key == "major":
        major_full = next((m for m in MAJORS if raw in m), None)
        if major_full is None:
            await update.message.reply_text(f"❌ رشته باید یکی از این‌ها باشه: {', '.join(MAJORS)}\n۲. رشته:")
            return AWAITING_TEST_STEP
        raw = major_full
    if field_key == "number":
        if not raw.isdigit():
            await update.message.reply_text("❌ شماره تست باید عدد باشه.\n۶. شماره تست:")
            return AWAITING_TEST_STEP
        raw = int(raw)

    state[field_key] = raw
    step_idx += 1
    state["_step"] = step_idx

    if step_idx < len(TEST_STEP_FIELDS):
        next_key, next_label, _ = TEST_STEP_FIELDS[step_idx]
        await update.message.reply_text(f"{step_idx + 1}. {next_label}:")
        return AWAITING_TEST_STEP

    await update.message.reply_text("📷 حالا عکس سوال (همراه با گزینه‌ها) رو بفرست:")
    return AWAITING_QUESTION_IMAGE


async def receive_question_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_id = _extract_image_file_id(update.message)
    if file_id is None:
        await update.message.reply_text("❌ این عکس/فایل نیست. دوباره بفرست:")
        return AWAITING_QUESTION_IMAGE

    state = context.user_data.setdefault("new_test", {})
    state["question_image_file_id"] = file_id
    await update.message.reply_text("✅ عکس دریافت شد.\nحالا شماره گزینه‌ی صحیح رو بنویس (۱ تا ۴):")
    return AWAITING_CORRECT_OPTION


async def receive_correct_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.message.text or "").strip()
    if raw not in {"1", "2", "3", "4"}:
        await update.message.reply_text("❌ باید عددی بین ۱ تا ۴ باشه. دوباره بنویس:")
        return AWAITING_CORRECT_OPTION

    state = context.user_data.setdefault("new_test", {})
    state["correct_option"] = int(raw)

    rows = [
        [InlineKeyboardButton("✅ بله، عکس توضیح/پاسخ دارم", callback_data="addtest:exp_yes")],
        [InlineKeyboardButton("❌ نه، رد کن", callback_data="addtest:exp_no")],
    ]
    await update.message.reply_text(
        "می‌خوای عکس توضیح/پاسخ‌نامه هم اضافه کنی؟", reply_markup=InlineKeyboardMarkup(rows)
    )
    return AWAITING_EXPLANATION_CHOICE


async def explanation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "addtest:exp_yes":
        await query.edit_message_text("📷 عکس توضیح/پاسخ‌نامه رو بفرست:")
        return AWAITING_EXPLANATION_IMAGE

    result = _save_new_test(context)
    await query.edit_message_text(result)
    return ConversationHandler.END


async def receive_explanation_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_id = _extract_image_file_id(update.message)
    if file_id is None:
        await update.message.reply_text("❌ این عکس/فایل نیست. دوباره بفرست:")
        return AWAITING_EXPLANATION_IMAGE

    state = context.user_data.setdefault("new_test", {})
    state["explanation_image_file_id"] = file_id
    result = _save_new_test(context)
    await update.message.reply_text(result)
    return ConversationHandler.END


def _save_new_test(context: ContextTypes.DEFAULT_TYPE) -> str:
    state = context.user_data.get("new_test", {})
    try:
        book = C.get_or_create_test_book(state["grade"], state["major"], state["subject"], state["book"])
        chapter = C.get_or_create_chapter(book["id"], state["chapter"])
        C.add_question(
            chapter["id"], state["number"], state["question_image_file_id"],
            correct_option=state["correct_option"],
            explanation_image_file_id=state.get("explanation_image_file_id"),
        )
        result = "✅ تست با موفقیت اضافه شد."
    except Exception as e:
        result = f"❌ خطا در ثبت تست: {e}"
    context.user_data.pop("new_test", None)
    return result


# ==================== آپلود دسته‌جمعی (ZIP: manifest + عکس‌ها) ====================

async def ask_bulk_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ این بخش فقط برای ادمینه.", show_alert=True)
        return ConversationHandler.END
    await query.edit_message_text(
        "📤 آپلود دسته‌جمعی\n\n"
        "یه فایل ZIP بفرست شامل:\n"
        "۱. یه فایل manifest.xlsx یا manifest.csv با ستون‌های:\n"
        "پایه | رشته | درس | کتاب | فصل | شماره | پاسخ | فایل_سوال | فایل_توضیح(اختیاری)\n\n"
        "۲. عکس‌های سوال/توضیح، با همون اسمی که توی manifest نوشتی (مثلاً q5.jpg)\n\n"
        "فایل ZIP رو بفرست:"
    )
    return AWAITING_BULK_ZIP


async def receive_bulk_zip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    if doc is None or not doc.file_name.lower().endswith(".zip"):
        await update.message.reply_text("❌ فایل ارسالی zip نیست. یه فایل .zip بفرست:")
        return AWAITING_BULK_ZIP

    import tempfile, os, shutil, zipfile

    tmp_dir = tempfile.mkdtemp(prefix="bulk_upload_")
    zip_path = os.path.join(tmp_dir, "upload.zip")
    extract_dir = os.path.join(tmp_dir, "extracted")

    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(zip_path)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            await update.message.reply_text("❌ فایل zip معتبر نیست. دوباره بفرست:")
            return AWAITING_BULK_ZIP

        added, errors = await _import_bulk_zip(extract_dir, context.bot, update.effective_user.id)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    text = f"✅ {added} تست با موفقیت اضافه شد."
    if errors:
        text += f"\n\n⚠️ {len(errors)} خطا:\n" + "\n".join(errors[:10])
        if len(errors) > 10:
            text += f"\n... و {len(errors) - 10} خطای دیگه"
    await update.message.reply_text(text)
    return ConversationHandler.END


def _read_manifest_rows(path: str) -> list:
    if path.lower().endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        return list(ws.iter_rows(min_row=2, values_only=True))
    if path.lower().endswith(".csv"):
        import csv
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        return rows[1:]
    raise ValueError("فرمت manifest باید xlsx یا csv باشه")


async def _import_bulk_zip(extract_dir: str, bot, admin_id: int) -> tuple[int, list[str]]:
    import os

    file_index: dict[str, str] = {}
    manifest_path = None
    for root, _, files in os.walk(extract_dir):
        for fname in files:
            full = os.path.join(root, fname)
            file_index[fname.lower()] = full
            if manifest_path is None and fname.lower().startswith("manifest") \
                    and fname.lower().endswith((".xlsx", ".xls", ".csv")):
                manifest_path = full

    if manifest_path is None:
        for fname, full in file_index.items():
            if fname.endswith((".xlsx", ".xls", ".csv")):
                manifest_path = full
                break

    if manifest_path is None:
        return 0, ["❌ فایل manifest (xlsx یا csv) داخل zip پیدا نشد."]

    try:
        rows = _read_manifest_rows(manifest_path)
    except Exception as e:
        return 0, [f"❌ خطا در خوندن manifest: {e}"]

    added = 0
    errors: list[str] = []
    image_cache: dict[str, str] = {}  # مسیر محلی -> file_id تلگرام (جلوگیری از آپلود تکراری)

    for row_idx, row in enumerate(rows, start=2):
        if row is None or all(c in (None, "") for c in row):
            continue
        if len(row) < 8:
            errors.append(f"ردیف {row_idx}: تعداد ستون‌ها ناقصه (حداقل ۸ ستون لازمه)")
            continue

        padded = list(row) + [None] * (9 - len(row))
        (grade, major_short, subject, book_name, chapter_name,
         number, correct, q_img_name, exp_img_name) = padded[:9]

        try:
            grade = str(grade).strip()
            major_full = next((m for m in MAJORS if str(major_short).strip() in m), None)
            if grade not in GRADES or major_full is None:
                errors.append(f"ردیف {row_idx}: پایه یا رشته نامعتبر")
                continue
            number = int(number)
            correct = int(correct)
            if correct not in (1, 2, 3, 4):
                errors.append(f"ردیف {row_idx}: پاسخ صحیح باید ۱ تا ۴ باشه")
                continue

            q_img_name = str(q_img_name).strip()
            q_path = file_index.get(q_img_name.lower())
            if not q_path:
                errors.append(f"ردیف {row_idx}: فایل عکس «{q_img_name}» داخل zip پیدا نشد")
                continue

            question_file_id = image_cache.get(q_path)
            if question_file_id is None:
                with open(q_path, "rb") as f:
                    msg = await bot.send_photo(chat_id=admin_id, photo=f)
                question_file_id = msg.photo[-1].file_id
                image_cache[q_path] = question_file_id

            explanation_file_id = None
            exp_img_name_clean = str(exp_img_name).strip() if exp_img_name else ""
            if exp_img_name_clean:
                exp_path = file_index.get(exp_img_name_clean.lower())
                if not exp_path:
                    errors.append(f"ردیف {row_idx}: فایل توضیح «{exp_img_name_clean}» پیدا نشد (سوال بدون توضیح ثبت شد)")
                else:
                    explanation_file_id = image_cache.get(exp_path)
                    if explanation_file_id is None:
                        with open(exp_path, "rb") as f:
                            msg2 = await bot.send_photo(chat_id=admin_id, photo=f)
                        explanation_file_id = msg2.photo[-1].file_id
                        image_cache[exp_path] = explanation_file_id

            book = C.get_or_create_test_book(grade, major_full, str(subject).strip(), str(book_name).strip())
            chapter = C.get_or_create_chapter(book["id"], str(chapter_name).strip())
            C.add_question(chapter["id"], number, question_file_id, correct, explanation_file_id)
            added += 1
        except Exception as e:
            errors.append(f"ردیف {row_idx}: {e}")

    return added, errors


def build_add_book_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_book_line, pattern=r"^admin:add_book$")],
        states={AWAITING_BOOK_LINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_book_line)]},
        fallbacks=[],
        name="admin_add_book_conversation",
        persistent=False,
    )


def build_add_test_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_test, pattern=r"^admin:add_test$")],
        states={
            AWAITING_TEST_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_test_step)],
            AWAITING_QUESTION_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_question_image)
            ],
            AWAITING_CORRECT_OPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_correct_option)
            ],
            AWAITING_EXPLANATION_CHOICE: [
                CallbackQueryHandler(explanation_choice, pattern=r"^addtest:exp_"),
            ],
            AWAITING_EXPLANATION_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_explanation_image)
            ],
        },
        fallbacks=[],
        name="admin_add_test_conversation",
        persistent=False,
    )


def build_excel_upload_conversation() -> ConversationHandler:
    """نام تابع به‌خاطر سازگاری با bot.py حفظ شده؛ الان آپلود ZIP رو مدیریت می‌کنه."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_bulk_upload, pattern=r"^admin:upload_bulk$")],
        states={AWAITING_BULK_ZIP: [MessageHandler(filters.Document.ALL, receive_bulk_zip)]},
        fallbacks=[],
        name="admin_bulk_upload_conversation",
        persistent=False,
    )


test_management_handlers = [
    CallbackQueryHandler(entry_test_management, pattern=r"^admin:tests$"),
]
