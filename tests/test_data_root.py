from pathlib import Path

from osm_polygon_web_search.data_root import data_root


EXPECTED_DATA_ROOT = Path("/Volumes/Seagate M3/projects/osm-polygon-web-search")


def test_data_root_returns_the_canonical_seagate_path() -> None:
    assert data_root() == EXPECTED_DATA_ROOT
