from datetime import datetime

from src.collectors.reddit import collect_reddit, listing_url

SAMPLE = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "Learn Python",
                    "permalink": "/r/learnprogramming/comments/x/learn_python/",
                    "selftext": "Tips here",
                    "created_utc": 1735819200,
                }
            },
            {
                "data": {
                    "title": "Cool link",
                    "url": "https://ext.com/a",
                    "permalink": "/r/learnprogramming/comments/y/cool_link/",
                    "selftext": "",
                    "created_utc": 1735819200,
                }
            },
        ]
    }
}


def test_listing_url():
    assert listing_url("learnprogramming", period="month", limit=5) == (
        "https://www.reddit.com/r/learnprogramming/top.json?t=month&limit=5"
    )


def test_collect_reddit_parses():
    arts = collect_reddit(["learnprogramming"], fetcher=lambda url: SAMPLE)
    assert len(arts) == 2
    first = arts[0]
    assert first.title == "Learn Python"
    assert first.url == (
        "https://www.reddit.com/r/learnprogramming/comments/x/learn_python/"
    )
    assert first.text == "Tips here"
    assert first.source == "Reddit r/learnprogramming"
    assert isinstance(first.published_at, datetime)
    # пост-ссылка без selftext: текст падает на заголовок
    assert arts[1].text == "Cool link"
