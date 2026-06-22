import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.db.base as db_base
from src.admin.app import app
from src.db.models import ArticleRecord, ArticleStatus, Base


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
