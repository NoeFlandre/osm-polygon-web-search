import pytest

from osm_polygon_web_search.queries import build_query


def test_query_quotes_place_and_country_and_includes_keywords() -> None:
    assert build_query("Alp X", "Liechtenstein", ["geology", "terrain"]) == (
        '"Alp X" "Liechtenstein" (geology OR terrain)'
    )


def test_query_removes_embedded_quotes_from_phrases() -> None:
    assert build_query('A "B"', "Liechtenstein", ["geology"]) == (
        '"A B" "Liechtenstein" (geology)'
    )


def test_query_requires_at_least_one_nonempty_keyword() -> None:
    with pytest.raises(ValueError, match="^at least one search keyword is required$"):
        build_query("Alp X", "Liechtenstein", ["", "  "])


def test_query_quotes_multiword_keywords() -> None:
    assert build_query("Alp X", "Liechtenstein", ["land cover"]) == (
        '"Alp X" "Liechtenstein" ("land cover")'
    )
