from src.collectors import habr
from src.collectors.base import Article
from src.collectors.habr import collect_habr, habr_feeds


def test_habr_feeds_general_when_no_hubs():
    assert habr_feeds([]) == ["https://habr.com/ru/rss/articles/?fl=ru"]


def test_habr_feeds_per_hub():
    assert habr_feeds(["programming", "python"]) == [
        "https://habr.com/ru/rss/hubs/programming/articles/?fl=ru",
        "https://habr.com/ru/rss/hubs/python/articles/?fl=ru",
    ]


def test_collect_habr_labels_source(monkeypatch):
    def fake_collect_rss(feeds, **kwargs):
        return [Article("t", "https://habr.com/ru/articles/1/", "x", "Habr Feed")]

    monkeypatch.setattr(habr, "collect_rss", fake_collect_rss)
    arts = collect_habr(["python"])
    assert len(arts) == 1
    assert arts[0].source == "Habr"
