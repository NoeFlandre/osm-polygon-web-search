import json
from pathlib import Path
from typing import cast

import pytest

import osm_polygon_web_search.pipeline as pipeline_module
from osm_polygon_web_search.candidates import PolygonCandidate, select_candidate
from osm_polygon_web_search.data_root import (
    ensure_data_path as data_root_ensure_data_path,
)
from osm_polygon_web_search.fetch import FetchedPage, PageFetchError, PageProvider
from osm_polygon_web_search.names import normalize_name
from osm_polygon_web_search.pipeline import (
    _search_records,
    build_plan,
    ensure_data_path,
    run_poc,
)
from osm_polygon_web_search.search import SearchProvider, SearchResult


def _make_pipeline_plan(
    query: str | None,
    *,
    place_name: str | None = "Alp X",
    query_variants: tuple[pipeline_module._QueryVariant, ...] | None = None,
) -> pipeline_module._PipelinePlan:
    candidate = (
        None
        if place_name is None
        else PolygonCandidate(
            osm_type="way",
            osm_id=42,
            name_raw=place_name,
            name_key=normalize_name(place_name),
            tags={"name": place_name},
            geometry={"type": "Polygon", "coordinates": []},
        )
    )
    selection = pipeline_module._SelectionPlan(
        pbf_path=Path("liechtenstein-latest.osm.pbf"),
        country="Liechtenstein",
        candidate_count=1 if candidate is not None else 0,
        unique_candidate_count=1 if candidate is not None else 0,
        selected=candidate,
    )
    return pipeline_module._PipelinePlan(
        selection=selection,
        query=query,
        query_variants=query_variants,
    )


def test_pipeline_reexports_select_candidate() -> None:
    assert pipeline_module.select_candidate is select_candidate


def test_pipeline_preserves_the_legacy_path_boundary_alias() -> None:
    assert pipeline_module.ensure_data_path is data_root_ensure_data_path


