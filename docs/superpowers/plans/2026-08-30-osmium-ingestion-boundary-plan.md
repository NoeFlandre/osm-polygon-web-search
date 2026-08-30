# Typed Osmium Ingestion Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PBF scanner's `Any` annotations with minimal structural interfaces while preserving every runtime path and public result.

**Architecture:** Keep the concrete pyosmium `isinstance` dispatch and model only the attributes each downstream helper consumes. Use static `cast` bridges at the external pyosmium boundary so runtime objects, filtering, and geometry work remain identical.

**Tech Stack:** Python 3.11+, pyosmium, `typing.Protocol`, pytest, coverage.py, Ruff, ty, mutmut, MkDocs, uv.

---

### Task 1: Prove the current PBF boundary is untyped

**Files:**
- Modify: `tests/test_pbf.py`

- [x] **Step 1: Write the failing boundary contract**

Add a focused test using `get_type_hints` that requires `_WayObject`,
`_AreaObject`, and `_GeometryFactory` on the three typed helpers and `object`
at the runtime dispatch boundary.

- [x] **Step 2: Run the focused test and observe RED**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_pbf.py::test_osmium_helpers_have_structural_boundary_types -q
```

Expected: the test fails because the protocols do not exist and the helpers
still expose `Any`.

### Task 2: Add the minimal structural interfaces

**Files:**
- Modify: `src/osm_polygon_web_search/pbf.py`

- [x] **Step 1: Define and apply the protocols**

Add private protocols for coordinate nodes, ways, areas, and multipolygon
factories. Replace the four `Any` helper annotations, preserve
`_object_candidate`'s pyosmium runtime checks, and use `cast` only to cross
from checked external objects into the structural interfaces.

- [x] **Step 2: Run focused tests and type checking until GREEN**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_pbf.py -q
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ty check
```

Expected: the new contract and all existing PBF behavior tests pass, and the
repository type check accepts both production pyosmium objects and test
doubles.

### Task 3: Verify the complete quality surface

**Files:**
- Modify only `pbf.py`, `test_pbf.py`, this design note, and this plan.

- [x] **Step 1: Run static, behavioral, documentation, and complexity gates**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ruff check --select C901 .
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pre-commit run --all-files
```

Expected: formatting, Ruff, `ty`, all tests with 100% line and branch
coverage, strict MkDocs, pre-commit, and the complexity ceiling pass.

Observed: 228 tests passed with 100% line and branch coverage. Ruff formatting,
Ruff lint including C901, `ty`, strict MkDocs, and pre-commit passed.

- [x] **Step 2: Run mutation and artifact checks**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut run --max-children 4
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut results
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just docker
```

Expected: zero surviving or unresolved mutants, a valid wheel, and either a
successful Docker build or a clearly documented unavailable local daemon.

Observed: the first mutation run exposed three untested static cast bridges.
The boundary test was strengthened to observe those exact adapter types, and
the final result was 1,586 of 1,586 mutants killed with an empty results
report. The wheel built successfully. Docker could not run because the local
daemon socket did not exist.

### Task 4: Publish only the validated refactor

- [x] **Step 1: Review and commit exact paths**

Check the diff for runtime changes, accidental data/model paths, and unrelated
files. Stage only the four scoped files and commit with a Conventional Commit.

- [x] **Step 2: Push and verify remote parity**

Push `main`, verify local `HEAD` equals `origin/main`, and require a clean
worktree.
