from pathlib import Path

import pytest

from osm_polygon_web_search.country import country_from_pbf


def test_country_comes_from_the_pbf_basename() -> None:
    assert country_from_pbf(Path("liechtenstein-latest.osm.pbf")) == "Liechtenstein"


def test_country_resolution_does_not_require_filesystem_access() -> None:
    assert country_from_pbf(Path("liechtenstein.osm.pbf")) == "Liechtenstein"


def test_country_resolution_accepts_a_plain_basename() -> None:
    assert country_from_pbf(Path("liechtenstein")) == "Liechtenstein"


def test_country_resolution_turns_hyphenated_basename_into_words() -> None:
    assert country_from_pbf(Path("new-zealand-latest.osm.pbf")) == "New Zealand"


def test_country_resolution_rejects_a_filename_without_a_stem() -> None:
    with pytest.raises(ValueError, match="cannot derive"):
        country_from_pbf(Path(".osm.pbf"))
