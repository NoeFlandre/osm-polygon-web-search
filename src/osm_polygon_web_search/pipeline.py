import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .candidates import PolygonCandidate, unique_candidates
from .country import country_from_pbf
from .data_root import data_root
from .fetch import PageFetcher, PageProvider
from .pbf import scan_pbf
from .queries import QUERY_VARIANTS, build_query, build_variant_queries
from .relevance import find_evidence
from .search import BraveSearchProvider, SearchProvider

DEFAULT_PBF = data_root() / "liechtenstein-latest.osm.pbf"
DEFAULT_KEYWORDS = ("land cover",)


def ensure_data_path(path: Path) -> Path:
    """Return a path only when it is inside the configured data root."""
    root = data_root().resolve()
    candidate = path.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"path must stay under the configured data root: {path}"
        ) from error
    return candidate


def _candidate_record(candidate: PolygonCandidate) -> dict[str, Any]:
    return {
        "identity": [candidate.osm_type, candidate.osm_id],
        "name_raw": candidate.name_raw,
        "name_key": candidate.name_key,
        "tags": dict(candidate.tags),
        "geometry": dict(candidate.geometry),
    }


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


def build_plan(
    pbf_path: Path,
    *,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
) -> dict[str, Any]:
    candidates = scan_pbf(pbf_path)
    unique = unique_candidates(candidates)
    selected = select_candidate(unique)
    country = country_from_pbf(pbf_path)
    query = (
        build_query(selected.name_raw, country, keywords)
        if selected is not None
        else None
    )
    return {
        "pbf": str(pbf_path),
        "country": country,
        "candidate_count": len(candidates),
        "unique_candidate_count": len(unique),
        "selected": _candidate_record(selected) if selected is not None else None,
        "query": query,
    }


def build_variant_plan(
    pbf_path: Path,
    *,
    variants: Sequence[tuple[str, str]] = QUERY_VARIANTS,
) -> dict[str, Any]:
    """Build one candidate plan carrying the approved query variants."""
    if not variants:
        raise ValueError("at least one query variant is required")

    plan = build_plan(pbf_path, keywords=(variants[0][1],))
    selected = plan["selected"]
    plan["query"] = None
    plan["query_variants"] = (
        build_variant_queries(selected["name_raw"], plan["country"], variants)
        if isinstance(selected, dict)
        else []
    )
    return plan


def _search_records(
    plan: dict[str, Any],
    *,
    provider: SearchProvider,
    fetcher: PageProvider,
    result_count: int,
) -> list[dict[str, Any]]:
    query = plan["query"]
    selected = plan["selected"]
    if not isinstance(query, str) or not isinstance(selected, dict):
        return []

    results: list[dict[str, Any]] = []
    for result in provider.search(query, count=result_count):
        page = fetcher.fetch(result.url)
        evidence = find_evidence(page.text or "", place_name=selected["name_raw"])
        results.append(
            {
                "result": asdict(result),
                "page": {"url": page.url, "status": page.status},
                "evidence": [asdict(item) for item in evidence],
            }
        )
    return results


def _search_variant_records(
    plan: dict[str, Any],
    *,
    provider: SearchProvider,
    fetcher: PageProvider,
    result_count: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for variant in plan["query_variants"]:
        variant_plan = {**plan, "query": variant["query"]}
        records.append(
            {
                "id": variant["id"],
                "keyword": variant["keyword"],
                "query": variant["query"],
                "results": _search_records(
                    variant_plan,
                    provider=provider,
                    fetcher=fetcher,
                    result_count=result_count,
                ),
            }
        )
    return records


def run_poc(
    pbf_path: Path,
    *,
    output_dir: Path,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
    search: bool = False,
    result_count: int = 5,
    all_variants: bool = False,
) -> Path:
    validated_pbf = ensure_data_path(pbf_path)
    plan = (
        build_variant_plan(validated_pbf)
        if all_variants
        else build_plan(validated_pbf, keywords=keywords)
    )
    if search:
        provider = BraveSearchProvider()
        fetcher = PageFetcher()
        if all_variants:
            plan["variant_results"] = _search_variant_records(
                plan,
                provider=provider,
                fetcher=fetcher,
                result_count=result_count,
            )
        else:
            plan["results"] = _search_records(
                plan,
                provider=provider,
                fetcher=fetcher,
                result_count=result_count,
            )

    destination = ensure_data_path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "run.json"
    output_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return output_path
