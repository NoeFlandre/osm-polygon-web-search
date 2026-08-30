# Sentence input boundary implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicated sentence filtering loops while preserving the mapping API, Arrow/Parquet behavior, row order, whitespace, batching, and output schema.

**Architecture:** Add one private lazy `_iter_sentence_inputs` boundary that pairs each source item with its validated non-empty sentence. The mapping path supplies `(row, row["sentence"])` pairs and the Arrow path supplies indexed sentence values, so both retain their existing memory and ordering behavior without sharing representation-specific code.

**Tech Stack:** Python 3.11+, pytest, PyArrow, Ruff, ty, coverage.py, mutmut, MkDocs Material.

---

### Task 1: Specify the shared sentence-input boundary with a failing test

**Files:**
- Modify: `tests/test_relevance_dataset.py`

- [x] **Step 1: Write the failing test**

Add this focused contract test beside the existing `_non_empty_sentence` test:

```python
def test_iter_sentence_inputs_keeps_sources_and_skips_blank_values() -> None:
    from osm_polygon_web_search.relevance_dataset import _iter_sentence_inputs

    assert list(
        _iter_sentence_inputs(
            [
                (4, "A sentence."),
                (5, "  "),
                (6, None),
                (7, "  Another sentence.  "),
            ]
        )
    ) == [
        (4, "A sentence."),
        (7, "  Another sentence.  "),
    ]
```

- [x] **Step 2: Run it and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_relevance_dataset.py::test_iter_sentence_inputs_keeps_sources_and_skips_blank_values
```

Expected result: collection fails with `ImportError` because
`_iter_sentence_inputs` does not yet exist.

### Task 2: Implement the smallest lazy boundary and verify GREEN

**Files:**
- Modify: `src/osm_polygon_web_search/relevance_dataset.py`
- Test: `tests/test_relevance_dataset.py`

- [x] **Step 1: Add the minimal implementation**

Update the imports and add the generic source-preserving iterator after
`_non_empty_sentence`:

```python
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, TypeVar

SourceT = TypeVar("SourceT")


def _iter_sentence_inputs(
    values: Iterable[tuple[SourceT, object]],
) -> Iterator[tuple[SourceT, str]]:
    for source, value in values:
        sentence = _non_empty_sentence(value)
        if sentence is not None:
            yield source, sentence
```

Keep the existing `_non_empty_sentence` contract unchanged, including
preserving surrounding whitespace in accepted strings.

- [x] **Step 2: Run the focused test and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_relevance_dataset.py::test_iter_sentence_inputs_keeps_sources_and_skips_blank_values
```

Expected result: `1 passed`.

### Task 3: Refactor both classification paths through the tested boundary

**Files:**
- Modify: `src/osm_polygon_web_search/relevance_dataset.py`
- Test: `tests/test_relevance_dataset.py`

- [x] **Step 1: Add a failing integration-boundary test**

Add this test after the iterator contract test:

```python
def test_classify_rows_uses_the_shared_sentence_input_boundary(monkeypatch) -> None:
    import osm_polygon_web_search.relevance_dataset as module

    calls = []
    original = module._iter_sentence_inputs

    def observe(values):
        materialized = list(values)
        calls.append(materialized)
        return original(materialized)

    monkeypatch.setattr(module, "_iter_sentence_inputs", observe)
    classifier = FakeClassifier({"A sentence.": "yes"})

    assert (
        classify_rows([{"id": 1, "sentence": "A sentence."}], classifier)[0][
            "relevance_label"
        ]
        == "yes"
    )
    assert calls == [
        [
            (
                {"id": 1, "sentence": "A sentence."},
                "A sentence.",
            )
        ]
    ]
```

Run:

```bash
.venv/bin/pytest -q tests/test_relevance_dataset.py::test_classify_rows_uses_the_shared_sentence_input_boundary
```

Expected result: `AssertionError` because `classify_rows` still owns its
filtering loop and does not call the new boundary.

- [x] **Step 2: Replace the mapping-path filtering loop**

Use the iterator to retain source rows and sentence values without
materializing invalid rows:

```python
sentence_rows: list[dict[str, Any]] = []
sentences: list[str] = []
inputs = ((row, row.get("sentence")) for row in rows)
for row, sentence in _iter_sentence_inputs(inputs):
    sentence_rows.append(dict(row))
    sentences.append(sentence)
```

- [x] **Step 3: Replace the Arrow-path filtering loop**

Preserve Arrow selection and source order while using the same boundary:

```python
    valid_indices: list[int] = []
    sentences: list[str] = []
    for index, sentence in _iter_sentence_inputs(enumerate(sentence_values)):
        valid_indices.append(index)
        sentences.append(sentence)
```

- [x] **Step 4: Run the complete relevance-dataset tests**

Run:

```bash
.venv/bin/pytest -q tests/test_relevance_dataset.py
```

Expected result: all relevance-dataset tests pass with the existing output,
batch, error, and empty-table contracts unchanged.

### Task 4: Run every configured quality gate, commit, and publish

- [x] **Step 1: Run the full configured checks**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
.venv/bin/ruff check --select C901,FURB .
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pre-commit run --all-files
.venv/bin/mutmut run
.venv/bin/mutmut results
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel --out-dir /private/tmp/osm-polygon-web-search-quality-dist-20260830-current
docker build -t osm-polygon-web-search:quality-refactor .
git diff --check
```

Expected results are: all tests and configured checks pass; coverage remains
100% line and branch coverage; `mutmut results` is empty; the wheel builds;
and `git diff --check` is clean. The Docker build is environment-dependent;
if the local daemon is unavailable, record that exact limitation without
treating it as a code failure.

- [x] **Step 2: Stage only the validated files, commit, push, and verify**

Stage only the two source/test files and these plan/spec files, then run:

```bash
git add src/osm_polygon_web_search/relevance_dataset.py tests/test_relevance_dataset.py docs/superpowers/plans/2026-08-30-sentence-input-boundary-plan.md docs/superpowers/specs/2026-08-30-sentence-input-boundary-design.md
git commit -m "refactor: centralize sentence input validation"
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

The final local and remote commit IDs must match and the worktree must be
clean.
