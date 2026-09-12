"""
شبیه‌ساز سبک برای تست end-to-end handlerها بدون نیاز به سرور واقعی تلگرام.
"""
import asyncio


class FakePhotoSize:
    def __init__(self, file_id):
        self.file_id = file_id


class FakeMessage:
    def __init__(self, text=None, document=None, caption=None, photo=None):
        self.text = text
        self.document = document
        self.caption = caption
        self.photo = photo or []
        self.replies = []
        self.documents_sent = []
        self.photos_sent = []

    async def reply_text(self, text, reply_markup=None, **kwargs):
        self.replies.append((text, reply_markup))
        return FakeMessage()

    async def reply_document(self, document, caption=None, **kwargs):
        self.documents_sent.append((document, caption))
        return FakeMessage()

    async def reply_photo(self, photo, caption=None, reply_markup=None, **kwargs):
        self.photos_sent.append((photo, caption, reply_markup))
        return FakeMessage()


class FakeCallbackQuery:
    def __init__(self, data, message=None):
        self.data = data
        self.message = message or FakeMessage()
        self.answers = []
        self.edits = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None, **kwargs):
        self.edits.append((text, reply_markup))
        return FakeMessage()


class FakeUser:
    def __init__(self, user_id, username=None, first_name="تست"):
        self.id = user_id
        self.username = username
        self.first_name = first_name


class FakeBot:
    def __init__(self):
        self.sent_messages = []
        self.sent_photos = []

    async def get_chat_member(self, chat_id, user_id):
        raise Exception("no forced channels configured in this test")

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text))

    async def send_photo(self, chat_id, photo, **kwargs):
        # photo می‌تونه یه file object (باز شده با open(path,'rb')) یا رشته باشه
        name = getattr(photo, "name", str(photo))
        file_id = f"UPLOADED::{name}"
        self.sent_photos.append((chat_id, name))
        msg = FakeMessage()
        msg.photo = [FakePhotoSize(file_id)]
        return msg

    async def get_me(self):
        class Me:
            username = "test_bot"
        return Me()


class FakeUpdate:
    def __init__(self, user, message=None, callback_query=None):
        self.effective_user = user
        self.message = message
        self.callback_query = callback_query


class FakeContext:
    def __init__(self, bot=None, args=None):
        self.bot = bot or FakeBot()
        self.user_data = {}
        self.args = args or []


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)
