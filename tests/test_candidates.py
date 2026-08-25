from osm_polygon_web_search.candidates import PolygonCandidate, unique_candidates
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
