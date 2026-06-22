from src.collectors.websearch import collect_websearch

SAMPLE = [
    {
        "url": "https://a.com/1",
        "title": "Туториал по Python",
        "content": "сниппет",
        "img_src": "https://a.com/1.jpg",
    },
    {"url": "https://a.com/2", "title": "Основы Git", "content": "сниппет2"},
]


def test_collect_websearch_parses():
    arts = collect_websearch(
        ["python для новичков"],
        searcher=lambda q: SAMPLE,
        text_fetcher=lambda url: None,  # офлайн: текст падает на сниппет
    )
    assert len(arts) == 2
    assert arts[0].title == "Туториал по Python"
    assert arts[0].source == "Веб-поиск"
    assert arts[0].text == "сниппет"
    assert arts[0].image_url == "https://a.com/1.jpg"
    assert arts[1].image_url is None


def test_collect_websearch_dedupes_across_queries():
    arts = collect_websearch(
        ["q1", "q2"],
        searcher=lambda q: SAMPLE,  # одинаковая выдача по обоим запросам
        text_fetcher=lambda url: "full",
    )
    assert len(arts) == 2  # дубли по url убраны


def test_collect_websearch_empty_when_no_queries():
    assert collect_websearch([], searcher=lambda q: SAMPLE) == []
