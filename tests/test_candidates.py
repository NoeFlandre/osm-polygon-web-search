from osm_polygon_web_search.candidates import (
    PolygonCandidate,
    select_candidate,
    unique_candidates,
)
from osm_polygon_web_search.names import normalize_name


def candidate(osm_type: str, osm_id: int, name: str) -> PolygonCandidate:
    return PolygonCandidate(
        osm_type=osm_type,
        osm_id=osm_id,
        name_raw=name,
        name_key=normalize_name(name),
        tags={"name": name},
        geometry={"type": "Polygon", "coordinates": []},
    )


def test_duplicate_names_are_all_excluded_across_ways_and_relations() -> None:
    candidates = [
        candidate("way", 1, "Parking"),
        candidate("relation", 2, " parking "),
        candidate("way", 3, "Unique Meadow"),
    ]

    assert unique_candidates(candidates) == [candidates[2]]


def test_name_normalization_is_case_and_unicode_stable() -> None:
    assert normalize_name("  Cafe\u0301  ") == "café"


def test_candidate_identity_includes_osm_type_and_id() -> None:
    item = candidate("relation", 42, "A place")

    assert item.identity == ("relation", 42)


def test_selection_prefers_physical_landscape_tags_after_uniqueness() -> None:
    building = PolygonCandidate(
        osm_type="way",
        osm_id=1,
        name_raw="A building",
        name_key="a building",
        tags={"name": "A building", "building": "yes"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    meadow = PolygonCandidate(
        osm_type="way",
        osm_id=2,
        name_raw="B meadow",
        name_key="b meadow",
        tags={"name": "B meadow", "landuse": "meadow"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    assert select_candidate([building, meadow]) is meadow


def test_selection_returns_none_for_no_candidates() -> None:
    assert select_candidate([]) is None


def test_selection_prefers_secondary_place_tags_over_unclassified_candidates() -> None:
    unclassified = PolygonCandidate(
        osm_type="way",
        osm_id=1,
        name_raw="Alpha",
        name_key="alpha",
        tags={"name": "Alpha"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    tourism = PolygonCandidate(
        osm_type="way",
        osm_id=2,
        name_raw="Zulu",
        name_key="zulu",
        tags={"name": "Zulu", "tourism": "attraction"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    assert select_candidate([unclassified, tourism]) is tourism


def test_selection_uses_stable_order_for_unclassified_candidates() -> None:
    first = PolygonCandidate(
        osm_type="way",
        osm_id=1,
        name_raw="Zed",
        name_key="zed",
        tags={"name": "Zed"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    second = PolygonCandidate(
        osm_type="way",
        osm_id=2,
        name_raw="Alpha",
        name_key="alpha",
        tags={"name": "Alpha"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    assert select_candidate([first, second]) is second
