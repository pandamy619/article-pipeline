from src.config import Settings


def test_split_basic():
    assert Settings._split("a,b ,  c") == ["a", "b", "c"]


def test_split_empty():
    assert Settings._split("") == []


def test_split_strips_inline_comment():
    # инлайн-комментарий после значения не должен попасть в список
    assert Settings._split("programming,python   # коммент") == ["programming", "python"]


def test_split_drops_comment_only_value():
    # если в значение целиком уехал комментарий из .env — получаем пустой список
    assert Settings._split("# имена без r/, напр. learnprogramming") == []
