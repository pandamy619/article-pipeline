from src.collectors import sources
from src.collectors.base import Article


def _art(name: str) -> Article:
    return Article(name, f"https://e.com/{name}", "x", name)


def test_collect_all_respects_toggles(monkeypatch):
    monkeypatch.setattr(sources.settings, "habr_enabled", True)
    monkeypatch.setattr(sources.settings, "arxiv_categories", "")
    monkeypatch.setattr(sources.settings, "reddit_subreddits", "")
    monkeypatch.setattr(sources, "collect_rss", lambda feeds, **k: [_art("rss")])
    monkeypatch.setattr(sources, "collect_habr", lambda hubs, **k: [_art("habr")])
    monkeypatch.setattr(sources, "collect_arxiv", lambda *a, **k: [_art("arxiv")])
    monkeypatch.setattr(sources, "collect_reddit", lambda *a, **k: [_art("reddit")])

    arts = sources.collect_all(["https://feed"])
    # arxiv/reddit выключены (пустые настройки) — их быть не должно
    assert {a.source for a in arts} == {"rss", "habr"}


def test_collect_all_interleaves_sources(monkeypatch):
    monkeypatch.setattr(sources.settings, "habr_enabled", True)
    monkeypatch.setattr(sources.settings, "arxiv_categories", "")
    monkeypatch.setattr(sources.settings, "reddit_subreddits", "")
    monkeypatch.setattr(
        sources,
        "collect_rss",
        lambda feeds, **k: [_art("rss1"), _art("rss2"), _art("rss3")],
    )
    monkeypatch.setattr(
        sources, "collect_habr", lambda hubs, **k: [_art("h1"), _art("h2")]
    )

    arts = sources.collect_all(["https://feed"])
    # по очереди из источников, остаток rss — в конце
    assert [a.source for a in arts] == ["rss1", "h1", "rss2", "h2", "rss3"]


def test_collect_all_isolates_failures(monkeypatch):
    monkeypatch.setattr(sources.settings, "habr_enabled", True)
    monkeypatch.setattr(sources.settings, "arxiv_categories", "")
    monkeypatch.setattr(sources.settings, "reddit_subreddits", "")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(sources, "collect_rss", lambda feeds, **k: [_art("rss")])
    monkeypatch.setattr(sources, "collect_habr", boom)

    arts = sources.collect_all(["https://feed"])
    # habr упал, но rss собрался — прогон выжил
    assert [a.source for a in arts] == ["rss"]
