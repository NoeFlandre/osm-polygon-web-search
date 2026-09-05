import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol, cast

import osmium
import osmium.filter
import osmium.geom
import osmium.osm

from .candidates import PolygonCandidate
from .names import normalize_name

Coordinate = tuple[float, float]


class _CoordinateNode(Protocol):
    @property
    def lon(self) -> float: ...

    @property
    def lat(self) -> float: ...


class _WayObject(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def tags(self) -> Mapping[str, str]: ...

    @property
    def nodes(self) -> Iterable[_CoordinateNode]: ...


class _AreaObject(Protocol):
    @property
    def tags(self) -> Mapping[str, str]: ...

    def from_way(self) -> bool: ...

    def orig_id(self) -> int: ...


class _GeometryFactory(Protocol):
    def create_multipolygon(self, obj: _AreaObject, /) -> str: ...


def way_geometry(
    nodes: Iterable[Coordinate],
    *,
    area_tag: str | None,
) -> dict[str, object] | None:
    """Build a minimal GeoJSON Polygon from a closed way ring."""
    if area_tag == "no":
        return None

    coordinates = [(float(lon), float(lat)) for lon, lat in nodes]
    if len(coordinates) < 4 or coordinates[0] != coordinates[-1]:
        return None
    if len(set(coordinates[:-1])) < 3:
        return None
    if not all(math.isfinite(value) for point in coordinates for value in point):
        return None
    return {"type": "Polygon", "coordinates": [coordinates]}


def is_area_relation(tags: Mapping[str, str]) -> bool:
    return tags.get("type") in {"multipolygon", "boundary"}


def _candidate(
    osm_type: str,
    osm_id: int,
    tags: Mapping[str, str],
    geometry: Mapping[str, object],
    *,
    name_key: str,
) -> PolygonCandidate:
    return PolygonCandidate(
        osm_type=osm_type,
        osm_id=osm_id,
        name_raw=tags["name"],
        name_key=name_key,
        tags=dict(tags),
        geometry=dict(geometry),
    )


def _way_candidate(obj: _WayObject) -> PolygonCandidate | None:
    name_key = normalize_name(obj.tags.get("name", ""))
    if not name_key:
        return None
    geometry = way_geometry(
        ((node.lon, node.lat) for node in obj.nodes),
        area_tag=obj.tags.get("area"),
    )
    return (
        _candidate("way", obj.id, obj.tags, geometry, name_key=name_key)
        if geometry is not None
        else None
    )


def _relation_geometry(
    factory: _GeometryFactory,
    obj: _AreaObject,
) -> dict[str, object] | None:
    try:
        geometry = json.loads(factory.create_multipolygon(obj))
    except (TypeError, ValueError, RuntimeError):
        return None
    if not isinstance(geometry, dict) or not geometry.get("coordinates"):
        return None
    return geometry


def _relation_candidate(
    obj: _AreaObject,
    factory: _GeometryFactory,
) -> PolygonCandidate | None:
    if obj.from_way():
        return None
    tags = dict(obj.tags)
    if not is_area_relation(tags):
        return None
    name_key = normalize_name(tags.get("name", ""))
    if not name_key:
        return None
    geometry = _relation_geometry(factory, obj)
    if geometry is None:
        return None
    return _candidate("relation", obj.orig_id(), tags, geometry, name_key=name_key)


def _object_candidate(
    obj: object,
    factory: _GeometryFactory,
) -> PolygonCandidate | None:
    if isinstance(obj, osmium.osm.Way):
        return _way_candidate(cast(_WayObject, obj))
    if isinstance(obj, osmium.osm.Area):
        return _relation_candidate(cast(_AreaObject, obj), factory)
    return None


def scan_pbf(path: Path) -> list[PolygonCandidate]:
    """Return named closed ways and assembled named area relations from a PBF."""
    factory = cast(_GeometryFactory, osmium.geom.GeoJSONFactory())
    candidates: list[PolygonCandidate] = []
    processor = (
        osmium.FileProcessor(
            str(path),
            entities=osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY,
        )
        .with_locations()
        .with_areas()
    )
    processor.with_filter(
        osmium.filter.EntityFilter(
            osmium.osm.osm_entity_bits.WAY | osmium.osm.osm_entity_bits.AREA
        )
    )
    processor.with_filter(osmium.filter.KeyFilter("name"))

    for obj in processor:
        item = _object_candidate(obj, factory)
        if item is not None:
            candidates.append(item)

    return candidates
