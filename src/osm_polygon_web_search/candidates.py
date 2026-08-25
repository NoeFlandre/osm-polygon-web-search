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


def unique_candidates(
    candidates: list[PolygonCandidate],
) -> list[PolygonCandidate]:
    """Keep candidates whose normalized name occurs exactly once."""
    counts = Counter(candidate.name_key for candidate in candidates)
    return [candidate for candidate in candidates if counts[candidate.name_key] == 1]
