# Search-Record Serialization Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate deterministic search-result serialization from the pipeline orchestrator without changing any public behavior or output.

**Architecture:** Keep `_search_records` responsible for plan validation, provider invocation, page fetching, and cache/concurrency policy. Add one pure `_serialize_search_results` helper that maps ordered `SearchResult` values and fetched pages into the existing JSON-ready record shape.

**Tech Stack:** Python 3.11, pytest, Ruff, ty, pyarrow-independent pipeline tests.

---

### Task 1: Specify the serialization boundary with a failing test

**Files:**
- Modify: `tests/test_pipeline.py`

- [x] **Step 1: Write the failing test**

Add this test after `test_search_records_fetches_pages_and_serializes_evidence`:

```python
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
```

- [x] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_pipeline.py::test_serialize_search_results_keeps_order_and_skips_missing_pages
```

Expected result: collection fails with `ImportError` because
`_serialize_search_results` does not exist yet.

### Task 2: Implement the smallest pure helper

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`

- [x] **Step 1: Add the helper needed by the failing test**

Import `Mapping` and `SearchResult`, then add this function immediately before
`_search_records`:

```python
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
```

- [x] **Step 2: Run the focused test and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_pipeline.py::test_serialize_search_results_keeps_order_and_skips_missing_pages
```

Expected result: `1 passed`.

### Task 3: Refactor the orchestrator to delegate serialization

**Files:**
- Modify: `src/osm_polygon_web_search/pipeline.py`

- [x] **Step 1: Replace only the inline serialization loop**

Keep the existing plan validation, search call, and `fetch_pages` call. Replace
the current `results` list and `for result in search_results` block with:

```python
    return _serialize_search_results(
        search_results,
        pages,
        place_name=selected["name_raw"],
    )
```

- [x] **Step 2: Run the pipeline tests and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_pipeline.py
```

Expected result: all pipeline tests pass.

- [x] **Step 3: Run the complete quality surface**

Run:

```bash
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ruff check --select C901 .
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pre-commit run --all-files
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut run
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut results
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel --out-dir /private/tmp/osm-polygon-web-search-search-record-dist-20260830
```

Expected result: every command exits successfully, mutation results are empty,
and coverage remains at 100% for lines and branches.

### Task 4: Close the mutation-scope gap with a failing contract test

**Files:**
- Modify: `tests/test_repository_contracts.py`

- [x] **Step 1: Write the failing contract test**

Add `import tomllib` beside the existing imports, then add this test after
`test_ruff_enforces_the_crap_complexity_ceiling`:

```python
def test_mutation_scope_covers_every_runtime_module() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    configured = set(config["tool"]["mutmut"]["only_mutate"])
    runtime_modules = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "src" / "osm_polygon_web_search").glob("*.py")
        if path.name != "__init__.py"
    }

    assert runtime_modules <= configured
```

- [x] **Step 2: Run the focused contract test and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_repository_contracts.py::test_mutation_scope_covers_every_runtime_module
```

Expected result: the assertion fails and reports the five missing modules:
`__main__.py`, `fetch.py`, `pipeline.py`, `search.py`, and `text.py`.

### Task 5: Expand mutation testing to every runtime module and publish

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_repository_contracts.py`
- Commit: the pipeline, test, specification, plan, and mutation-contract files

- [x] **Step 1: Add only the missing runtime modules to the mutation allowlist**

Add these five entries to `[tool.mutmut].only_mutate`:

```toml
  "src/osm_polygon_web_search/__main__.py",
  "src/osm_polygon_web_search/fetch.py",
  "src/osm_polygon_web_search/pipeline.py",
  "src/osm_polygon_web_search/search.py",
  "src/osm_polygon_web_search/text.py",
```

- [x] **Step 2: Run the contract test and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_repository_contracts.py::test_mutation_scope_covers_every_runtime_module
```

Expected result: `1 passed`.

- [x] **Step 3: Run the complete quality surface again**

Run:

```bash
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ruff check --select C901 .
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pre-commit run --all-files
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut run
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut results
```

Expected result: every command exits successfully, all runtime mutants are
killed, mutation results are empty, and coverage remains at 100% for lines and
branches.

### Task 6: Commit and publish the validated change

**Files:**
- Commit all validated source, test, configuration, and documentation changes;
  keep generated mutation artifacts and project data out of Git.

- [x] **Step 1: Check the final diff**

Run:

```bash
git diff --check
git status --short --branch
```

Expected result: no whitespace errors and no unrelated paths.

- [x] **Step 2: Commit**

Run:

```bash
git add docs/development.md justfile pyproject.toml src/osm_polygon_web_search/__main__.py src/osm_polygon_web_search/fetch.py src/osm_polygon_web_search/pipeline.py src/osm_polygon_web_search/search.py tests/test_module_entrypoint.py tests/test_pipeline.py tests/test_repository_contracts.py tests/test_search_and_fetch.py tests/test_text_and_relevance.py docs/superpowers/specs/2026-08-30-search-record-serialization-design.md docs/superpowers/plans/2026-08-30-search-record-serialization-plan.md
git commit -m "refactor: isolate search result serialization"
```

- [x] **Step 3: Push and verify**

Run:

```bash
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected result: the working tree is clean and the local and remote commit IDs
match.

### Validation evidence

- 201 tests pass with 100% line and branch coverage.
- Ruff formatting, linting, the C90 complexity ceiling, `ty`, pre-commit, and
  strict MkDocs validation pass.
- Mutation testing kills all 1,560 generated mutants with no unresolved
  statuses.
- The wheel builds successfully. Docker validation requires a running local
  Docker daemon.

### Mutation-gate note

The ensure_ascii=None equivalent is excluded by an exact source-line pattern.
HTTP header names and values are module constants, and their observable
contracts remain covered by request-header tests; all other generated mutants
must be killed.
