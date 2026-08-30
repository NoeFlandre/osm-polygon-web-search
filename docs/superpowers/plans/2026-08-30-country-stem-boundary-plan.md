# Country stem boundary implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate PBF filename suffix parsing from country-label formatting without changing the existing country resolution contract.

**Architecture:** Add one private, pure `_country_stem` helper that removes the exact `.osm.pbf` and `-latest` suffixes in their existing order. Keep `country_from_pbf` responsible for whitespace normalization, title casing, and empty-label validation.

**Tech Stack:** Python 3.11+, pytest, Ruff, ty, coverage.py, mutmut, MkDocs Material.

---

### Task 1: Specify the country-stem boundary with a failing test

**Files:**
- Modify: `tests/test_country.py`

- [x] **Step 1: Write the failing test**

Add a direct contract test for the new private parsing boundary:

```python
def test_country_stem_removes_pbf_and_latest_suffixes() -> None:
    from osm_polygon_web_search.country import _country_stem

    assert _country_stem(Path("liechtenstein-latest.osm.pbf")) == "liechtenstein"
```

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_country.py::test_country_stem_removes_pbf_and_latest_suffixes
```

Expected result: collection fails because `_country_stem` does not yet exist.

### Task 2: Implement and integrate the smallest parsing boundary

**Files:**
- Modify: `src/osm_polygon_web_search/country.py`
- Modify: `tests/test_country.py`

- [x] **Step 1: Add the minimal helper**

Implement:

```python
def _country_stem(path: Path) -> str:
    return path.name.removesuffix(".osm.pbf").removesuffix("-latest")
```

Use `_country_stem(path)` inside `country_from_pbf` and leave its existing
normalization and empty-label error unchanged.

- [x] **Step 2: Run focused tests and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_country.py
```

Expected result: all country tests pass with the original outputs preserved.

### Task 3: Validate, commit, and publish

Run the full configured tests, coverage, Ruff, complexity, ty, strict MkDocs,
pre-commit, and mutation gates. Build the wheel. Attempt the Docker build and
record an environment-only daemon failure if no local daemon is available.
Run `git diff --check`, stage only the scoped files, commit with a
Conventional Commit message, push `main`, and verify local and remote commit
IDs match.
