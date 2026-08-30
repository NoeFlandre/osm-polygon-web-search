# Data-root Boundary Quality Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Seagate-only path policy to its owning module while preserving every existing API, path result, error, and output.

**Architecture:** `data_root.py` will own `DATA_ROOT`, `data_root`, and `ensure_data_path`. The pipeline will retain a compatibility alias through its import, while sentence and relevance dataset adapters will depend directly on the data-root boundary.

**Tech Stack:** Python 3.11+, uv, pytest/pytest-cov, Ruff, ty, mutmut, MkDocs Material, pre-commit.

---

### Task 1: Add boundary and compatibility RED tests

**Files:**

- Modify: `tests/test_data_root.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Add the failing data-root boundary test**

Import `ensure_data_path` from `osm_polygon_web_search.data_root` and add:

```python
def test_data_root_owns_the_seagate_path_boundary() -> None:
    assert ensure_data_path(EXPECTED_DATA_ROOT / "runs") == (
        EXPECTED_DATA_ROOT / "runs"
    )
```

- [ ] **Step 2: Add the compatibility-alias test**

Import the data-root function and pipeline module, then add:

```python
def test_pipeline_preserves_the_legacy_path_boundary_alias() -> None:
    assert pipeline_module.ensure_data_path is ensure_data_path
```

- [ ] **Step 3: Verify RED**

Run:

```text
uv run --no-cache pytest -q tests/test_data_root.py::test_data_root_owns_the_seagate_path_boundary tests/test_pipeline.py::test_pipeline_preserves_the_legacy_path_boundary_alias
```

Expected result: the first test fails during collection because
`data_root.ensure_data_path` does not exist; after adding the import needed by
the second test, the current implementation would also fail the identity
assertion because the pipeline still owns a separate function object.

### Task 2: Relocate the path policy with no behavior change

**Files:**

- Modify: `src/osm_polygon_web_search/data_root.py`
- Modify: `src/osm_polygon_web_search/pipeline.py`
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`
- Modify: `src/osm_polygon_web_search/relevance_dataset.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the existing implementation to the data-root module**

Keep the exact validation order and error text:

```python
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
```

- [ ] **Step 2: Preserve the pipeline import and remove its duplicate**

Change the pipeline import to:

```python
from .data_root import data_root, ensure_data_path
```

Delete only the old function body from `pipeline.py`; do not change its
callers or signatures.

- [ ] **Step 3: Point dataset adapters at the owning boundary**

Change both dataset modules from:

```python
from .pipeline import ensure_data_path
```

to:

```python
from .data_root import ensure_data_path
```

- [ ] **Step 4: Include the moved policy in mutation scope**

Add `src/osm_polygon_web_search/data_root.py` to the existing
`tool.mutmut.only_mutate` list in `pyproject.toml` without changing any other
mutation configuration.

### Task 3: Verify GREEN and complete the quality gate

**Files:**

- Test: `tests/test_data_root.py`
- Test: `tests/test_pipeline.py`
- Source: the four modules listed in Task 2

- [ ] **Step 1: Run focused GREEN tests**

```text
uv run --no-cache pytest -q tests/test_data_root.py tests/test_pipeline.py
```

- [ ] **Step 2: Run the complete regression and static checks**

```text
env UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache just check
uv run --no-cache ruff check --select C901 .
uv run --no-cache mutmut run
test -z "$(uv run --no-cache mutmut results)"
uv run --no-cache pre-commit run --all-files
```

The mutation run must report zero surviving or unresolved mutants; full branch
coverage plus the configured McCabe ceiling of 5 establishes CRAP below 6.

- [ ] **Step 3: Review, commit, push, and verify synchronization**

Stage only the design, plan, source, test, and configuration files named above,
commit with:

```text
git commit -m "refactor: move path policy to data root"
git push origin main
```

Verify a clean worktree and that `git ls-remote origin refs/heads/main` equals
the local `HEAD` SHA.
