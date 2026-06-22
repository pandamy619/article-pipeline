from datetime import datetime

from src.collectors.arxiv import build_query_url, collect_arxiv

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>A Gentle
      Intro to Testing</title>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <link href="http://arxiv.org/abs/2501.00001v1" rel="alternate" type="text/html"/>
    <published>2025-01-02T10:00:00Z</published>
    <summary>We present a gentle intro.</summary>
  </entry>
</feed>"""


def test_build_query_url():
    url = build_query_url(["cs.SE", "cs.PL"], max_results=5)
    assert "search_query=cat:cs.SE+OR+cat:cs.PL" in url
    assert "max_results=5" in url


def test_collect_arxiv_parses():
    arts = collect_arxiv(["cs.SE"], fetcher=lambda url: SAMPLE_ATOM)
    assert len(arts) == 1
    a = arts[0]
    assert a.title == "A Gentle Intro to Testing"
    assert a.url == "http://arxiv.org/abs/2501.00001v1"
    assert a.source == "arXiv"
    assert a.text == "We present a gentle intro."
    assert isinstance(a.published_at, datetime)


def test_collect_arxiv_empty_categories():
    assert collect_arxiv([]) == []
