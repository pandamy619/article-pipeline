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


def test_stats(client):
    data = client.get("/api/stats").json()
    assert data["new"] == 1
    assert data["total"] == 1


def test_reject_action(client):
    assert client.post("/api/articles/1/reject").json() == {"ok": True}
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.rejected
    s.close()
