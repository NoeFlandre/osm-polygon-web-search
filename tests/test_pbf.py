import json
from types import SimpleNamespace
from typing import get_type_hints

import osmium.filter
import pytest

from osm_polygon_web_search.pbf import is_area_relation, way_geometry


def test_osmium_helpers_have_structural_boundary_types() -> None:
    from osm_polygon_web_search import pbf

    assert get_type_hints(pbf._way_candidate)["obj"] is pbf._WayObject
    relation_geometry_hints = get_type_hints(pbf._relation_geometry)
    assert relation_geometry_hints["factory"] is pbf._GeometryFactory
    assert relation_geometry_hints["obj"] is pbf._AreaObject
    relation_candidate_hints = get_type_hints(pbf._relation_candidate)
    assert relation_candidate_hints["obj"] is pbf._AreaObject
    assert relation_candidate_hints["factory"] is pbf._GeometryFactory
    object_candidate_hints = get_type_hints(pbf._object_candidate)
    assert object_candidate_hints["obj"] is object
    assert object_candidate_hints["factory"] is pbf._GeometryFactory


def test_closed_way_becomes_a_polygon() -> None:
    assert way_geometry(
        [(7.0, 47.0), (7.1, 47.0), (7.1, 47.1), (7.0, 47.0)],
        area_tag=None,
    ) == {
        "type": "Polygon",
        "coordinates": [[(7.0, 47.0), (7.1, 47.0), (7.1, 47.1), (7.0, 47.0)]],
    }


def test_open_way_is_not_a_polygon() -> None:
    assert (
        way_geometry(
            [(7.0, 47.0), (7.1, 47.0), (7.1, 47.1), (7.0, 47.1)],
            area_tag=None,
        )
        is None
    )


def test_area_no_closed_way_is_not_a_polygon() -> None:
    assert (
        way_geometry(
            [(7.0, 47.0), (7.1, 47.0), (7.1, 47.1), (7.0, 47.0)],
            area_tag="no",
        )
        is None
    )


def test_only_area_relations_are_accepted() -> None:
    assert is_area_relation({"type": "multipolygon"})
    assert is_area_relation({"type": "boundary"})
    assert not is_area_relation({"type": "route"})


def test_invalid_closed_rings_are_rejected() -> None:
    assert (
        way_geometry(
            [(7.0, 47.0), (7.0, 47.0), (7.0, 47.0), (7.0, 47.0)],
            area_tag=None,
        )
        is None
    )
    assert (
        way_geometry(
            [(7.0, 47.0), (7.1, 47.0), (float("nan"), 47.1), (7.0, 47.0)],
            area_tag=None,
        )
        is None
    )


class FakeObject:
    def __init__(
        self,
        kind: str,
        *,
        object_id: int,
        tags: dict[str, str],
        nodes: list[tuple[float, float]] | None = None,
        from_way: bool = False,
        geometry: str = "{}",
    ) -> None:
        self.kind = kind
        self.id = object_id
        self.tags = tags
        self.nodes = [SimpleNamespace(lon=lon, lat=lat) for lon, lat in nodes or []]
        self._from_way = from_way
        self._geometry = geometry

    def is_way(self) -> bool:
        return self.kind == "way"

    def is_area(self) -> bool:
        return self.kind == "area"

    def from_way(self) -> bool:
        return self._from_way

    def orig_id(self) -> int:
        return self.id


class FakeWay(FakeObject):
    pass


class FakeArea(FakeObject):
    pass


class FakeProcessor:
    def __init__(self, objects: list[FakeObject]) -> None:
        self.objects = objects
        self.filters = []

    def with_locations(self) -> "FakeProcessor":
        return self

    def with_areas(self) -> "FakeProcessor":
        return self

    def with_filter(self, filt) -> "FakeProcessor":
        self.filters.append(filt)
        return self

    def __iter__(self):
        return iter(self.objects)


