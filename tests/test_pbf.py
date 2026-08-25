import json
from types import SimpleNamespace

from osm_polygon_web_search.pbf import is_area_relation, way_geometry


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

    def with_locations(self) -> "FakeProcessor":
        return self

    def with_areas(self) -> "FakeProcessor":
        return self

    def __iter__(self):
        return iter(self.objects)


class FakeFactory:
    def create_multipolygon(self, obj: FakeObject) -> str:
        if obj._geometry == "raise":
            raise RuntimeError("broken relation")
        return obj._geometry


def test_scan_pbf_collects_closed_ways_and_valid_area_relations(monkeypatch) -> None:
    from osm_polygon_web_search import pbf

    ring = [(7.0, 47.0), (7.1, 47.0), (7.1, 47.1), (7.0, 47.0)]
    path_seen = []
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
        FakeArea("area", object_id=7, tags={"type": "multipolygon"}, geometry="raise"),
        FakeArea("area", object_id=8, tags={"type": "multipolygon"}, geometry="[]"),
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

    def file_processor(path):
        path_seen.append(path)
        return FakeProcessor(objects)

    monkeypatch.setattr(pbf.osmium, "FileProcessor", file_processor)
    monkeypatch.setattr(pbf.osmium.osm, "Way", FakeWay)
    monkeypatch.setattr(pbf.osmium.osm, "Area", FakeArea)
    monkeypatch.setattr(pbf.osmium.geom, "GeoJSONFactory", FakeFactory)

    candidates = pbf.scan_pbf(__import__("pathlib").Path("fake.osm.pbf"))

    assert path_seen == ["fake.osm.pbf"]
    assert [(item.osm_type, item.osm_id) for item in candidates] == [
        ("way", 1),
        ("relation", 9),
    ]
    assert candidates[0].name_raw == "Closed"
    assert candidates[0].name_key == "closed"
    assert candidates[0].tags == {"name": "Closed"}
    assert candidates[0].geometry["type"] == "Polygon"
    assert candidates[1].name_raw == "Named relation"
    assert candidates[1].name_key == "named relation"
    assert candidates[1].tags["type"] == "multipolygon"
