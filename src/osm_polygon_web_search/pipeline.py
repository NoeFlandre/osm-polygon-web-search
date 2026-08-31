import json
from collections.abc import Iterable, Mapping, MutableMapping, MutableSet, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .candidates import PolygonCandidate, select_candidate, unique_candidates
from .country import country_from_pbf
from .data_root import data_root, ensure_data_path
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
from .search import BraveSearchProvider, SearchProvider, SearchResult

DEFAULT_PBF = data_root() / "liechtenstein-latest.osm.pbf"
DEFAULT_KEYWORDS = ("land cover",)
DEFAULT_RESULT_COUNT = 10


@dataclass(frozen=True, slots=True)
class _SelectionPlan:
    pbf_path: Path
    country: str
    candidate_count: int
    unique_candidate_count: int
    selected: PolygonCandidate | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "pbf": str(self.pbf_path),
            "country": self.country,
            "candidate_count": self.candidate_count,
            "unique_candidate_count": self.unique_candidate_count,
            "selected": (
                _candidate_record(self.selected) if self.selected is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class _QueryVariant:
    id: str
    keyword: str
    query: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "keyword": self.keyword, "query": self.query}


@dataclass(frozen=True, slots=True)
class _PipelinePlan:
    selection: _SelectionPlan
    query: str | None
    query_variants: tuple[_QueryVariant, ...] | None = None

    def as_dict(self) -> dict[str, Any]:
        plan = self.selection.as_dict()
        plan["query"] = self.query
        if self.query_variants is not None:
            plan["query_variants"] = [
                variant.as_dict() for variant in self.query_variants
            ]
        return plan


def _candidate_record(candidate: PolygonCandidate) -> dict[str, Any]:
    return {
        "identity": [candidate.osm_type, candidate.osm_id],
        "name_raw": candidate.name_raw,
        "name_key": candidate.name_key,
        "tags": dict(candidate.tags),
        "geometry": dict(candidate.geometry),
    }


def _build_selection_plan(pbf_path: Path) -> _SelectionPlan:
    candidates = scan_pbf(pbf_path)
    unique = unique_candidates(candidates)
    selected = select_candidate(unique)
    country = country_from_pbf(pbf_path)
    return _SelectionPlan(
        pbf_path=pbf_path,
        country=country,
        candidate_count=len(candidates),
        unique_candidate_count=len(unique),
        selected=selected,
    )


def _build_plan(
    pbf_path: Path,
    *,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
) -> _PipelinePlan:
    selection = _build_selection_plan(pbf_path)
    query = (
        build_query(selection.selected.name_raw, selection.country, keywords)
        if selection.selected is not None
        else None
    )
    return _PipelinePlan(selection=selection, query=query)


def _build_variant_plan(
    pbf_path: Path,
    *,
    variants: Sequence[tuple[str, str]] = QUERY_VARIANTS,
) -> _PipelinePlan:
    if not variants:
        raise ValueError("at least one query variant is required")

    selection = _build_selection_plan(pbf_path)
    query_variants = ()
    if selection.selected is not None:
        query_variants = tuple(
            _QueryVariant(
                id=variant["id"],
                keyword=variant["keyword"],
                query=variant["query"],
            )
            for variant in build_variant_queries(
                selection.selected.name_raw,
                selection.country,
                variants,
            )
        )
    return _PipelinePlan(
        selection=selection,
        query=None,
        query_variants=query_variants,
    )


def build_plan(
    pbf_path: Path,
    *,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
) -> dict[str, Any]:
    return _build_plan(pbf_path, keywords=keywords).as_dict()


def build_variant_plan(
    pbf_path: Path,
    *,
    variants: Sequence[tuple[str, str]] = QUERY_VARIANTS,
) -> dict[str, Any]:
    """Build one candidate plan carrying the approved query variants."""
    return _build_variant_plan(pbf_path, variants=variants).as_dict()


def _serialize_search_results(
    search_results: Sequence[SearchResult],
    pages: Mapping[str, FetchedPage],
    *,
    place_name: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in search_results:
        page = pages.get(result.url)
        if page is None:
            continue
        evidence = find_evidence(page.text or "", place_name=place_name)
        records.append(
            {
                "result": asdict(result),
                "page": {"url": page.url, "status": page.status},
                "evidence": [asdict(item) for item in evidence],
            }
        )
    return records


def _new_search_results(
    search_results: Sequence[SearchResult],
    seen_urls: MutableSet[str] | None,
) -> list[SearchResult]:
    if seen_urls is None:
        return list(search_results)

    new_results: list[SearchResult] = []
    for result in search_results:
        if result.url in seen_urls:
            continue
        seen_urls.add(result.url)
        new_results.append(result)
    return new_results


def _search_records(
    plan: _PipelinePlan,
    *,
    provider: SearchProvider,
    fetcher: PageProvider,
    result_count: int,
    page_cache: MutableMapping[str, FetchedPage] | None = None,
    seen_urls: MutableSet[str] | None = None,
) -> list[dict[str, Any]]:
    query = plan.query
    selected = plan.selection.selected
    if query is None or selected is None:
        return []

    search_results = _new_search_results(
        provider.search(query, count=result_count),
        seen_urls,
    )
    pages = fetch_pages(
        fetcher,
        [result.url for result in search_results],
        cache=page_cache,
        max_workers=(
            1 if getattr(fetcher, "min_delay_seconds", 0.0) > 0 else PAGE_FETCH_WORKERS
        ),
    )
    return _serialize_search_results(
        search_results,
        pages,
        place_name=selected.name_raw,
    )


def _search_variant_records(
    plan: _PipelinePlan,
    *,
    provider: SearchProvider,
    fetcher: PageProvider,
    result_count: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page_cache: dict[str, FetchedPage] = {}
    seen_urls: set[str] = set()
    if plan.query_variants is None:
        return records

    for variant in plan.query_variants:
        variant_plan = replace(plan, query=variant.query, query_variants=None)
        records.append(
            {
                "id": variant.id,
                "keyword": variant.keyword,
                "query": variant.query,
                "results": _search_records(
                    variant_plan,
                    provider=provider,
                    fetcher=fetcher,
                    result_count=result_count,
                    page_cache=page_cache,
                    seen_urls=seen_urls,
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
    result_count: int = DEFAULT_RESULT_COUNT,
    all_variants: bool = False,
) -> Path:
    validated_pbf = ensure_data_path(pbf_path)
    runtime_plan = (
        _build_variant_plan(validated_pbf)
        if all_variants
        else _build_plan(validated_pbf, keywords=keywords)
    )
    plan = runtime_plan.as_dict()
    if search:
        provider = BraveSearchProvider()
        fetcher = PageFetcher()
        if all_variants:
            plan["variant_results"] = _search_variant_records(
                runtime_plan,
                provider=provider,
                fetcher=fetcher,
                result_count=result_count,
            )
        else:
            plan["results"] = _search_records(
                runtime_plan,
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
