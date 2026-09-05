import pytest

import osm_polygon_web_search.queries as query_module
from osm_polygon_web_search.queries import build_query


def test_query_quotes_place_and_country_and_includes_keywords() -> None:
    assert build_query("Alp X", "Liechtenstein", ["geology", "terrain"]) == (
        '"Alp X" "Liechtenstein" (geology OR terrain)'
    )


def test_query_removes_embedded_quotes_from_phrases() -> None:
    assert build_query('A "B"', "Liechtenstein", ["geology"]) == (
        '"A B" "Liechtenstein" geology'
    )


def test_query_requires_at_least_one_nonempty_keyword() -> None:
    with pytest.raises(ValueError, match="^at least one search keyword is required$"):
        build_query("Alp X", "Liechtenstein", ["", "  "])


def test_query_quotes_multiword_keywords() -> None:
    assert build_query("Alp X", "Liechtenstein", ["land cover"]) == (
        '"Alp X" "Liechtenstein" "land cover"'
    )


def test_query_variant_catalog_contains_v1_to_v9_without_description() -> None:
    assert query_module.QUERY_VARIANTS == (
        ("v1", "land cover"),
        ("v2", "land use"),
        ("v3", "vegetation"),
        ("v4", "terrain"),
        ("v5", "soil surface"),
        ("v6", "ecosystem"),
        ("v7", "physical geography"),
        ("v8", "buildings infrastructure"),
        ("v9", "landscape environment"),
    )


def test_build_variant_queries_preserves_variant_identity_and_place_scope() -> None:
    assert query_module.build_variant_queries("Alp X", "Liechtenstein") == [
        {
            "id": "v1",
            "keyword": "land cover",
            "query": '"Alp X" "Liechtenstein" "land cover"',
        },
        {
            "id": "v2",
            "keyword": "land use",
            "query": '"Alp X" "Liechtenstein" "land use"',
        },
        {
            "id": "v3",
            "keyword": "vegetation",
            "query": '"Alp X" "Liechtenstein" vegetation',
        },
        {
            "id": "v4",
            "keyword": "terrain",
            "query": '"Alp X" "Liechtenstein" terrain',
        },
        {
            "id": "v5",
            "keyword": "soil surface",
            "query": '"Alp X" "Liechtenstein" "soil surface"',
        },
        {
            "id": "v6",
            "keyword": "ecosystem",
            "query": '"Alp X" "Liechtenstein" ecosystem',
        },
        {
            "id": "v7",
            "keyword": "physical geography",
            "query": '"Alp X" "Liechtenstein" "physical geography"',
        },
        {
            "id": "v8",
            "keyword": "buildings infrastructure",
            "query": '"Alp X" "Liechtenstein" "buildings infrastructure"',
        },
        {
            "id": "v9",
            "keyword": "landscape environment",
            "query": '"Alp X" "Liechtenstein" "landscape environment"',
        },
    ]
