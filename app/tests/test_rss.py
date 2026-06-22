from datetime import datetime

from src.collectors.rss import _og_image, collect_rss

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Первая статья</title>
      <link>https://example.com/a</link>
      <pubDate>Tue, 10 Jun 2025 09:00:00 GMT</pubDate>
      <description>краткое описание</description>
    </item>
    <item>
      <title>Вторая статья</title>
      <link>https://example.com/b</link>
      <pubDate>Wed, 11 Jun 2025 12:30:00 GMT</pubDate>
      <description>другое описание</description>
    </item>
  </channel>
</rss>"""


def test_collect_rss_normalizes_entries():
    # подменяем загрузку текста, чтобы тест был оффлайн и детерминированный
    articles = collect_rss([SAMPLE_RSS], text_fetcher=lambda url: f"full text of {url}")

    assert len(articles) == 2
    first = articles[0]
    assert first.title == "Первая статья"
    assert first.url == "https://example.com/a"
    assert first.source == "Test Feed"
    assert first.text == "full text of https://example.com/a"
    assert isinstance(first.published_at, datetime)
    assert first.published_at.year == 2025


def test_collect_rss_falls_back_to_summary():
    # если полный текст не достался — берём summary из ленты
    articles = collect_rss([SAMPLE_RSS], text_fetcher=lambda url: None)
    assert articles[0].text == "краткое описание"


def test_limit_per_feed():
    articles = collect_rss([SAMPLE_RSS], text_fetcher=lambda url: "x", limit_per_feed=1)
    assert len(articles) == 1


SAMPLE_RSS_IMG = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Feed</title>
    <item>
      <title>С картинкой</title>
      <link>https://example.com/img</link>
      <enclosure url="https://img.example.com/a.jpg" type="image/jpeg" length="10"/>
    </item>
  </channel>
</rss>"""


def test_collect_rss_extracts_image():
    arts = collect_rss([SAMPLE_RSS_IMG], text_fetcher=lambda url: "x")
    assert arts[0].image_url == "https://img.example.com/a.jpg"


def test_og_image_extraction():
    assert (
        _og_image('<meta property="og:image" content="https://img/og.jpg">')
        == "https://img/og.jpg"
    )
    assert (
        _og_image('<meta content="https://img/o2.jpg" name="og:image">')
        == "https://img/o2.jpg"
    )
    assert _og_image("<html></html>") is None


def test_collect_rss_meta_path_gets_page_image(monkeypatch):
    from src.collectors import rss

    monkeypatch.setattr(
        rss,
        "fetch_article_meta",
        lambda url: ("текст со страницы", "https://img/p.jpg"),
    )
    arts = rss.collect_rss([SAMPLE_RSS])  # без text_fetcher -> meta-путь
    assert arts[0].text == "текст со страницы"
    assert arts[0].image_url == "https://img/p.jpg"
