from pathlib import Path
from typing import cast

import pytest

import osm_polygon_web_search.pipeline as pipeline_module
from osm_polygon_web_search.candidates import PolygonCandidate
from osm_polygon_web_search.fetch import FetchedPage, PageProvider
from osm_polygon_web_search.names import normalize_name
from osm_polygon_web_search.pipeline import (
    _search_records,
    build_plan,
    ensure_data_path,
    run_poc,
    select_candidate,
)
from osm_polygon_web_search.search import SearchProvider, SearchResult


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
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.scan_pbf",
        lambda path: [candidate],
    )

    plan = build_plan(
        Path(
            "/Volumes/Seagate M3/projects/osm-polygon-web-search/"
            "liechtenstein-latest.osm.pbf"
        )
    )

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
    assert plan["query"] == '"Alp X" "Liechtenstein" "land cover"'


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


def test_selection_prefers_physical_landscape_tags_after_uniqueness() -> None:
    building = PolygonCandidate(
        osm_type="way",
        osm_id=1,
        name_raw="A building",
        name_key="a building",
        tags={"name": "A building", "building": "yes"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    meadow = PolygonCandidate(
        osm_type="way",
        osm_id=2,
        name_raw="B meadow",
        name_key="b meadow",
        tags={"name": "B meadow", "landuse": "meadow"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    assert select_candidate([building, meadow]) is meadow


def test_selection_returns_none_for_no_candidates() -> None:
    assert select_candidate([]) is None


def test_selection_prefers_secondary_place_tags_over_unclassified_candidates() -> None:
    unclassified = PolygonCandidate(
        osm_type="way",
        osm_id=1,
        name_raw="Alpha",
        name_key="alpha",
        tags={"name": "Alpha"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    tourism = PolygonCandidate(
        osm_type="way",
        osm_id=2,
        name_raw="Zulu",
        name_key="zulu",
        tags={"name": "Zulu", "tourism": "attraction"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    assert select_candidate([unclassified, tourism]) is tourism


def test_selection_uses_stable_order_for_unclassified_candidates() -> None:
    first = PolygonCandidate(
        osm_type="way",
        osm_id=1,
        name_raw="Zed",
        name_key="zed",
        tags={"name": "Zed"},
        geometry={"type": "Polygon", "coordinates": []},
    )
    second = PolygonCandidate(
        osm_type="way",
        osm_id=2,
        name_raw="Alpha",
        name_key="alpha",
        tags={"name": "Alpha"},
        geometry={"type": "Polygon", "coordinates": []},
    )

    assert select_candidate([first, second]) is second


def test_build_plan_reports_no_selection_when_the_pbf_has_no_candidates(
    monkeypatch,
) -> None:
    monkeypatch.setattr("osm_polygon_web_search.pipeline.scan_pbf", lambda path: [])

    plan = build_plan(Path("liechtenstein-latest.osm.pbf"), keywords=["geology"])

    assert plan["selected"] is None
    assert plan["query"] is None


def test_search_records_skip_an_unsearchable_plan() -> None:
    class Provider:
        def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
            raise AssertionError("provider must not be called")

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError("fetcher must not be called")

    assert (
        _search_records(
            {"query": None, "selected": None},
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
        {
            "query": '"Alp X" "Liechtenstein" (geology)',
            "selected": {"name_raw": "Alp X"},
        },
        provider=Provider(),
        fetcher=Fetcher(),
        result_count=5,
    )

    assert calls == [('"Alp X" "Liechtenstein" (geology)', 5)]
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


def test_search_variant_records_runs_each_query_variant(monkeypatch) -> None:
    calls = []

    def fake_search_records(plan, *, provider, fetcher, result_count):
        calls.append((plan["query"], result_count))
        return [{"query": plan["query"]}]

    monkeypatch.setattr(pipeline_module, "_search_records", fake_search_records)
    plan = {
        "query": None,
        "selected": {"name_raw": "Alp X"},
        "query_variants": [
            {
                "id": "v1",
                "keyword": "land cover",
                "query": '"Alp X" "Liechtenstein" "land cover"',
            },
            {
                "id": "v2",
                "keyword": "land use",
                "query": '"Alp X" "Liechtenstein" "land use"',
            },
        ],
    }

    records = pipeline_module._search_variant_records(
        plan,
        provider=cast(SearchProvider, object()),
        fetcher=cast(PageProvider, object()),
        result_count=5,
    )

    assert [item["id"] for item in records] == ["v1", "v2"]
    assert [item["results"] for item in records] == [
        [{"query": '"Alp X" "Liechtenstein" "land cover"'}],
        [{"query": '"Alp X" "Liechtenstein" "land use"'}],
    ]
    assert calls == [
        ('"Alp X" "Liechtenstein" "land cover"', 5),
        ('"Alp X" "Liechtenstein" "land use"', 5),
    ]


def test_run_poc_writes_the_manifest_inside_the_validated_output_path(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.build_plan",
        lambda path, keywords: {"query": None, "selected": None},
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.ensure_data_path",
        lambda path: tmp_path,
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline._search_records",
        lambda plan, provider, fetcher, result_count: [],
    )

    output = run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
        search=True,
    )

    assert output == tmp_path / "run.json"
    assert '"results": []' in output.read_text()


def test_run_poc_writes_a_plan_without_live_search(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.build_plan",
        lambda path, keywords: {"query": None, "selected": None},
    )
    output_dir = tmp_path / "nested" / "run"
    monkeypatch.setattr(
        "osm_polygon_web_search.pipeline.ensure_data_path",
        lambda path: output_dir,
    )

    output = run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
        search=False,
    )

    assert output.exists()
    assert output.read_text() == '{\n  "query": null,\n  "selected": null\n}\n'
    assert '"results"' not in output.read_text()


def test_run_poc_writes_all_variant_results(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(
        pipeline_module,
        "build_variant_plan",
        lambda path: {"query": None, "query_variants": []},
    )
    monkeypatch.setattr(
        pipeline_module,
        "ensure_data_path",
        lambda path: tmp_path,
    )
    monkeypatch.setattr(
        pipeline_module,
        "_search_variant_records",
        lambda plan, provider, fetcher, result_count: [{"id": "v1"}],
    )

    output = pipeline_module.run_poc(
        Path("liechtenstein-latest.osm.pbf"),
        output_dir=Path("ignored"),
        all_variants=True,
        search=True,
    )

    assert '"variant_results": [' in output.read_text()
