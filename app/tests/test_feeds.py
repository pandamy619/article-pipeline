from src.feeds import service as fs


def test_add_and_list(session):
    f = fs.add_feed(session, "https://a.com/feed")
    assert f.id is not None
    assert [x.url for x in fs.list_feeds(session)] == ["https://a.com/feed"]


def test_add_dedupes(session):
    fs.add_feed(session, "https://a.com/feed")
    again = fs.add_feed(session, "https://a.com/feed")
    assert len(fs.list_feeds(session)) == 1
    assert again is not None


def test_add_blank_returns_none(session):
    assert fs.add_feed(session, "   ") is None


def test_remove(session):
    f = fs.add_feed(session, "https://a.com/feed")
    assert fs.remove_feed(session, f.id) is True
    assert fs.remove_feed(session, 999) is False
    assert list(fs.list_feeds(session)) == []


def test_set_enabled_filters_only_enabled(session):
    f = fs.add_feed(session, "https://a.com/feed")
    fs.set_enabled(session, f.id, False)
    assert list(fs.list_feeds(session, only_enabled=True)) == []


def test_effective_feeds_merges_env_and_db(session, monkeypatch):
    import src.config

    monkeypatch.setattr(src.config.settings, "rss_feeds", "https://env.com/feed")
    fs.add_feed(session, "https://db.com/feed")
    fs.add_feed(session, "https://env.com/feed")  # дубль с env — не должен повториться
    assert fs.effective_feeds(session) == [
        "https://env.com/feed",
        "https://db.com/feed",
    ]
