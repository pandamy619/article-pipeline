import src.config
from src.images.search import image_keywords, search_images


class _FakeLLM:
    def __init__(self, reply="искусственный интеллект"):
        self.reply = reply

    def generate(self, prompt, *, system=None, format=None):
        return self.reply


def test_image_keywords_takes_first_line_clean():
    q = image_keywords(_FakeLLM('  "нейросети" \nлишнее'), "длинный текст про ИИ")
    assert q == "нейросети"


def test_image_keywords_empty_text():
    assert image_keywords(_FakeLLM(), "") == ""


def test_search_stock_pexels_and_pixabay(monkeypatch):
    monkeypatch.setattr(src.config.settings, "pexels_api_key", "k")
    monkeypatch.setattr(src.config.settings, "pixabay_api_key", "k")
    hits = search_images(
        "python",
        source="stock",
        pexels=lambda q: {
            "photos": [
                {"src": {"large2x": "https://p/b.jpg", "medium": "https://p/m.jpg"}}
            ]
        },
        pixabay=lambda q: {
            "hits": [{"largeImageURL": "https://x/b.jpg", "webformatURL": "https://x/w.jpg"}]
        },
    )
    assert {h.source for h in hits} == {"pexels", "pixabay"}
    assert any(h.url == "https://p/b.jpg" and h.thumb == "https://p/m.jpg" for h in hits)


def test_search_web_searxng(monkeypatch):
    hits = search_images(
        "python",
        source="web",
        searx=lambda q: {
            "results": [
                {"img_src": "https://i/x.jpg", "thumbnail_src": "https://i/t.jpg"}
            ]
        },
    )
    assert hits[0].source == "web"
    assert hits[0].url == "https://i/x.jpg" and hits[0].thumb == "https://i/t.jpg"


def test_search_empty_query():
    assert search_images("  ", source="stock") == []


def test_stock_off_without_keys(monkeypatch):
    monkeypatch.setattr(src.config.settings, "pexels_api_key", "")
    monkeypatch.setattr(src.config.settings, "pixabay_api_key", "")
    # без ключей сток молчит, даже если бы пришёл ответ
    assert (
        search_images(
            "x", source="stock", pexels=lambda q: {"photos": [{"src": {"large": "u"}}]}
        )
        == []
    )
