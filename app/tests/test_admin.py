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


def test_index_lists_articles(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Тестовая статья" in r.text
    assert "Tproger" in r.text
    assert "подходит новичку" in r.text


def test_reject_action(client):
    client.post("/articles/1/reject")
    s = db_base.SessionLocal()
    assert s.get(ArticleRecord, 1).status == ArticleStatus.rejected
    s.close()