class FakeFactory:
    def create_multipolygon(self, obj: object) -> str:
        assert isinstance(obj, FakeObject)
        if obj._geometry == "raise":
            raise RuntimeError("broken relation")
        return obj._geometry


def test_candidate_rejects_an_empty_normalized_name() -> None:
    from osm_polygon_web_search import pbf

    assert pbf._candidate("way", 1, {"name": "  "}, {"type": "Polygon"}) is None


def test_candidate_rejects_a_missing_name() -> None:
    from osm_polygon_web_search import pbf

    assert pbf._candidate("way", 1, {}, {"type": "Polygon"}) is None


def test_candidate_uses_a_supplied_normalized_name() -> None:
    from osm_polygon_web_search import pbf

    candidate = pbf._candidate(
        "way",
        1,
        {"name": "Raw Name"},
        {"type": "Polygon"},
        name_key="precomputed-key",
    )

    assert candidate is not None
    assert candidate.name_key == "precomputed-key"


def test_unnamed_way_is_rejected_before_geometry(monkeypatch) -> None:
    from osm_polygon_web_search import pbf

    monkeypatch.setattr(
        pbf,
        "way_geometry",
        lambda *args, **kwargs: pytest.fail("unnamed way geometry was built"),
    )

    assert (
        pbf._way_candidate(
            FakeWay(
                "way",
                object_id=1,
                tags={},
                nodes=[(7.0, 47.0), (7.1, 47.0), (7.0, 47.0)],
            )
        )
        is None
    )


def test_way_candidate_does_not_normalize_the_name_twice(monkeypatch) -> None:
    from osm_polygon_web_search import pbf

    calls: list[str] = []

    def normalize(value: str) -> str:
        calls.append(value)
        return "precomputed-key"

    monkeypatch.setattr(pbf, "normalize_name", normalize)
    candidate = pbf._way_candidate(
        FakeWay(
            "way",
            object_id=1,
            tags={"name": "Raw Name"},
            nodes=[(7.0, 47.0), (7.1, 47.0), (7.0, 47.1), (7.0, 47.0)],
        )
    )

    assert candidate is not None
    assert candidate.name_key == "precomputed-key"
    assert calls == ["Raw Name"]


def test_unnamed_area_relation_is_rejected_before_geometry(monkeypatch) -> None:
    from osm_polygon_web_search import pbf

    monkeypatch.setattr(
        pbf,
        "_relation_geometry",
        lambda *args, **kwargs: pytest.fail("unnamed relation geometry was built"),
    )

    assert (
        pbf._relation_candidate(
            FakeArea(
                "area",
                object_id=1,
                tags={"type": "multipolygon"},
            ),
            FakeFactory(),
        )
        is None
    )


def test_relation_candidate_does_not_normalize_the_name_twice(monkeypatch) -> None:
    from osm_polygon_web_search import pbf

    calls: list[str] = []

    def normalize(value: str) -> str:
        calls.append(value)
        return "precomputed-key"

    monkeypatch.setattr(pbf, "normalize_name", normalize)
    candidate = pbf._relation_candidate(
        FakeArea(
            "area",
            object_id=1,
            tags={"type": "multipolygon", "name": "Raw Name"},
            geometry=json.dumps({"type": "MultiPolygon", "coordinates": [[[[]]]]}),
        ),
        FakeFactory(),
    )

    assert candidate is not None
    assert candidate.name_key == "precomputed-key"
    assert calls == ["Raw Name"]


