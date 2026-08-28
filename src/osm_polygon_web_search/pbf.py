import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import osmium
import osmium.geom
import osmium.osm

from .candidates import PolygonCandidate
from .names import normalize_name

Coordinate = tuple[float, float]


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
) -> PolygonCandidate | None:
    name = tags.get("name", "")
    name_key = normalize_name(name)
    if not name_key:
        return None
    return PolygonCandidate(
        osm_type=osm_type,
        osm_id=osm_id,
        name_raw=name,
        name_key=name_key,
        tags=dict(tags),
        geometry=dict(geometry),
    )


def _way_candidate(obj: Any) -> PolygonCandidate | None:
    geometry = way_geometry(
        ((node.lon, node.lat) for node in obj.nodes),
        area_tag=obj.tags.get("area"),
    )
    return (
        _candidate("way", obj.id, dict(obj.tags), geometry)
        if geometry is not None
        else None
    )


def _relation_geometry(factory: Any, obj: Any) -> dict[str, object] | None:
    try:
        geometry = json.loads(factory.create_multipolygon(obj))
    except (TypeError, ValueError, RuntimeError):
        return None
    if not isinstance(geometry, dict) or not geometry.get("coordinates"):
        return None
    return geometry


def _relation_candidate(obj: Any, factory: Any) -> PolygonCandidate | None:
    if obj.from_way():
        return None
    tags = dict(obj.tags)
    if not is_area_relation(tags):
        return None
    geometry = _relation_geometry(factory, obj)
    if geometry is None:
        return None
    return _candidate("relation", obj.orig_id(), tags, geometry)


def _object_candidate(obj: Any, factory: Any) -> PolygonCandidate | None:
    if isinstance(obj, osmium.osm.Way):
        return _way_candidate(obj)
    if isinstance(obj, osmium.osm.Area):
        return _relation_candidate(obj, factory)
    return None


def scan_pbf(path: Path) -> list[PolygonCandidate]:
    """Return named closed ways and assembled named area relations from a PBF."""
    factory = osmium.geom.GeoJSONFactory()
    candidates: list[PolygonCandidate] = []

    for obj in osmium.FileProcessor(str(path)).with_locations().with_areas():
        item = _object_candidate(obj, factory)
        if item is not None:
            candidates.append(item)

    return candidates
