from src.config import settings
from src.settings_store import (
    apply_overrides,
    current_values,
    get_overrides,
    set_override,
)


def test_set_and_get_override(session):
    assert set_override(session, "max_articles_per_run", "5") is True
    assert get_overrides(session)["max_articles_per_run"] == "5"


def test_set_rejects_unknown_key(session):
    assert set_override(session, "not_a_setting", "x") is False


def test_set_rejects_per_project_key(session):
    # тематика/порог/источники — настройки проекта, не глобальные
    assert set_override(session, "relevance_threshold", "9") is False
    assert set_override(session, "searxng_queries", "x") is False


def test_apply_overrides_casts(session, monkeypatch):
    monkeypatch.setattr(settings, "max_articles_per_run", 7)
    monkeypatch.setattr(settings, "semantic_dedup_enabled", True)
    set_override(session, "max_articles_per_run", "5")
    set_override(session, "semantic_dedup_enabled", "false")
    apply_overrides(session)
    assert settings.max_articles_per_run == 5
    assert settings.semantic_dedup_enabled is False


def test_current_values_has_editable_keys(session):
    vals = current_values(session)
    assert "max_articles_per_run" in vals
    assert "llm_model" in vals
    assert "relevance_threshold" not in vals  # ушло в проекты
