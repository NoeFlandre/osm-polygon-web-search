# Typed selection-plan boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (optional). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pipeline's repeated untyped selection-plan branching with one private typed boundary while preserving every public plan and search output.

**Architecture:** `_SelectionPlan` stores the PBF path, country, candidate counts, and the optional `PolygonCandidate`. Its `as_dict()` method preserves the current JSON-compatible selection-plan shape. The two public plan builders use the typed candidate for query construction and return the same mutable dictionaries consumed by the existing search orchestration.

**Tech Stack:** Python 3.11+, dataclasses, pytest, Ruff, ty, coverage.py, mutmut, MkDocs Material.

---

### Task 1: Specify the typed boundary with a failing test

**Files:**
- Modify: `tests/test_pipeline.py`

- [x] **Step 1: Write the failing serialization contract test**

Add this test after the pipeline compatibility tests:

```python
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
```

- [x] **Step 2: Run it and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_pipeline.py::test_selection_plan_serializes_the_existing_selection_shape
```

Expected result: collection fails with `AttributeError` because the typed
private boundary does not yet exist.

### Task 2: Implement and test the typed selection-plan boundary

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [x] **Step 1: Add the smallest dataclass implementation**

Import `dataclass` and add this private boundary before `_candidate_record`:

```python
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
```

- [x] **Step 2: Run the focused test and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_pipeline.py::test_selection_plan_serializes_the_existing_selection_shape
```

Expected result: `1 passed`.

### Task 3: Refactor plan builders to use typed state

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`
- Test: `tests/test_pipeline.py`

- [x] **Step 1: Return `_SelectionPlan` from the private selector**

Replace `_build_selection_plan` with:

```python
def _build_selection_plan(pbf_path: Path) -> _SelectionPlan:
    candidates = scan_pbf(pbf_path)
    unique = unique_candidates(candidates)
    selected = select_candidate(unique)
    return _SelectionPlan(
        pbf_path=pbf_path,
        country=country_from_pbf(pbf_path),
        candidate_count=len(candidates),
        unique_candidate_count=len(unique),
        selected=selected,
    )
```

- [x] **Step 2: Build the ordinary plan from the typed candidate**

Replace `build_plan` with:

```python
def build_plan(
    pbf_path: Path,
    *,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
) -> dict[str, Any]:
    selection = _build_selection_plan(pbf_path)
    plan = selection.as_dict()
    plan["query"] = (
        build_query(selection.selected.name_raw, selection.country, keywords)
        if selection.selected is not None
        else None
    )
    return plan
```

- [x] **Step 3: Build the variant plan from the same typed candidate**

Replace `build_variant_plan` with:

```python
def build_variant_plan(
    pbf_path: Path,
    *,
    variants: Sequence[tuple[str, str]] = QUERY_VARIANTS,
) -> dict[str, Any]:
    """Build one candidate plan carrying the approved query variants."""
    if not variants:
        raise ValueError("at least one query variant is required")

    selection = _build_selection_plan(pbf_path)
    plan = selection.as_dict()
    plan["query"] = None
    plan["query_variants"] = (
        build_variant_queries(selection.selected.name_raw, selection.country, variants)
        if selection.selected is not None
        else []
    )
    return plan
```

- [x] **Step 4: Run the pipeline regression tests and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_pipeline.py
```

Expected result: every existing pipeline contract passes, including public
dictionary shape, no-selection behavior, variant planning, search caching,
and CLI output.

### Task 4: Run quality gates and publish

- [x] **Step 1: Run the complete configured checks**

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
.venv/bin/ruff check --select C901,FURB .
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pre-commit run --all-files
.venv/bin/mutmut run
if .venv/bin/mutmut results | rg -q .; then exit 1; else echo "mutation results empty"; fi
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel --out-dir /private/tmp/osm-polygon-web-search-quality-dist-20260830-selection
docker build -t osm-polygon-web-search:selection-plan-quality .
git diff --check
```

Expected results are 100% line and branch coverage, all static/docs checks
passing, empty mutation results, a successful wheel build, and no whitespace
errors. If the Docker daemon is unavailable, record that environment-only
limitation without weakening the other gates.

- [x] **Step 2: Commit and push only the scoped files**

```bash
git add src/osm_polygon_web_search/pipeline.py tests/test_pipeline.py docs/superpowers/specs/2026-08-30-selection-plan-boundary-design.md docs/superpowers/plans/2026-08-30-selection-plan-boundary-plan.md
git commit -m "refactor: type the selection plan boundary"
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

The local and remote hashes must match and the final worktree must be clean.
