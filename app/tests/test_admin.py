import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.db.base as db_base
from src.admin.app import app
from src.db.models import ArticleRecord, ArticleStatus, Base, RunLog


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)
    monkeypatch.setattr(db_base, "SessionLocal", test_session)

    s = test_session()
    s.add(
        ArticleRecord(
            url="https://e.com/1",
            content_hash="h1",
            title="Тестовая статья",
            text="t",
            source="Tproger",
            status=ArticleStatus.new,
            relevance_score=8,
            relevance_reason="подходит новичку",
        )
    )
    s.commit()
    s.close()
    return TestClient(app)


def test_list_articles(client):
    r = client.get("/api/articles")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Тестовая статья"
    assert data[0]["source"] == "Tproger"
    assert data[0]["relevance_score"] == 8
    assert "post_text" in data[0]


def test_stats(client):
    data = client.get("/api/stats").json()
    assert data["new"] == 1
    assert data["total"] == 1


def test_reject_action(client):
    assert client.post("/api/articles/1/reject").json() == {"ok": True}
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.rejected
    s.close()


def test_set_status(client):
    assert client.post("/api/articles/1/status", json={"status": "drafted"}).json() == {
        "ok": True
    }
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.drafted
    s.close()


def test_published_status_locked(client):
    s = db_base.SessionLocal()
    s.get(ArticleRecord, 1).status = ArticleStatus.published
    s.commit()
    s.close()
    assert client.post("/api/articles/1/status", json={"status": "new"}).json() == {
        "ok": False
    }
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.published
    s.close()


def test_save_post(client):
    client.post("/api/articles/1/post", json={"text": "новый пост"})
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).post_text == "новый пост"
    s.close()


def test_revise(client, monkeypatch):
    import src.llm.client as llm

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def generate(self, prompt, *, system=None, format=None):
            return '{"post": "переписанный пост"}'

    monkeypatch.setattr(llm, "OllamaClient", FakeClient)

    s = db_base.SessionLocal()
    s.get(ArticleRecord, 1).post_text = "старый\n\nИсточник: https://e.com/1"
    s.commit()
    s.close()

    data = client.post("/api/articles/1/revise", json={"instruction": "короче"}).json()
    assert data["ok"] is True
    assert "переписанный пост" in data["post"]


def test_feeds_api_add_list_delete(client):
    r = client.post("/api/feeds", json={"url": "https://x.com/feed"})
    assert r.json()["ok"] is True
    fid = r.json()["id"]

    feeds = client.get("/api/feeds").json()
    assert any(f["url"] == "https://x.com/feed" and f["source"] == "db" for f in feeds)

    assert client.delete(f"/api/feeds/{fid}").json() == {"ok": True}
    feeds2 = client.get("/api/feeds").json()
    assert not any(f["url"] == "https://x.com/feed" for f in feeds2)


def test_schedule_and_unschedule(client):
    s = db_base.SessionLocal()
    s.get(ArticleRecord, 1).post_text = "пост"
    s.commit()
    s.close()

    r = client.post("/api/articles/1/schedule", json={}).json()
    assert r["ok"] is True
    assert r["scheduled_at"]
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.scheduled
    s.close()

    assert client.post("/api/articles/1/unschedule").json() == {"ok": True}


def test_schedule_explicit_time(client):
    s = db_base.SessionLocal()
    s.get(ArticleRecord, 1).post_text = "пост"
    s.commit()
    s.close()
    r = client.post(
        "/api/articles/1/schedule", json={"when": "2030-01-01T10:00:00Z"}
    ).json()
    assert r["ok"] is True
    assert "2030-01-01" in r["scheduled_at"]


def test_bulk_queue_then_reject(client):
    s = db_base.SessionLocal()
    s.get(ArticleRecord, 1).post_text = "пост"
    s.add(
        ArticleRecord(
            url="https://e.com/2",
            content_hash="h2",
            title="t2",
            text="x",
            source="s",
            status=ArticleStatus.drafted,
            post_text="пост2",
        )
    )
    s.commit()
    s.close()

    r = client.post(
        "/api/articles/bulk", json={"ids": [1, 2], "action": "queue"}
    ).json()
    assert r["ok"] is True
    assert r["done"] == 2
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.scheduled
    s.close()

    r = client.post(
        "/api/articles/bulk", json={"ids": [1, 2], "action": "reject"}
    ).json()
    assert r["done"] == 2
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 2).status == ArticleStatus.rejected
    s.close()


