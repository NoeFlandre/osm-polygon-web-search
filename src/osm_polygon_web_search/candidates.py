from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolygonCandidate:
    osm_type: str
    osm_id: int
    name_raw: str
    name_key: str
    tags: Mapping[str, str]
    geometry: Mapping[str, object]

    @property
    def identity(self) -> tuple[str, int]:
        return self.osm_type, self.osm_id


_PRIMARY_PHYSICAL_TAGS = (
    "natural",
    "water",
    "landuse",
    "geological",
)
_SECONDARY_PLACE_TAGS = ("leisure", "tourism", "man_made", "building")


def select_candidate(candidates: list[PolygonCandidate]) -> PolygonCandidate | None:
    if not candidates:
        return None

    def sort_key(item: PolygonCandidate) -> tuple[object, ...]:
        if any(key in item.tags for key in _PRIMARY_PHYSICAL_TAGS):
            tag_priority = 0
        elif any(key in item.tags for key in _SECONDARY_PLACE_TAGS):
            tag_priority = 1
        else:
            tag_priority = 2
        return (
            tag_priority,
            len(item.name_raw) < 4,
            item.name_key,
            item.osm_type,
            item.osm_id,
        )

    return min(candidates, key=sort_key)


def unique_candidates(
    candidates: list[PolygonCandidate],
) -> list[PolygonCandidate]:
    """Keep candidates whose normalized name occurs exactly once."""
    counts = Counter(candidate.name_key for candidate in candidates)
    return [candidate for candidate in candidates if counts[candidate.name_key] == 1]
