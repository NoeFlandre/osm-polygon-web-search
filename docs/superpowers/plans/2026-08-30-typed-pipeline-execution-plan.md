# Typed Pipeline Execution Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the pipeline's selection, query, and variant state typed until the single JSON serialization boundary without changing public outputs or behavior.

**Architecture:** Add private frozen dataclasses `_QueryVariant` and `_PipelinePlan`. Private builders produce `_PipelinePlan`; the public plan functions serialize it to the existing dictionaries, while `run_poc` passes the typed plan directly to the private search helpers and serializes only for file output. The existing query builder remains the owner of query-string rendering.

**Tech Stack:** Python 3.11+, dataclasses, PyArrow-independent pipeline orchestration, pytest, Ruff, ty, coverage.py, mutmut, MkDocs, uv.

---

## Task 1: Lock typed plan serialization with a failing test

**Files:**
- Modify: `tests/test_pipeline.py`

- [x] Add this test after `test_selection_plan_serializes_the_existing_selection_shape`:

```python
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
```

- [x] Run `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_pipeline.py::test_pipeline_plan_serializes_typed_query_state -q`.
- [x] Confirm RED is an expected collection/runtime failure because `_PipelinePlan` and `_QueryVariant` do not yet exist.

## Task 2: Implement the smallest typed value objects

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`

- [x] Import `replace` from `dataclasses` only when the variant execution refactor in Task 3 needs it; do not add unused imports during this task.
- [x] Add the following private value objects directly after `_SelectionPlan`:

```python
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
```

- [x] Run the focused serialization test and confirm it passes.
- [x] Run the existing pipeline planning tests and confirm public dictionary output remains unchanged.

## Task 3: Keep plan construction typed through public serialization

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`
- Test: `tests/test_pipeline.py`

- [x] Add private `_build_plan` returning `_PipelinePlan`; construct the existing query from `selection.selected.name_raw` and `selection.country`, or `None` when no candidate is selected.
- [x] Add private `_build_variant_plan` returning `_PipelinePlan`; reject an empty `variants` sequence with the existing error, convert the existing `build_variant_queries` records into `_QueryVariant` values, and use `()` when there is no selected candidate.
- [x] Change public `build_plan` and `build_variant_plan` to return the corresponding private builder's `.as_dict()` result. Keep their signatures and exact return dictionaries unchanged.
- [x] Add this focused regression test before changing `run_poc`:

```python
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
```

- [x] Run the focused builder test and the full pipeline planning tests.
- [x] Update `run_poc` to select `_build_plan` or `_build_variant_plan`, create the JSON dictionary from the returned typed plan once, and pass that same typed plan to search helpers.
- [x] Extend the public builder regression coverage to prove custom keywords are forwarded through the typed builder.

## Task 4: Refactor search helpers to consume typed plans

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [x] Change `_search_records` to accept `_PipelinePlan`, return `[]` when `plan.query is None` or `plan.selection.selected is None`, and use `plan.query` plus `plan.selection.selected.name_raw` for provider and evidence calls.
- [x] Change `_search_variant_records` to accept `_PipelinePlan`, iterate its `query_variants` tuple, and create each ordinary search plan with `dataclasses.replace(plan, query=variant.query, query_variants=None)`.
- [x] Preserve page-cache sharing, result ordering, serial/concurrent fetch selection, result counts, and JSON-ready result dictionaries.
- [x] Add a test that monkeypatches `_build_plan` with a typed `_PipelinePlan`, captures the argument received by `_search_records`, and asserts identity equality with the typed plan while asserting the written JSON still contains the existing `results` key and values.
- [x] Replace direct dictionary fixtures passed to `_search_records` and `_search_variant_records` with `_PipelinePlan` fixtures that represent the same selected and unselected cases. Keep every existing output assertion unchanged.
- [x] Assert that each derived ordinary search plan clears `query_variants` before it reaches `_search_records`.
- [x] Run `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_pipeline.py -q` and confirm all pipeline tests pass.

## Task 5: Full verification and publication

**Files:**
- Modify only `src/osm_polygon_web_search/pipeline.py`, `tests/test_pipeline.py`, this design note, and this plan.

- [x] Run `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check` and require all tests, 100% line/branch coverage, Ruff, `ty`, and strict MkDocs to pass.
- [x] Run `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ruff check --select C901,FURB .` and `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pre-commit run --all-files`.
- [x] Move generated mutation artifacts to `/private/tmp/`, run fresh `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut run --max-children 4`, and require an empty `mutmut results` report. The initial fresh run found two untested argument-forwarding mutants; focused contracts killed both, and the final full run reported 1,566/1,566 killed.
- [x] Run `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel`; record the local Docker-daemon limitation because `just docker` could not connect, without altering source behavior.
- [ ] Inspect `git diff --check`, stage only the four scoped files, commit with `refactor: type the pipeline execution plan`, push `main`, and verify `git rev-parse HEAD` equals `git ls-remote origin refs/heads/main` with a clean worktree.

### Verification record

- `just check`: 222 tests passed; 100% line and branch coverage across 730 statements and 152 branches; Ruff, `ty`, and strict MkDocs passed.
- Complexity gate: Ruff `C901` and `FURB` passed. With the repository's McCabe ceiling of 5 and complete branch coverage, the CRAP score ceiling is 5, below the required 6.
- Pre-commit: all hooks passed.
- Mutation testing: 1,566/1,566 killed; zero survived, timed out, or lacked tests.
- Package: `dist/osm_polygon_web_search-0.1.0-py3-none-any.whl` built successfully.
- Docker: blocked only by the unavailable local Docker daemon socket at `/Users/noeflandre/.docker/run/docker.sock`.