def test_scan_pbf_collects_closed_ways_and_valid_area_relations(monkeypatch) -> None:
    from osm_polygon_web_search import pbf

    ring = [(7.0, 47.0), (7.1, 47.0), (7.1, 47.1), (7.0, 47.0)]
    cast_types: list[object] = []
    path_seen = []
    entities_seen = []
    processors = []
    objects = [
        FakeWay("way", object_id=1, tags={"name": "Closed"}, nodes=ring),
        FakeWay("way", object_id=2, tags={"name": "Open"}, nodes=ring[:-1]),
        FakeWay("way", object_id=3, tags={"name": ""}, nodes=ring),
        FakeWay(
            "way",
            object_id=11,
            tags={"name": "Not an area", "area": "no"},
            nodes=ring,
        ),
        FakeObject("relation", object_id=4, tags={"type": "route"}),
        FakeArea("area", object_id=5, tags={"type": "multipolygon"}, from_way=True),
        FakeArea(
            "area",
            object_id=12,
            tags={"type": "multipolygon", "name": "Way-derived area"},
            from_way=True,
            geometry=json.dumps({"type": "MultiPolygon", "coordinates": [[[[]]]]}),
        ),
        FakeArea("area", object_id=6, tags={"type": "route"}),
        FakeArea(
            "area",
            object_id=7,
            tags={"type": "multipolygon", "name": "Broken relation"},
            geometry="raise",
        ),
        FakeArea(
            "area",
            object_id=8,
            tags={"type": "multipolygon", "name": "Empty relation"},
            geometry="[]",
        ),
        FakeArea(
            "area",
            object_id=9,
            tags={"type": "multipolygon", "name": "Named relation"},
            geometry=json.dumps({"type": "MultiPolygon", "coordinates": [[[[]]]]}),
        ),
        FakeArea(
            "area",
            object_id=10,
            tags={"type": "multipolygon"},
            geometry=json.dumps({"type": "MultiPolygon", "coordinates": [[[[]]]]}),
        ),
    ]

    def file_processor(path, *, entities=None):
        path_seen.append(path)
        entities_seen.append(entities)
        processor = FakeProcessor(objects)
        processors.append(processor)
        return processor

    def recording_cast(type_: object, value: object) -> object:
        cast_types.append(type_)
        return value

    monkeypatch.setattr(pbf.osmium, "FileProcessor", file_processor)
    monkeypatch.setattr(pbf, "cast", recording_cast)
    monkeypatch.setattr(
        osmium.filter,
        "EntityFilter",
        lambda entities: ("entity-filter", entities),
    )
    monkeypatch.setattr(
        osmium.filter,
        "KeyFilter",
        lambda *keys: ("key-filter", keys),
    )
    monkeypatch.setattr(pbf.osmium.osm, "Way", FakeWay)
    monkeypatch.setattr(pbf.osmium.osm, "Area", FakeArea)
    monkeypatch.setattr(pbf.osmium.geom, "GeoJSONFactory", FakeFactory)

    candidates = pbf.scan_pbf(__import__("pathlib").Path("fake.osm.pbf"))

    assert path_seen == ["fake.osm.pbf"]
    assert entities_seen == [
        pbf.osmium.osm.osm_entity_bits.NODE | pbf.osmium.osm.osm_entity_bits.WAY
    ]
    assert [item[0] for item in processors[0].filters] == [
        "entity-filter",
        "key-filter",
    ]
    assert processors[0].filters[0][1] == (
        pbf.osmium.osm.osm_entity_bits.WAY | pbf.osmium.osm.osm_entity_bits.AREA
    )
    assert processors[0].filters[1][1] == ("name",)
    assert [(item.osm_type, item.osm_id) for item in candidates] == [
        ("way", 1),
        ("relation", 9),
    ]
    assert set(cast_types) == {
        pbf._AreaObject,
        pbf._GeometryFactory,
        pbf._WayObject,
    }
    assert candidates[0].name_raw == "Closed"
    assert candidates[0].name_key == "closed"
    assert candidates[0].tags == {"name": "Closed"}
    assert candidates[0].geometry["type"] == "Polygon"
    assert candidates[1].name_raw == "Named relation"
    assert candidates[1].name_key == "named relation"
    assert candidates[1].tags["type"] == "multipolygon"
