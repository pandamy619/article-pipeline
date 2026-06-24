from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus
from src.db.repo import save_articles
from src.moderation import service


def _make_draft(session, url="u1", text="пост"):
    save_articles(session, [Article("T", url, "body", "src")])
    rec = session.query(ArticleRecord).filter_by(url=url).one()
    rec.status = ArticleStatus.drafted
    rec.post_text = text
    session.flush()
    return rec.id


def test_get_drafts_and_mark_pending(session):
    aid = _make_draft(session)
    assert len(service.get_drafts(session)) == 1
    service.mark_pending(session, aid)
    assert session.get(ArticleRecord, aid).status == ArticleStatus.pending
    assert len(service.get_drafts(session)) == 0


def test_get_drafts_excludes_review(session):
    # веб-находка (review=True) не должна попадать в рассылку бота
    aid = _make_draft(session, url="web1")
    session.get(ArticleRecord, aid).review = True
    session.flush()
    assert len(service.get_drafts(session)) == 0


def test_reject(session):
    aid = _make_draft(session)
    service.reject(session, aid)
    assert session.get(ArticleRecord, aid).status == ArticleStatus.rejected


def test_set_post_text(session):
    aid = _make_draft(session)
    service.set_post_text(session, aid, "новый текст")
    assert session.get(ArticleRecord, aid).post_text == "новый текст"


def test_mark_published(session):
    aid = _make_draft(session)
    service.mark_published(session, aid, 555)
    rec = session.get(ArticleRecord, aid)
    assert rec.status == ArticleStatus.published
    assert rec.tg_message_id == 555


def test_get_post_text(session):
    aid = _make_draft(session, text="готовый пост")
    assert service.get_post_text(session, aid) == "готовый пост"


def test_parse_callback():
    assert service.parse_callback("mod:approve:12") == ("approve", 12)
    assert service.parse_callback("mod:edit:3") == ("edit", 3)
    assert service.parse_callback("mod:bad:1") is None
    assert service.parse_callback("x:approve:1") is None
    assert service.parse_callback("mod:approve:abc") is None


def test_build_callback_roundtrip():
    assert service.parse_callback(service.build_callback("reject", 7)) == ("reject", 7)
