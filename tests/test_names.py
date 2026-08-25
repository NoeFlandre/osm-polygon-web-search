from osm_polygon_web_search.names import normalize_name


def test_name_normalization_collapses_all_whitespace_to_single_spaces() -> None:
    assert normalize_name("  Alpe\t  Vermales  ") == "alpe vermales"
