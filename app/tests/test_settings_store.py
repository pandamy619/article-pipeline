from src.config import settings
from src.settings_store import (
    apply_overrides,
    current_values,
    get_overrides,
    set_override,
)


def test_set_and_get_override(session):
    assert set_override(session, "relevance_threshold", "9") is True
    assert get_overrides(session)["relevance_threshold"] == "9"


def test_set_rejects_unknown_key(session):
    assert set_override(session, "not_a_setting", "x") is False


def test_apply_overrides_casts(session, monkeypatch):
    monkeypatch.setattr(settings, "relevance_threshold", 7)
    monkeypatch.setattr(settings, "semantic_dedup_enabled", True)
    set_override(session, "relevance_threshold", "9")
    set_override(session, "semantic_dedup_enabled", "false")
    apply_overrides(session)
    assert settings.relevance_threshold == 9
    assert settings.semantic_dedup_enabled is False


def test_current_values_has_editable_keys(session):
    vals = current_values(session)
    assert "channel_topic" in vals
    assert "llm_model" in vals
