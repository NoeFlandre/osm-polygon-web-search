# Text input boundary implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicated string-input filtering while preserving sentence-row output, Arrow row order, empty-string handling, and all public interfaces.

**Architecture:** Add one private lazy `_iter_text_inputs` boundary that keeps source/value pairs only when the value is a string. The mapping sentence adapter supplies page rows as sources and the Arrow adapter supplies integer indices, so representation-specific storage remains local while the acceptance policy is shared.

**Tech Stack:** Python 3.11+, pytest, PyArrow, Ruff, ty, coverage.py, mutmut, MkDocs Material.

---

### Task 1: Specify text-input acceptance with a failing test

**Files:**
- Modify: `tests/test_sentence_dataset.py`

- [x] **Step 1: Write the failing test**

Add this direct contract test near the existing sentence-row tests:

```python
def test_iter_text_inputs_keeps_strings_and_skips_other_values() -> None:
    from osm_polygon_web_search.sentence_dataset import _iter_text_inputs

    assert list(
        _iter_text_inputs(
            [
                (2, ""),
                (3, None),
                (4, 42),
                (5, "First."),
            ]
        )
    ) == [(2, ""), (5, "First.")]
```

- [x] **Step 2: Run it and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_sentence_dataset.py::test_iter_text_inputs_keeps_strings_and_skips_other_values
```

Expected result: collection fails with `ImportError` because
`_iter_text_inputs` does not yet exist.

### Task 2: Implement the smallest lazy text-input boundary

**Files:**
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`
- Test: `tests/test_sentence_dataset.py`

- [x] **Step 1: Add the minimal implementation**

Add `Iterator` and `TypeVar` to the imports, define `SourceT`, and add this
private helper before `_segment_page_texts`:

```python
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, TypeVar

SourceT = TypeVar("SourceT")


def _iter_text_inputs(
    values: Iterable[tuple[SourceT, object]],
) -> Iterator[tuple[SourceT, str]]:
    for source, value in values:
        if isinstance(value, str):
            yield source, value
```

The helper must retain empty strings exactly as the existing adapters do.

- [x] **Step 2: Run the focused test and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_sentence_dataset.py::test_iter_text_inputs_keeps_strings_and_skips_other_values
```

Expected result: `1 passed`.

### Task 3: Route the mapping adapter through the tested boundary

**Files:**
- Modify: `tests/test_sentence_dataset.py`
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`

- [x] **Step 1: Add a failing integration-boundary test**

Add this test helper and test after the direct contract test:

```python
def _observe_text_input_calls(monkeypatch):
    import osm_polygon_web_search.sentence_dataset as module

    calls = []
    original = module._iter_text_inputs

    def observe(values):
        materialized = list(values)
        calls.append(materialized)
        return original(materialized)

    monkeypatch.setattr(module, "_iter_text_inputs", observe)
    return calls


def test_sentence_rows_uses_the_shared_text_input_boundary(monkeypatch) -> None:
    calls = _observe_text_input_calls(monkeypatch)
    row = {"page_url": "https://example.test/page", "text": "First."}

    sentence_rows([row], FakeSegmenter())

    assert calls == [[(row, "First.")]]
```

Run:

```bash
.venv/bin/pytest -q tests/test_sentence_dataset.py::test_sentence_rows_uses_the_shared_text_input_boundary
```

Expected result: `AssertionError` because `sentence_rows` still owns its
string-filtering loop.

- [x] **Step 2: Replace the mapping-path filtering loop**

In `sentence_rows`, preserve the two existing output lists but source them
through the iterator:

```python
    page_rows: list[Mapping[str, Any]] = []
    texts: list[str] = []
    inputs = ((row, row.get("text")) for row in rows)
    for row, text in _iter_text_inputs(inputs):
        page_rows.append(row)
        texts.append(text)
```

- [x] **Step 3: Run the focused mapping tests and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_sentence_dataset.py::test_sentence_rows_uses_the_shared_text_input_boundary tests/test_sentence_dataset.py::test_sentence_rows_expands_pages_and_retains_page_context
```

Expected result: both tests pass with the original row expansion unchanged.

### Task 4: Route the Arrow adapter through the same boundary

**Files:**
- Modify: `tests/test_sentence_dataset.py`
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`

- [x] **Step 1: Add a failing Arrow-boundary test**

Add this test after the mapping-boundary test:

```python
def test_source_text_inputs_uses_the_shared_text_input_boundary(monkeypatch) -> None:
    calls = _observe_text_input_calls(monkeypatch)
    source = pa.table({"text": pa.array(["First.", None, ""])})

    assert _source_text_inputs(source) == ([0, 2], ["First.", ""])
    assert calls == [[(0, "First."), (1, None), (2, "")]]
```

Run:

```bash
.venv/bin/pytest -q tests/test_sentence_dataset.py::test_source_text_inputs_uses_the_shared_text_input_boundary
```

Expected result: `AssertionError` because `_source_text_inputs` still owns its
string-filtering loop.

- [x] **Step 2: Replace the Arrow-path filtering loop**

In `_source_text_inputs`, retain its existing missing-column behavior and
output lists while iterating through the shared boundary:

```python
    text_values = source["text"].to_pylist() if "text" in source.column_names else []
    source_indices: list[int] = []
    texts: list[str] = []
    for index, text in _iter_text_inputs(enumerate(text_values)):
        source_indices.append(index)
        texts.append(text)
    return source_indices, texts
```

- [x] **Step 3: Run all sentence-dataset tests**

Run:

```bash
.venv/bin/pytest -q tests/test_sentence_dataset.py
```

Expected result: all sentence-dataset tests pass, including scalar/batched
segmentation, source-order, Arrow-schema, empty-output, and CLI contracts.

### Task 5: Run every configured quality gate, commit, and publish

- [x] **Step 1: Run the repository checks**

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
.venv/bin/ruff check --select C901,FURB .
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 .venv/bin/pre-commit run --all-files
.venv/bin/mutmut run
if .venv/bin/mutmut results | rg -q .; then exit 1; else echo "mutation results empty"; fi
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel --out-dir /private/tmp/osm-polygon-web-search-quality-dist-20260830-current
docker build -t osm-polygon-web-search:quality-refactor .
git diff --check
```

Expected results are full passing tests and configured checks, 100% line and
branch coverage, empty mutation results, a successful wheel build, and clean
diff whitespace. If Docker has no local daemon, record that environmental
limitation separately.

- [x] **Step 2: Commit and push only the scoped files**

```bash
git add src/osm_polygon_web_search/sentence_dataset.py tests/test_sentence_dataset.py docs/superpowers/plans/2026-08-30-text-input-boundary-plan.md docs/superpowers/specs/2026-08-30-text-input-boundary-design.md
git commit -m "refactor: centralize text input filtering"
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

The local and remote hashes must match and the final worktree must be clean.
