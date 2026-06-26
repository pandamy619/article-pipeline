import asyncio

from src.publisher.telegram import publish, resolve_chat_id, split_text


def test_resolve_chat_id():
    assert resolve_chat_id("-1001234567890") == -1001234567890
    assert resolve_chat_id("@mychannel") == "@mychannel"
    assert resolve_chat_id(12345) == 12345


def test_split_text_short():
    assert split_text("привет") == ["привет"]
    assert split_text("") == []


def test_split_text_long():
    parts = split_text("a " * 3000, limit=100)
    assert len(parts) > 1
    assert all(len(p) <= 100 for p in parts)


def test_split_preserves_words():
    text = "слово " * 2000
    parts = split_text(text, limit=200)
    assert " ".join(parts).split() == text.split()


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

        class M:
            message_id = len(self.sent)

        return M()


def test_publish_returns_first_message_id():
    bot = FakeBot()
    mid = asyncio.run(publish(bot, "@chan", "короткий пост"))
    assert mid == 1
    assert bot.sent == [("@chan", "короткий пост")]


def test_publish_splits_long():
    bot = FakeBot()
    asyncio.run(publish(bot, "-100123", "x " * 4000))
    assert len(bot.sent) >= 2
    assert all(chat == -100123 for chat, _ in bot.sent)


class PhotoBot:
    def __init__(self, photo_raises=False):
        self.photos = []
        self.msgs = []
        self.photo_raises = photo_raises

    async def send_photo(self, chat_id, photo, caption):
        if self.photo_raises:
            raise RuntimeError("bad image")
        self.photos.append((chat_id, photo, caption))

        class M:
            message_id = 7

        return M()

    async def send_message(self, chat_id, text):
        self.msgs.append((chat_id, text))

        class M:
            message_id = 99

        return M()


def test_publish_with_image_uses_photo():
    bot = PhotoBot()
    mid = asyncio.run(publish(bot, "@c", "короткий пост", image_url="https://i/x.jpg"))
    assert mid == 7
    assert bot.photos and not bot.msgs


def test_publish_long_with_image_falls_back_to_text():
    bot = PhotoBot()
    # caption > 1024 -> фото нельзя, шлём текстом
    asyncio.run(publish(bot, "@c", "x " * 1000, image_url="https://i/x.jpg"))
    assert bot.msgs and not bot.photos


def test_publish_photo_error_falls_back_to_text():
    bot = PhotoBot(photo_raises=True)
    asyncio.run(publish(bot, "@c", "короткий", image_url="https://i/x.jpg"))
    assert bot.msgs and not bot.photos


def test_publish_external_image_sends_url():
    bot = PhotoBot()
    asyncio.run(publish(bot, "@c", "пост", image_url="https://i/x.jpg"))
    assert bot.photos[0][1] == "https://i/x.jpg"  # внешняя — ссылкой


def test_publish_local_image_sends_file(monkeypatch, tmp_path):
    from aiogram.types import FSInputFile

    import src.config
    from src import media

    monkeypatch.setattr(src.config.settings, "media_dir", str(tmp_path))
    (tmp_path / "x.jpg").write_bytes(b"img")

    bot = PhotoBot()
    asyncio.run(
        publish(bot, "@c", "пост", image_url=media.MEDIA_URL_PREFIX + "x.jpg")
    )
    # локальный файл уходит байтами (FSInputFile), а не ссылкой
    assert isinstance(bot.photos[0][1], FSInputFile)
