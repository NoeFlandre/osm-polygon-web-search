import re
from dataclasses import dataclass

from .names import normalize_name

CRITERION_TERMS: dict[str, tuple[str, ...]] = {
    "land_use_land_cover": (
        "land cover",
        "land use",
        "agriculture",
        "farmland",
        "urban",
    ),
    "soil_surface": (
        "soil",
        "surface",
        "limestone",
        "rock",
        "sand",
        "gravel",
        "stone",
    ),
    "vegetation_ecosystem": (
        "vegetation",
        "ecosystem",
        "forest",
        "woodland",
        "grassland",
        "wetland",
        "habitat",
    ),
    "terrain_geomorphology": (
        "terrain",
        "geomorphology",
        "geology",
        "valley",
        "ridge",
        "slope",
        "formation",
    ),
    "buildings_infrastructure": (
        "building",
        "infrastructure",
        "bridge",
        "road",
        "railway",
    ),
    "physical_setting": (
        "located",
        "position",
        "extent",
        "landscape",
        "geographic",
    ),
}


@dataclass(frozen=True, slots=True)
class Evidence:
    sentence: str
    criteria: tuple[str, ...]


def _contains_term(sentence: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE) is not None


def find_evidence(text: str, *, place_name: str) -> list[Evidence]:
    """Find sentences that mention the place and describe a target criterion."""
    place_key = normalize_name(place_name)
    if not place_key:
        return []

    evidence: list[Evidence] = []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sentence in sentences:
        if place_key not in normalize_name(sentence):
            continue
        criteria = tuple(
            criterion
            for criterion, terms in CRITERION_TERMS.items()
            if any(_contains_term(sentence, term) for term in terms)
        )
        if criteria:
            evidence.append(Evidence(sentence=sentence.strip(), criteria=criteria))
    return evidence