def test_auth_required_when_token_set(client, monkeypatch):
    import src.config

    monkeypatch.setattr(src.config.settings, "admin_token", "secret")
    assert client.get("/api/stats").status_code == 401
    ok = client.get("/api/stats", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200
    assert (
        client.get(
            "/api/auth/check", headers={"Authorization": "Bearer secret"}
        ).status_code
        == 200
    )


def test_channels_crud(client):
    chs = client.get("/api/channels").json()
    assert len(chs) == 1  # дефолтный канал засеян
    c = client.post("/api/channels", json={"name": "Второй", "topic": "go"}).json()
    cid = c["id"]
    assert c["name"] == "Второй"
    assert (
        client.put(f"/api/channels/{cid}", json={"topic": "rust"}).json()["topic"]
        == "rust"
    )
    assert client.delete(f"/api/channels/{cid}").json() == {"ok": True}
    assert len(client.get("/api/channels").json()) == 1


def test_articles_scoped_by_channel(client):
    chs = client.get("/api/channels").json()  # ensure default + привяжет сироту
    default_id = chs[0]["id"]
    arts = client.get(f"/api/articles?channel={default_id}").json()
    assert any(a["id"] == 1 for a in arts)
    assert client.get("/api/articles?channel=999").json() == []


def test_settings_api_get_and_set(client, monkeypatch):
    import src.config

    monkeypatch.setattr(src.config.settings, "relevance_threshold", 7)
    data = client.get("/api/settings").json()
    assert "relevance_threshold" in data["settings"]
    assert "types" in data
    assert client.post(
        "/api/settings", json={"key": "relevance_threshold", "value": "9"}
    ).json() == {"ok": True}
    assert client.post("/api/settings", json={"key": "nope", "value": "x"}).json() == {
        "ok": False
    }


def test_last_run_empty(client):
    assert client.get("/api/last-run").json() == {"exists": False}


def test_last_run_reports_metrics(client):
    s = db_base.SessionLocal()
    s.add(RunLog(collected=5, added=3, drafted=2, ok=True))
    s.commit()
    s.close()
    data = client.get("/api/last-run").json()
    assert data["exists"] is True
    assert data["drafted"] == 2
    assert data["ok"] is True


def test_collect_enqueue_status_dedup(client):
    # ставим сбор в очередь — возвращается задача queued
    job = client.post("/api/collect").json()
    assert job["status"] == "queued"
    assert job["channel_id"] is None
    jid = job["id"]

    # статус по id
    st = client.get(f"/api/collect/status/{jid}").json()
    assert st["id"] == jid and st["status"] == "queued"

    # активные содержат её
    assert any(j["id"] == jid for j in client.get("/api/collect/active").json())

    # повторный запрос не плодит дубль — та же задача
    assert client.post("/api/collect").json()["id"] == jid


def test_search_web_enqueues_job(client):
    r = client.post(
        "/api/search", json={"query": "асинхронный python", "mode": "web"}
    ).json()
    assert r["mode"] == "web"
    assert r["job"]["status"] == "queued"
    assert r["job"]["query"] == "асинхронный python"
    # повторный запрос с тем же query/каналом не плодит дубль
    again = client.post(
        "/api/search", json={"query": "асинхронный python", "mode": "web"}
    ).json()
    assert again["job"]["id"] == r["job"]["id"]


def _add_web_candidate(title, url, h):
    s = db_base.SessionLocal()
    s.add(
        ArticleRecord(
            url=url,
            content_hash=h,
            title=title,
            text="t",
            source="Веб-поиск",
            status=ArticleStatus.drafted,
            post_text="пост",
            review=True,
        )
    )
    s.commit()
    s.close()


def test_web_candidate_hidden_until_approved(client):
    _add_web_candidate("Веб находка", "https://web.com/a", "wh1")

    # в общей таблице её нет, в pending — есть
    assert all(a["title"] != "Веб находка" for a in client.get("/api/articles").json())
    pend = client.get("/api/search/pending").json()
    cand = next(p for p in pend if p["title"] == "Веб находка")

    # одобряем -> появляется в общей таблице и уходит из pending
    assert client.post(f"/api/articles/{cand['id']}/approve").json() == {"ok": True}
    assert any(a["title"] == "Веб находка" for a in client.get("/api/articles").json())
    assert all(
        p["title"] != "Веб находка" for p in client.get("/api/search/pending").json()
    )


def test_bulk_approve_moves_web_candidates(client):
    _add_web_candidate("К1", "https://web.com/c1", "wc1")
    _add_web_candidate("К2", "https://web.com/c2", "wc2")
    pend = client.get("/api/search/pending").json()
    ids = [p["id"] for p in pend if p["title"] in ("К1", "К2")]
    assert len(ids) == 2

    r = client.post(
        "/api/articles/bulk", json={"ids": ids, "action": "approve"}
    ).json()
    assert r["done"] == 2

    titles = {a["title"] for a in client.get("/api/articles").json()}
    assert {"К1", "К2"} <= titles  # переехали в общую таблицу
    assert all(
        p["title"] not in ("К1", "К2")
        for p in client.get("/api/search/pending").json()
    )


def test_web_candidate_reject_stays_hidden(client):
    _add_web_candidate("Отклоню", "https://web.com/b", "wh2")
    pend = client.get("/api/search/pending").json()
    cand = next(p for p in pend if p["title"] == "Отклоню")

    assert client.post(f"/api/articles/{cand['id']}/reject").json() == {"ok": True}
    # ни в pending (rejected), ни в общей таблице (review=True)
    assert all(
        p["title"] != "Отклоню" for p in client.get("/api/search/pending").json()
    )
    assert all(a["title"] != "Отклоню" for a in client.get("/api/articles").json())


def test_publish_bad_chat_returns_error_not_500(client, monkeypatch):
    from aiogram.exceptions import TelegramBadRequest

    import src.bot_factory as bf
    import src.publisher.telegram as tg

    s = db_base.SessionLocal()
    s.get(ArticleRecord, 1).post_text = "пост"
    s.commit()
    s.close()

    class _Sess:
        async def close(self):
            pass

    class _Bot:
        session = _Sess()

    monkeypatch.setattr(bf, "make_bot", lambda token: _Bot())

    async def _raise(*a, **k):
        raise TelegramBadRequest(method=None, message="chat not found")

    monkeypatch.setattr(tg, "publish", _raise)

    r = client.post("/api/articles/1/publish")
    assert r.status_code == 200  # не 500
    data = r.json()
    assert data["ok"] is False
    assert "chat not found" in data["error"]


def test_chat(client, monkeypatch):
    import src.llm.client as llm

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def chat(self, messages, *, format=None):
            return "это полезная статья для новичков"

    monkeypatch.setattr(llm, "OllamaClient", FakeClient)

    data = client.post(
        "/api/articles/1/chat",
        json={"messages": [{"role": "user", "content": "как тебе статья?"}]},
    ).json()
    assert "новичков" in data["reply"]
