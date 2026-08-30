from pathlib import Path

from osm_polygon_web_search.data_root import data_root, ensure_data_path

EXPECTED_DATA_ROOT = Path("/Volumes/Seagate M3/projects/osm-polygon-web-search")


def test_data_root_returns_the_canonical_seagate_path() -> None:
    assert data_root() == EXPECTED_DATA_ROOT


def test_data_root_owns_the_seagate_path_boundary() -> None:
    assert ensure_data_path(EXPECTED_DATA_ROOT / "runs") == (
        EXPECTED_DATA_ROOT / "runs"
    )
