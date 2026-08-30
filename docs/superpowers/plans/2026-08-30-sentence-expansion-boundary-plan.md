# Sentence-expansion Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the positional sentence-expansion tuple with a named tuple without changing its values or any generated dataset output.

**Architecture:** Keep sentence expansion as one private pure function, but give its four related lists descriptive fields through `_SentenceExpansion`. The Arrow table builder will read those fields directly; tuple compatibility remains available at the private boundary.

**Tech Stack:** Python 3.11, pytest, pytest-cov, PyArrow, Ruff, ty, mutmut, MkDocs.

---

### Task 1: Name the sentence-expansion result fields

**Files:**
- Create: `docs/superpowers/specs/2026-08-30-sentence-expansion-boundary-design.md`
- Modify: `src/osm_polygon_web_search/sentence_dataset.py:1-63,105-135`
- Test: `tests/test_sentence_dataset.py:203-215`

- [x] **Step 1: Write the failing test**

Extend the existing expansion test in `tests/test_sentence_dataset.py`:

```python
def test_expand_sentence_groups_exposes_named_fields() -> None:
    from osm_polygon_web_search.sentence_dataset import _expand_sentence_groups

    expansion = _expand_sentence_groups(
        [4, 9],
        [["First.", "Second!"], ["Third?"]],
    )

    assert expansion.repeated_indices == [4, 4, 9]
    assert expansion.sentence_values == ["First.", "Second!", "Third?"]
    assert expansion.sentence_indices == [0, 1, 0]
    assert expansion.sentence_counts == [2, 2, 1]
```

- [x] **Step 2: Run the focused test to verify RED**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pytest -q tests/test_sentence_dataset.py::test_expand_sentence_groups_exposes_named_fields
```

Expected: `AttributeError` because the current four-item tuple has no named
fields.

- [x] **Step 3: Implement the smallest compatible representation**

Import `NamedTuple` and define this private result type before
`_expand_sentence_groups`:

```python
class _SentenceExpansion(NamedTuple):
    repeated_indices: list[int]
    sentence_values: list[str]
    sentence_indices: list[int]
    sentence_counts: list[int]
```

Change `_expand_sentence_groups` to return `_SentenceExpansion` and construct
that named tuple from the existing four lists. Replace positional destructuring
in `_sentence_table` with:

```python
    expansion = _expand_sentence_groups(source_indices, sentence_groups)

    selected = source.take(pa.array(expansion.repeated_indices, type=pa.int64()))
```

Use `expansion.sentence_values`, `expansion.sentence_indices`, and
`expansion.sentence_counts` for the three corresponding Arrow columns.

- [x] **Step 4: Run focused and module tests to verify GREEN**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pytest -q tests/test_sentence_dataset.py::test_expand_sentence_groups_exposes_named_fields tests/test_sentence_dataset.py
```

Expected: the new named-field test and all sentence dataset tests pass. The
existing tuple-equality test must remain green, proving compatibility.

- [x] **Step 5: Refactor only while green**

Confirm that `_sentence_table` no longer relies on positional destructuring,
that `_SentenceExpansion` remains private, and that no unrelated segmentation
or Parquet behavior changed.

- [x] **Step 6: Run the complete quality surface**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pre-commit run --all-files
.venv/bin/ruff check --select C901,FURB .
.venv/bin/mutmut run
.venv/bin/mutmut results
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel --out-dir /private/tmp/osm-polygon-web-search-quality-dist-20260830-expansion
docker build -t osm-polygon-web-search:quality-20260830-expansion .
git diff --check
```

Expected: full tests, 100% line/branch coverage, Ruff, ty, strict MkDocs,
pre-commit, complexity, mutation testing, and wheel build pass. If Docker's
local daemon socket is absent, report that environmental limitation without
changing the repository.

- [x] **Step 7: Commit and push the validated change**

```bash
git add docs/superpowers/specs/2026-08-30-sentence-expansion-boundary-design.md docs/superpowers/plans/2026-08-30-sentence-expansion-boundary-plan.md src/osm_polygon_web_search/sentence_dataset.py tests/test_sentence_dataset.py
git commit -m "refactor: name sentence expansion fields"
git push origin main
```