def test_selection_plan_serializes_the_existing_selection_shape() -> None:
    candidate = PolygonCandidate(
        osm_type="way",
        osm_id=42,
        name_raw="Alp X",
        name_key=normalize_name("Alp X"),
        tags={"name": "Alp X"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    selection = pipeline_module._SelectionPlan(
        pbf_path=Path("liechtenstein-latest.osm.pbf"),
        country="Liechtenstein",
        candidate_count=3,
        unique_candidate_count=1,
        selected=candidate,
    )

    assert selection.as_dict() == {
        "pbf": "liechtenstein-latest.osm.pbf",
        "country": "Liechtenstein",
        "candidate_count": 3,
        "unique_candidate_count": 1,
        "selected": {
            "identity": ["way", 42],
            "name_raw": "Alp X",
            "name_key": "alp x",
            "tags": {"name": "Alp X"},
            "geometry": {"type": "Polygon", "coordinates": []},
        },
    }


def test_pipeline_plan_serializes_typed_query_state() -> None:
    candidate = PolygonCandidate(
        osm_type="way",
        osm_id=42,
        name_raw="Alp X",
        name_key=normalize_name("Alp X"),
        tags={"name": "Alp X"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    selection = pipeline_module._SelectionPlan(
        pbf_path=Path("liechtenstein-latest.osm.pbf"),
        country="Liechtenstein",
        candidate_count=3,
        unique_candidate_count=1,
        selected=candidate,
    )
    plan = pipeline_module._PipelinePlan(
        selection=selection,
        query=None,
        query_variants=(
            pipeline_module._QueryVariant(
                id="v1",
                keyword="land cover",
                query='"Alp X" "Liechtenstein" "land cover"',
            ),
        ),
    )

    assert plan.as_dict() == {
        "pbf": "liechtenstein-latest.osm.pbf",
        "country": "Liechtenstein",
        "candidate_count": 3,
        "unique_candidate_count": 1,
        "selected": {
            "identity": ["way", 42],
            "name_raw": "Alp X",
            "name_key": "alp x",
            "tags": {"name": "Alp X"},
            "geometry": {"type": "Polygon", "coordinates": []},
        },
        "query": None,
        "query_variants": [
            {
                "id": "v1",
                "keyword": "land cover",
                "query": '"Alp X" "Liechtenstein" "land cover"',
            }
        ],
    }


def test_build_plan_selects_one_unique_candidate_without_a_provider(
    monkeypatch,
) -> None:
    candidate = PolygonCandidate(
        osm_type="way",
        osm_id=42,
        name_raw="Alp X",
        name_key=normalize_name("Alp X"),
        tags={"name": "Alp X"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    scanned_paths = []

    def scan(path):
        scanned_paths.append(path)
        return [candidate]

    monkeypatch.setattr("osm_polygon_web_search.pipeline.scan_pbf", scan)

    pbf_path = Path(
        "/Volumes/Seagate M3/projects/osm-polygon-web-search/"
        "liechtenstein-latest.osm.pbf"
    )
    plan = build_plan(pbf_path, keywords=("terrain",))

    assert scanned_paths == [pbf_path]
    assert plan["country"] == "Liechtenstein"
    assert plan["candidate_count"] == 1
    assert plan["unique_candidate_count"] == 1
    assert plan["pbf"] == str(
        Path(
            "/Volumes/Seagate M3/projects/osm-polygon-web-search/"
            "liechtenstein-latest.osm.pbf"
        )
    )
    assert plan["selected"] == {
        "identity": ["way", 42],
        "name_raw": "Alp X",
        "name_key": "alp x",
        "tags": {"name": "Alp X"},
        "geometry": {"type": "Polygon", "coordinates": []},
    }
    assert plan["query"] == '"Alp X" "Liechtenstein" terrain'


def test_private_plan_builders_return_typed_pipeline_plans(monkeypatch) -> None:
    candidate = PolygonCandidate(
        osm_type="way",
        osm_id=42,
        name_raw="Alp X",
        name_key=normalize_name("Alp X"),
        tags={"name": "Alp X"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    monkeypatch.setattr(
        pipeline_module,
        "scan_pbf",
        lambda path: [candidate],
    )

    ordinary = pipeline_module._build_plan(
        Path("liechtenstein-latest.osm.pbf"),
        keywords=("terrain",),
    )
    variants = pipeline_module._build_variant_plan(
        Path("liechtenstein-latest.osm.pbf"),
        variants=(("v1", "land cover"),),
    )

    assert isinstance(ordinary, pipeline_module._PipelinePlan)
    assert ordinary.query == '"Alp X" "Liechtenstein" terrain'
    assert ordinary.query_variants is None
    assert isinstance(variants, pipeline_module._PipelinePlan)
    assert variants.query is None
    assert variants.query_variants is not None
    assert variants.query_variants[0].keyword == "land cover"


def test_build_variant_plan_lists_all_queries_without_the_old_baseline(
    monkeypatch,
) -> None:
    candidate = PolygonCandidate(
        osm_type="way",
        osm_id=42,
        name_raw="Alp X",
        name_key=normalize_name("Alp X"),
        tags={"name": "Alp X"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.scan_pbf",
        lambda path: [candidate],
    )

    plan = pipeline_module.build_variant_plan(
        Path(
            "/Volumes/Seagate M3/projects/osm-polygon-web-search/"
            "liechtenstein-latest.osm.pbf"
        )
    )

    assert plan["query"] is None
    assert [item["id"] for item in plan["query_variants"]] == [
        f"v{number}" for number in range(1, 10)
    ]
    assert all("description" not in item["query"] for item in plan["query_variants"])


def test_build_variant_plan_builds_only_the_requested_variant_queries(
    monkeypatch,
) -> None:
    candidate = PolygonCandidate(
        osm_type="way",
        osm_id=42,
        name_raw="Alp X",
        name_key=normalize_name("Alp X"),
        tags={"name": "Alp X"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.scan_pbf",
        lambda path: [candidate],
    )
    monkeypatch.setattr(
        pipeline_module,
        "build_plan",
        lambda *args, **kwargs: pytest.fail(
            "variant planning must not build an ordinary query plan"
        ),
    )

    plan = pipeline_module.build_variant_plan(
        Path("liechtenstein-latest.osm.pbf"),
        variants=(("v1", "land cover"), ("v2", "terrain")),
    )

    assert [item["keyword"] for item in plan["query_variants"]] == [
        "land cover",
        "terrain",
    ]


def test_build_variant_plan_has_no_queries_without_a_selection(monkeypatch) -> None:
    monkeypatch.setattr("osm_polygon_web_search.pipeline.scan_pbf", lambda path: [])

    plan = pipeline_module.build_variant_plan(Path("liechtenstein-latest.osm.pbf"))

    assert plan["selected"] is None
    assert plan["query"] is None
    assert plan["query_variants"] == []


def test_build_variant_plan_requires_at_least_one_variant() -> None:
    with pytest.raises(ValueError, match="^at least one query variant is required$"):
        pipeline_module.build_variant_plan(
            Path("liechtenstein-latest.osm.pbf"),
            variants=(),
        )


def test_output_paths_must_stay_under_the_seagate_data_root() -> None:
    assert ensure_data_path(
        Path("/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc")
    )

    with pytest.raises(ValueError, match="data root"):
        ensure_data_path(Path("/tmp/osm-polygon-web-search"))


def test_run_poc_rejects_a_pbf_outside_the_seagate_data_root(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.build_plan",
        lambda path, keywords: pytest.fail("outside PBF must be rejected first"),
    )

    with pytest.raises(ValueError, match="data root"):
        run_poc(
            Path("/tmp/outside.osm.pbf"),
            output_dir=tmp_path,
        )


def test_build_plan_reports_no_selection_when_the_pbf_has_no_candidates(
    monkeypatch,
) -> None:
    monkeypatch.setattr("osm_polygon_web_search.pipeline.scan_pbf", lambda path: [])

    plan = build_plan(Path("liechtenstein-latest.osm.pbf"), keywords=["geology"])

    assert plan["selected"] is None
    assert plan["query"] is None


def test_run_poc_passes_the_typed_plan_to_search_before_serializing(
    monkeypatch,
    tmp_path,
) -> None:
    typed_plan = pipeline_module._PipelinePlan(
        selection=pipeline_module._SelectionPlan(
            pbf_path=tmp_path / "source.pbf",
            country="Liechtenstein",
            candidate_count=0,
            unique_candidate_count=0,
            selected=None,
        ),
        query=None,
    )
    search_plans = []

    monkeypatch.setattr(
        pipeline_module,
        "_build_plan",
        lambda path, *, keywords: typed_plan,
    )
    monkeypatch.setattr(
        pipeline_module,
        "ensure_data_path",
        lambda path: tmp_path,
    )

    def fake_search_records(plan, *, provider, fetcher, result_count):
        search_plans.append(plan)
        return []

    monkeypatch.setattr(pipeline_module, "_search_records", fake_search_records)
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    output = run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
        search=True,
    )

    assert search_plans == [typed_plan]
    assert json.loads(output.read_text())["results"] == []


def test_search_records_skip_an_unsearchable_plan() -> None:
    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            raise AssertionError("provider must not be called")

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError("fetcher must not be called")

    assert (
        _search_records(
            _make_pipeline_plan(None, place_name=None),
            provider=Provider(),
            fetcher=Fetcher(),
            result_count=5,
        )
        == []
    )


def test_search_records_reads_typed_query_and_selected_name() -> None:
    plan = _make_pipeline_plan('"Alp X" "Liechtenstein" terrain')

    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            assert query == '"Alp X" "Liechtenstein" terrain'
            return []

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError(f"fetcher must not be called for {url}")

    assert (
        _search_records(
            plan,
            provider=Provider(),
            fetcher=Fetcher(),
            result_count=5,
        )
        == []
    )


@pytest.mark.parametrize(
    ("query", "place_name"),
    [
        (None, "Alp X"),
        ("Alp X", None),
    ],
)
def test_search_records_skips_plans_with_one_missing_required_value(
    query: str | None,
    place_name: str | None,
) -> None:
    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            raise AssertionError("provider must not be called")

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError("fetcher must not be called")

    assert (
        _search_records(
            _make_pipeline_plan(query, place_name=place_name),
            provider=Provider(),
            fetcher=Fetcher(),
            result_count=5,
        )
        == []
    )


def test_search_records_fetches_pages_and_serializes_evidence() -> None:
    calls = []

    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            calls.append((query, count))
            return [
                SearchResult(
                    rank=1,
                    title="Alp X",
                    url="https://example.test/alp-x",
                    snippet="Limestone.",
                )
            ]

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            return FetchedPage(
                url=url,
                status=200,
                html="<p>Alp X has limestone.</p>",
                text="Alp X has limestone.",
            )

    records = _search_records(
        _make_pipeline_plan('"Alp X" "Liechtenstein" (geology)'),
        provider=Provider(),
        fetcher=Fetcher(),
        result_count=7,
    )

    assert calls == [('"Alp X" "Liechtenstein" (geology)', 7)]
    assert records == [
        {
            "result": {
                "rank": 1,
                "title": "Alp X",
                "url": "https://example.test/alp-x",
                "snippet": "Limestone.",
            },
            "page": {
                "url": "https://example.test/alp-x",
                "status": 200,
            },
            "evidence": [
                {
                    "sentence": "Alp X has limestone.",
                    "criteria": ("soil_surface",),
                }
            ],
        }
    ]


def test_serialize_search_results_keeps_order_and_skips_missing_pages() -> None:
    from osm_polygon_web_search.pipeline import _serialize_search_results

    search_results = [
        SearchResult(1, "Missing", "https://example.test/missing", ""),
        SearchResult(2, "Available", "https://example.test/available", ""),
    ]
    pages = {
        "https://example.test/available": FetchedPage(
            url="https://example.test/available",
            status=200,
            html="<p>Alp X has limestone.</p>",
            text="Alp X has limestone.",
        )
    }

    assert _serialize_search_results(
        search_results,
        pages,
        place_name="Alp X",
    ) == [
        {
            "result": {
                "rank": 2,
                "title": "Available",
                "url": "https://example.test/available",
                "snippet": "",
            },
            "page": {
                "url": "https://example.test/available",
                "status": 200,
            },
            "evidence": [
                {
                    "sentence": "Alp X has limestone.",
                    "criteria": ("soil_surface",),
                }
            ],
        }
    ]


def test_serialize_search_results_passes_empty_text_to_evidence(monkeypatch) -> None:
    from osm_polygon_web_search.pipeline import _serialize_search_results

    texts = []
    monkeypatch.setattr(
        pipeline_module,
        "find_evidence",
        lambda text, *, place_name: texts.append((text, place_name)) or [],
    )

    records = _serialize_search_results(
        [SearchResult(1, "Available", "https://example.test/available", "")],
        {
            "https://example.test/available": FetchedPage(
                url="https://example.test/available",
                status=200,
                html="",
                text=None,
            )
        },
        place_name="Alp X",
    )

    assert records[0]["evidence"] == []
    assert texts == [("", "Alp X")]


def test_search_records_skips_pages_that_cannot_be_fetched() -> None:
    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            return [
                SearchResult(1, "Unavailable", "https://example.test/unavailable", ""),
                SearchResult(2, "Available", "https://example.test/available", ""),
            ]

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            if url.endswith("unavailable"):
                raise PageFetchError("page request failed")
            return FetchedPage(
                url=url,
                status=200,
                html="<p>Alp X has limestone.</p>",
                text="Alp X has limestone.",
            )

    records = _search_records(
        _make_pipeline_plan('"Alp X" "Liechtenstein" "land cover"'),
        provider=Provider(),
        fetcher=Fetcher(),
        result_count=5,
    )

    assert [record["result"]["url"] for record in records] == [
        "https://example.test/available"
    ]


def test_search_variant_records_runs_each_query_variant(monkeypatch) -> None:
    calls = []

    def fake_search_records(plan, *, provider, fetcher, result_count, page_cache=None):
        calls.append((plan.query, provider, fetcher, result_count, page_cache))
        return [{"query": plan.query}]

    monkeypatch.setattr(pipeline_module, "_search_records", fake_search_records)
    plan = _make_pipeline_plan(
        None,
        query_variants=(
            pipeline_module._QueryVariant(
                id="v1",
                keyword="land cover",
                query='"Alp X" "Liechtenstein" "land cover"',
            ),
            pipeline_module._QueryVariant(
                id="v2",
                keyword="land use",
                query='"Alp X" "Liechtenstein" "land use"',
            ),
        ),
    )

    provider = cast(SearchProvider, object())
    fetcher = cast(PageProvider, object())
    records = pipeline_module._search_variant_records(
        plan,
        provider=provider,
        fetcher=fetcher,
        result_count=7,
    )

    assert [item["id"] for item in records] == ["v1", "v2"]
    assert [item["keyword"] for item in records] == ["land cover", "land use"]
    assert [item["query"] for item in records] == [
        '"Alp X" "Liechtenstein" "land cover"',
        '"Alp X" "Liechtenstein" "land use"',
    ]
    assert [item["results"] for item in records] == [
        [{"query": '"Alp X" "Liechtenstein" "land cover"'}],
        [{"query": '"Alp X" "Liechtenstein" "land use"'}],
    ]
    assert [call[0] for call in calls] == [
        '"Alp X" "Liechtenstein" "land cover"',
        '"Alp X" "Liechtenstein" "land use"',
    ]
    assert all(call[1] is provider for call in calls)
    assert all(call[2] is fetcher for call in calls)
    assert all(call[3] == 7 for call in calls)
    assert calls[0][4] is calls[1][4]


def test_search_variant_records_reads_typed_variants(monkeypatch) -> None:
    variant = pipeline_module._QueryVariant(
        id="v1",
        keyword="land cover",
        query='"Alp X" "Liechtenstein" "land cover"',
    )
    plan = _make_pipeline_plan(
        None,
        place_name=None,
        query_variants=(variant,),
    )
    search_plans = []

    def fake_search_records(plan, *, provider, fetcher, result_count, page_cache=None):
        search_plans.append(plan)
        return []

    monkeypatch.setattr(pipeline_module, "_search_records", fake_search_records)

    records = pipeline_module._search_variant_records(
        plan,
        provider=cast(SearchProvider, object()),
        fetcher=cast(PageProvider, object()),
        result_count=5,
    )

    assert search_plans[0].query == variant.query
    assert search_plans[0].query_variants is None
    assert records == [
        {
            "id": "v1",
            "keyword": "land cover",
            "query": variant.query,
            "results": [],
        }
    ]


def test_search_variant_records_skips_an_ordinary_plan() -> None:
    assert (
        pipeline_module._search_variant_records(
            _make_pipeline_plan(None),
            provider=cast(SearchProvider, object()),
            fetcher=cast(PageProvider, object()),
            result_count=5,
        )
        == []
    )


def test_search_variant_records_shares_a_page_cache(monkeypatch) -> None:
    caches = []

    def fake_search_records(plan, *, provider, fetcher, result_count, page_cache):
        caches.append(page_cache)
        return []

    monkeypatch.setattr(pipeline_module, "_search_records", fake_search_records)

    pipeline_module._search_variant_records(
        _make_pipeline_plan(
            None,
            query_variants=(
                pipeline_module._QueryVariant("v1", "one", "one"),
                pipeline_module._QueryVariant("v2", "two", "two"),
            ),
        ),
        provider=cast(SearchProvider, object()),
        fetcher=cast(PageProvider, object()),
        result_count=5,
    )

    assert len(caches) == 2
    assert isinstance(caches[0], dict)
    assert caches[0] is caches[1]


def test_search_records_uses_serial_fetching_when_delay_is_configured(
    monkeypatch,
) -> None:
    fetch_calls = []

    def fake_fetch_pages(fetcher, urls, *, cache, max_workers):
        fetch_calls.append((urls, cache, max_workers))
        return {}

    monkeypatch.setattr(pipeline_module, "fetch_pages", fake_fetch_pages)

    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            return [SearchResult(1, "Alp X", "https://example.test/alp-x", "")]

    class Fetcher:
        min_delay_seconds = 0.1

        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError(f"fetch should be stubbed for {url}")

    _search_records(
        _make_pipeline_plan("Alp X"),
        provider=Provider(),
        fetcher=Fetcher(),
        result_count=5,
    )

    assert fetch_calls[0][2] == 1


def test_search_records_uses_concurrency_when_fetcher_has_no_delay_attribute(
    monkeypatch,
) -> None:
    fetch_calls = []

    def fake_fetch_pages(fetcher, urls, *, cache, max_workers):
        fetch_calls.append((urls, cache, max_workers))
        return {}

    monkeypatch.setattr(pipeline_module, "fetch_pages", fake_fetch_pages)

    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            return [SearchResult(1, "Alp X", "https://example.test/alp-x", "")]

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError(f"fetch should be stubbed for {url}")

    _search_records(
        _make_pipeline_plan("Alp X"),
        provider=Provider(),
        fetcher=Fetcher(),
        result_count=5,
    )

    assert fetch_calls[0][2] == pipeline_module.PAGE_FETCH_WORKERS


def test_search_records_forwards_the_page_cache(monkeypatch) -> None:
    captured = []

    def fake_fetch_pages(fetcher, urls, *, cache, max_workers):
        captured.append(cache)
        return {}

    monkeypatch.setattr(pipeline_module, "fetch_pages", fake_fetch_pages)

    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            return [SearchResult(1, "Alp X", "https://example.test/alp-x", "")]

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError(f"fetch should be stubbed for {url}")

    page_cache = {}
    _search_records(
        _make_pipeline_plan("Alp X"),
        provider=Provider(),
        fetcher=Fetcher(),
        result_count=5,
        page_cache=page_cache,
    )

    assert captured == [page_cache]


def test_run_poc_writes_the_manifest_inside_the_validated_output_path(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    build_calls = []
    built_plan = _make_pipeline_plan(None, place_name=None)

    def fake_build_plan(path, *, keywords):
        build_calls.append((path, keywords))
        return built_plan

    monkeypatch.setattr(pipeline_module, "_build_plan", fake_build_plan)

    ensured_paths = []

    def fake_ensure_data_path(path):
        ensured_paths.append(path)
        return tmp_path

    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.ensure_data_path",
        fake_ensure_data_path,
    )

    search_calls = []

    def fake_search_records(plan, provider, fetcher, result_count):
        search_calls.append((plan, provider, fetcher, result_count))
        return []

    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline._search_records",
        fake_search_records,
    )

    input_path = Path("liechtenstein-latest.osm.pbf")
    output_path = Path("ignored")
    output = run_poc(
        input_path,
        output_dir=output_path,
        search=True,
    )

    assert output == tmp_path / "run.json"
    assert '"results": []' in output.read_text()
    assert build_calls == [(tmp_path, ("land cover",))]
    assert ensured_paths == [input_path, output_path]
    assert len(search_calls) == 1
    assert search_calls[0][0] is built_plan
    assert isinstance(search_calls[0][1], pipeline_module.BraveSearchProvider)
    assert isinstance(search_calls[0][2], pipeline_module.PageFetcher)
    assert search_calls[0][3] == 5


def test_run_poc_writes_a_plan_without_live_search(monkeypatch, tmp_path) -> None:
    plan = _make_pipeline_plan(None, place_name=None)
    monkeypatch.setattr(
        pipeline_module,
        "_build_plan",
        lambda path, *, keywords: plan,
    )
    output_dir = tmp_path / "nested" / "run"
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.ensure_data_path",
        lambda path: output_dir,
    )

    output = run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
    )

    assert output.exists()
    assert json.loads(output.read_text()) == plan.as_dict()
    assert '"results"' not in output.read_text()


def test_run_poc_streams_json_without_building_a_second_string(
    monkeypatch,
    tmp_path,
) -> None:
    plan = _make_pipeline_plan(None, place_name=None)
    monkeypatch.setattr(
        pipeline_module,
        "_build_plan",
        lambda path, *, keywords: plan,
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.ensure_data_path",
        lambda path: tmp_path,
    )
    monkeypatch.setattr(
        pipeline_module.json,
        "dumps",
        lambda *args, **kwargs: pytest.fail("plan must be streamed to disk"),
    )

    output = run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
        search=False,
    )

    assert json.loads(output.read_text()) == plan.as_dict()
    assert output.read_text().endswith("\n")


def test_run_poc_writes_utf8_json_with_unicode_preserved(monkeypatch, tmp_path) -> None:
    plan = _make_pipeline_plan(None, place_name="München")
    monkeypatch.setattr(
        pipeline_module,
        "_build_plan",
        lambda path, *, keywords: plan,
    )
    monkeypatch.setattr(
        pipeline_module,
        "ensure_data_path",
        lambda path: tmp_path,
    )

    original_open = Path.open
    encodings = []

    def capture_open(path, *args, **kwargs):
        encodings.append(kwargs.get("encoding"))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", capture_open)

    output = run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
    )

    assert encodings[0] == "utf-8"
    assert '"München"' in output.read_text(encoding="utf-8")


def test_run_poc_writes_all_variant_results(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    variant_plan_calls = []
    built_plan = _make_pipeline_plan(
        None,
        place_name=None,
        query_variants=(),
    )

    def fake_build_variant_plan(path):
        variant_plan_calls.append(path)
        return built_plan

    monkeypatch.setattr(
        pipeline_module,
        "_build_variant_plan",
        fake_build_variant_plan,
    )

    ensured_paths = []

    def fake_ensure_data_path(path):
        ensured_paths.append(path)
        return tmp_path

    monkeypatch.setattr(
        pipeline_module,
        "ensure_data_path",
        fake_ensure_data_path,
    )

    search_calls = []

    def fake_search_variant_records(plan, provider, fetcher, result_count):
        search_calls.append((plan, provider, fetcher, result_count))
        return [{"id": "v1"}]

    monkeypatch.setattr(
        pipeline_module,
        "_search_variant_records",
        fake_search_variant_records,
    )

    input_path = Path("liechtenstein-latest.osm.pbf")
    output_path = Path("ignored")
    output = pipeline_module.run_poc(
        input_path,
        output_dir=output_path,
        all_variants=True,
        search=True,
    )

    assert '"variant_results": [' in output.read_text()
    assert variant_plan_calls == [tmp_path]
    assert ensured_paths == [input_path, output_path]
    assert len(search_calls) == 1
    assert search_calls[0][0] is built_plan
    assert isinstance(search_calls[0][1], pipeline_module.BraveSearchProvider)
    assert isinstance(search_calls[0][2], pipeline_module.PageFetcher)
    assert search_calls[0][3] == 5
