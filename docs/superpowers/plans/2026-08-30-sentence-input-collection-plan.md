# Sentence-input Collection Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicated sentence-input list construction while preserving every existing relevance-classification behavior.

**Architecture:** Keep `_iter_sentence_inputs` as the single validation/filtering boundary and add a private collector that materializes its source values and validated sentences together. Route both row and Arrow transformations through that collector without changing their public interfaces.

**Tech Stack:** Python 3.11, pytest, pytest-cov, PyArrow, Ruff, ty, mutmut, MkDocs.

---

### Task 1: Centralize relevance sentence-input collection

**Files:**
- Create: `docs/superpowers/specs/2026-08-30-sentence-input-collection-design.md`
- Modify: `src/osm_polygon_web_search/relevance_dataset.py:24-57,85-94`
- Test: `tests/test_relevance_dataset.py:1-131`

- [x] **Step 1: Write the failing test**

Add this import and test to `tests/test_relevance_dataset.py`:

```python
from osm_polygon_web_search.relevance_dataset import (
    _collect_sentence_inputs,
    _non_empty_sentence,
    classify_rows,
    relevant_rows,
    transform_parquet,
)


def test_collect_sentence_inputs_preserves_valid_source_order() -> None:
    assert _collect_sentence_inputs(
        [
            (4, "A sentence."),
            (5, "  "),
            (6, None),
            (7, "  Another sentence.  "),
        ]
    ) == (
        [4, 7],
        ["A sentence.", "  Another sentence.  "],
    )
```

- [x] **Step 2: Run the focused test to verify RED**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pytest -q tests/test_relevance_dataset.py::test_collect_sentence_inputs_preserves_valid_source_order
```

Expected: collection fails with `ImportError` because `_collect_sentence_inputs` does not yet exist.

- [x] **Step 3: Implement the smallest passing collector**

Add this helper immediately after `_iter_sentence_inputs`:

```python
def _collect_sentence_inputs(
    values: Iterable[tuple[SourceT, object]],
) -> tuple[list[SourceT], list[str]]:
    sources: list[SourceT] = []
    sentences: list[str] = []
    for source, sentence in _iter_sentence_inputs(values):
        sources.append(source)
        sentences.append(sentence)
    return sources, sentences
```

Then replace the duplicated accumulation in `classify_rows` with:

```python
    source_rows, sentences = _collect_sentence_inputs(
        (row, row.get("sentence")) for row in rows
    )
    sentence_rows = [dict(row) for row in source_rows]
```

Replace the duplicated accumulation in `transform_parquet` with:

```python
    valid_indices, sentences = _collect_sentence_inputs(enumerate(sentence_values))
```

- [x] **Step 4: Run focused and module tests to verify GREEN**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pytest -q tests/test_relevance_dataset.py
```

Expected: all relevance-dataset tests pass, including the existing tests for
blank-value filtering, row context, Arrow ordering, empty schemas, and batch
length errors.

- [x] **Step 5: Refactor only while green**

Inspect the changed module for duplicated list-building logic and confirm that
the collector owns only materialization while `_iter_sentence_inputs` still
owns validation. Keep the helper private and do not introduce a new module or
change the public result dictionaries.

- [x] **Step 6: Run the complete quality surface**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pre-commit run --all-files
.venv/bin/ruff check --select C901,FURB .
.venv/bin/mutmut run
.venv/bin/mutmut results
git diff --check
git status --short --branch
```

Expected: full tests, 100% line/branch coverage, Ruff, ty, strict MkDocs,
pre-commit, complexity, and mutation testing pass with no survivors or
unresolved mutants. Docker is attempted separately when the daemon is
available; a missing local Docker socket is reported as an environment-only
limitation.

- [x] **Step 7: Commit and push the validated change**

```bash
git add docs/superpowers/specs/2026-08-30-sentence-input-collection-design.md docs/superpowers/plans/2026-08-30-sentence-input-collection-plan.md src/osm_polygon_web_search/relevance_dataset.py tests/test_relevance_dataset.py
git commit -m "refactor: centralize relevance sentence inputs"
git push origin main
```
