"""
اسکیمای کامل دیتابیس ربات تست/کنکور.
از sqlite3 استاندارد پایتون استفاده می‌کنیم (بدون نیاز به نصب پکیج اضافه).
"""

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ==================== کاربران ====================
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,   -- آیدی عددی تلگرام
    username        TEXT,
    full_name       TEXT,
    grade           TEXT,                  -- دهم / یازدهم / دوازدهم
    major           TEXT,                  -- ریاضی / تجربی / انسانی
    points          INTEGER NOT NULL DEFAULT 0,
    weekly_points   INTEGER NOT NULL DEFAULT 0,
    referred_by     INTEGER,               -- user_id معرف
    invited_count   INTEGER NOT NULL DEFAULT 0,
    registration_step TEXT NOT NULL DEFAULT 'not_started',
                        -- not_started / awaiting_name / awaiting_grade /
                        -- awaiting_major / awaiting_confirm / done
    registered_at   TEXT,
    last_active_at  TEXT,
    FOREIGN KEY (referred_by) REFERENCES users(user_id)
);

-- ==================== کانال‌های جوین اجباری ====================
CREATE TABLE IF NOT EXISTS forced_channels (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id   TEXT NOT NULL UNIQUE,   -- مثل @main_channel
    title        TEXT NOT NULL,
    invite_link  TEXT NOT NULL
);

-- ==================== کتاب‌های کتابخانه (فایل دانلودی) ====================
CREATE TABLE IF NOT EXISTS library_books (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    grade     TEXT NOT NULL,
    major     TEXT NOT NULL,
    subject   TEXT NOT NULL,          -- ریاضی، فیزیک، زیست و ...
    publisher TEXT NOT NULL,          -- ناشر/نام کتاب، مثل «خیلی سبز»
    file_id   TEXT,                   -- telegram file_id ، تا وقتی خالیه یعنی ناموجود
    available INTEGER NOT NULL DEFAULT 0,
    UNIQUE(grade, major, subject, publisher)
);

-- ==================== کتاب‌های تست (خیلی سبز، گاج، ...) ====================
CREATE TABLE IF NOT EXISTS test_books (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    grade   TEXT NOT NULL,
    major   TEXT NOT NULL,
    subject TEXT NOT NULL,
    name    TEXT NOT NULL,            -- خیلی سبز / قلم چی / گاج / میکرو / الگو
    UNIQUE(grade, major, subject, name)
);

-- ==================== فصل‌ها ====================
CREATE TABLE IF NOT EXISTS chapters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    test_book_id  INTEGER NOT NULL,
    name          TEXT NOT NULL,
    order_index   INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (test_book_id) REFERENCES test_books(id) ON DELETE CASCADE,
    UNIQUE(test_book_id, name)
);

-- ==================== سوالات ====================
CREATE TABLE IF NOT EXISTS questions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id               INTEGER NOT NULL,
    number                   INTEGER NOT NULL,     -- شماره تست داخل فصل
    question_image_file_id   TEXT NOT NULL,        -- عکس کامل سوال + گزینه‌ها
    correct_option           INTEGER NOT NULL CHECK (correct_option BETWEEN 1 AND 4),
    explanation_image_file_id TEXT,                -- عکس اختیاری پاسخ‌نامه/توضیح
    created_at               TEXT NOT NULL,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    UNIQUE(chapter_id, number)
);

-- ==================== جلسات آزمون ====================
CREATE TABLE IF NOT EXISTS exam_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    chapter_id     INTEGER NOT NULL,
    start_number   INTEGER NOT NULL,
    end_number     INTEGER NOT NULL,
    mode           TEXT NOT NULL,        -- timed / free
    status         TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress / finished
    current_index  INTEGER NOT NULL DEFAULT 0,  -- اشاره‌گر به سوال فعلی (0-based)
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (chapter_id) REFERENCES chapters(id)
);

-- ==================== پاسخ‌های هر جلسه آزمون ====================
CREATE TABLE IF NOT EXISTS exam_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    question_id     INTEGER NOT NULL,
    selected_option INTEGER,             -- NULL یعنی پاسخ داده نشده
    is_correct      INTEGER,             -- NULL یعنی پاسخ داده نشده
    answered_at     TEXT,
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id),
    UNIQUE(session_id, question_id)
);

-- ==================== گزارش اشکال در تست ====================
CREATE TABLE IF NOT EXISTS question_reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id   INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    report_type   TEXT NOT NULL,   -- wrong_options / wrong_answer / bad_text / other
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending / resolved / rejected
    created_at    TEXT NOT NULL,
    resolved_at   TEXT,
    resolved_by   INTEGER,
    admin_note    TEXT,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ==================== تاریخچه‌ی اصلاح سوالات (لاگ) ====================
CREATE TABLE IF NOT EXISTS question_edit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id    INTEGER NOT NULL,
    admin_id       INTEGER NOT NULL,
    field_changed  TEXT NOT NULL,
    old_value      TEXT,
    new_value      TEXT,
    changed_at     TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- ==================== گزارش کتاب ناموجود (کتابخانه) ====================
CREATE TABLE IF NOT EXISTS book_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    grade           TEXT NOT NULL,
    major           TEXT NOT NULL,
    subject         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
                        -- pending / added / rejected / unavailable / custom_replied
    admin_response  TEXT,
    created_at      TEXT NOT NULL,
    resolved_at     TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ==================== انتقاد و پیشنهاد ====================
CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    message         TEXT NOT NULL,
    admin_response  TEXT,
    created_at      TEXT NOT NULL,
    responded_at    TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ==================== امتحانات نهایی (فایل‌های آپلودی ادمین) ====================
CREATE TABLE IF NOT EXISTS final_exams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    grade       TEXT NOT NULL,
    major       TEXT NOT NULL,
    subject     TEXT NOT NULL,
    title       TEXT NOT NULL,       -- مثل «نوبت دوم - خرداد ۱۴۰۲»
    file_id     TEXT NOT NULL,
    uploaded_by INTEGER,
    uploaded_at TEXT NOT NULL
);

-- ==================== تنظیمات کلی ربات (کلید-مقدار) ====================
CREATE TABLE IF NOT EXISTS bot_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ==================== ایندکس‌ها برای کوئری‌های پرتکرار ====================
CREATE INDEX IF NOT EXISTS idx_chapters_book        ON chapters(test_book_id);
CREATE INDEX IF NOT EXISTS idx_questions_chapter     ON questions(chapter_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user         ON exam_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_answers_session        ON exam_answers(session_id);
CREATE INDEX IF NOT EXISTS idx_answers_correct_flag   ON exam_answers(session_id, is_correct);
CREATE INDEX IF NOT EXISTS idx_reports_status         ON question_reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_question       ON question_reports(question_id);
CREATE INDEX IF NOT EXISTS idx_book_requests_status   ON book_requests(status);
CREATE INDEX IF NOT EXISTS idx_feedback_pending       ON feedback(responded_at);
CREATE INDEX IF NOT EXISTS idx_users_points           ON users(points DESC);
CREATE INDEX IF NOT EXISTS idx_users_weekly_points    ON users(weekly_points DESC);
CREATE INDEX IF NOT EXISTS idx_final_exams_lookup     ON final_exams(grade, major, subject);
"""
