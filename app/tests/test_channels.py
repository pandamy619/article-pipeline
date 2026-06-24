from src.channels import service as ch
from src.config import settings
from src.db.models import ArticleRecord, ArticleStatus


def _article(session, url):
    rec = ArticleRecord(
        url=url, content_hash=url, title="t", text="x", status=ArticleStatus.new
    )
    session.add(rec)
    session.flush()
    return rec


def test_create_list_get(session):
    c = ch.create_channel(session, name="A", topic="t", bot_token="x")
    assert c.id is not None
    assert [x.name for x in ch.list_channels(session)] == ["A"]
    assert ch.get_channel(session, c.id).topic == "t"


def test_update_ignores_unknown(session):
    c = ch.create_channel(session, name="A")
    ch.update_channel(session, c.id, topic="new", bogus="x")
    assert ch.get_channel(session, c.id).topic == "new"


def test_strips_whitespace_in_telegram_fields(session):
    # вставленный с пробелом/переносом channel_id ломает Telegram — обрезаем
    c = ch.create_channel(
        session, name="A", channel_id="  -1003980386609\n", bot_token=" 12:abc "
    )
    assert c.channel_id == "-1003980386609"
    assert c.bot_token == "12:abc"
    ch.update_channel(session, c.id, channel_id="\t@chan ")
    assert ch.get_channel(session, c.id).channel_id == "@chan"


def test_delete_detaches_articles(session):
    c = ch.create_channel(session, name="A")
    a = _article(session, "u1")
    a.channel_id = c.id
    session.flush()
    assert ch.delete_channel(session, c.id) is True
    assert session.get(ArticleRecord, a.id).channel_id is None


def test_ensure_default_seeds_and_attaches(session, monkeypatch):
    monkeypatch.setattr(settings, "channel_topic", "тема")
    a = _article(session, "u1")
    c = ch.ensure_default_channel(session)
    assert c.name == "Основной"
    assert session.get(ArticleRecord, a.id).channel_id == c.id
    assert ch.ensure_default_channel(session).id == c.id
