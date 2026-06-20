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
