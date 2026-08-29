import json
from collections.abc import Iterable, MutableMapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .candidates import PolygonCandidate, select_candidate, unique_candidates
from .country import country_from_pbf
from .data_root import data_root
from .fetch import (
    PAGE_FETCH_WORKERS,
    FetchedPage,
    PageFetcher,
    PageProvider,
    fetch_pages,
)
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
    page_cache: MutableMapping[str, FetchedPage] | None = None,
) -> list[dict[str, Any]]:
    query = plan["query"]
    selected = plan["selected"]
    if not isinstance(query, str) or not isinstance(selected, dict):
        return []

    search_results = list(provider.search(query, count=result_count))
    pages = fetch_pages(
        fetcher,
        [result.url for result in search_results],
        cache=page_cache,
        max_workers=(
            1 if getattr(fetcher, "min_delay_seconds", 0.0) > 0 else PAGE_FETCH_WORKERS
        ),
    )
    results: list[dict[str, Any]] = []
    for result in search_results:
        page = pages.get(result.url)
        if page is None:
            continue
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
    page_cache: dict[str, FetchedPage] = {}
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
                    page_cache=page_cache,
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
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return output_path
