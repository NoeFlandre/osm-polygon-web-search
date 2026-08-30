# Sentence-table Boundary Quality Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (optional). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Isolate deterministic Arrow sentence-expansion bookkeeping from the sentence-table adapter without changing any observable behavior.

**Architecture:** Keep `sentence_dataset._sentence_table` as the Arrow/model orchestration boundary. Add small private helpers for extracting string text inputs and expanding ordered source indices into sentence metadata columns; leave the scalar mapping API, batched model compatibility, and Parquet contract unchanged.

**Tech Stack:** Python 3.11+, uv, pytest/pytest-cov, PyArrow, Ruff, ty, mutmut, MkDocs Material.

---

### Task 1: Add the failing expansion-contract test

**Files:**
- Modify: `tests/test_sentence_dataset.py`

- [ ] **Step 1: Write the failing test**

Add this test with the existing imports in `tests/test_sentence_dataset.py`:

```python
def test_expand_sentence_groups_preserves_arrow_row_order_and_metadata() -> None:
    from osm_polygon_web_search.sentence_dataset import _expand_sentence_groups

    assert _expand_sentence_groups(
        [4, 9],
        [["First.", "Second!"], ["Third?"]],
    ) == (
        [4, 4, 9],
        ["First.", "Second!", "Third?"],
        [0, 1, 0],
        [2, 2, 1],
    )
```

- [ ] **Step 2: Run the focused test and verify the expected red failure**

Run:

```bash
uv run --no-cache pytest -q tests/test_sentence_dataset.py::test_expand_sentence_groups_preserves_arrow_row_order_and_metadata
```

Expected result: collection fails with an `ImportError` because
`_expand_sentence_groups` does not exist yet. This confirms the test targets
the new pure helper rather than accidentally passing against existing code.

### Task 2: Implement the minimal pure helper and verify green

**Files:**
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`
- Test: `tests/test_sentence_dataset.py`

- [ ] **Step 1: Add the smallest implementation**

Add this private helper before `sentence_rows`:

```python
def _expand_sentence_groups(
    source_indices: Sequence[int],
    sentence_groups: Sequence[Sequence[str]],
) -> tuple[list[int], list[str], list[int], list[int]]:
    repeated_indices: list[int] = []
    sentence_values: list[str] = []
    sentence_indices: list[int] = []
    sentence_counts: list[int] = []
    for source_index, sentences in zip(source_indices, sentence_groups, strict=True):
        count = len(sentences)
        repeated_indices.extend([source_index] * count)
        sentence_values.extend(sentences)
        sentence_indices.extend(range(count))
        sentence_counts.extend([count] * count)
    return repeated_indices, sentence_values, sentence_indices, sentence_counts
```

- [ ] **Step 2: Run the focused test and verify green**

Run:

```bash
uv run --no-cache pytest -q tests/test_sentence_dataset.py::test_expand_sentence_groups_preserves_arrow_row_order_and_metadata
```

Expected result: `1 passed`.

### Task 3: Refactor the Arrow adapter around the tested helper

**Files:**
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`
- Test: `tests/test_sentence_dataset.py`

- [ ] **Step 1: Extract source text/index preparation**

Add this private helper before `_sentence_table`:

```python
def _source_text_inputs(source: Any) -> tuple[list[int], list[str]]:
    text_values = source["text"].to_pylist() if "text" in source.column_names else []
    source_indices: list[int] = []
    texts: list[str] = []
    for index, text in enumerate(text_values):
        if isinstance(text, str):
            source_indices.append(index)
            texts.append(text)
    return source_indices, texts
```

- [ ] **Step 2: Replace duplicated inline bookkeeping in `_sentence_table`**

The body of `_sentence_table` must retain the existing lazy `pyarrow` import,
model call, strict group-count behavior, typed Arrow arrays, and column order,
but use the helpers as follows:

```python
def _sentence_table(source: Any, model: SentenceModel) -> Any:
    import pyarrow as pa

    source_indices, texts = _source_text_inputs(source)
    sentence_groups = _segment_page_texts(texts, model)
    (
        repeated_indices,
        sentence_values,
        sentence_indices,
        sentence_counts,
    ) = _expand_sentence_groups(source_indices, sentence_groups)

    selected = source.take(pa.array(repeated_indices, type=pa.int64()))
    return (
        selected.append_column(
            "sentence",
            pa.array(sentence_values, type=pa.string()),
        )
        .append_column(
            "sentence_index",
            pa.array(sentence_indices, type=pa.int64()),
        )
        .append_column(
            "sentence_count",
            pa.array(sentence_counts, type=pa.int64()),
        )
        .append_column(
            "sentence_model",
            pa.array([SAT_MODEL_ID] * len(sentence_values), type=pa.string()),
        )
    )
```

- [ ] **Step 3: Run all sentence-dataset tests**

Run:

```bash
uv run --no-cache pytest -q tests/test_sentence_dataset.py
```

Expected result: all sentence-dataset tests pass, including exact row and
empty-output schema assertions.

### Task 4: Run repository quality gates and review the final diff

**Files:**
- Review: `src/osm_polygon_web_search/sentence_dataset.py`
- Review: `tests/test_sentence_dataset.py`
- Review: `docs/superpowers/specs/2026-08-30-sentence-table-boundary-design.md`

- [ ] **Step 1: Run full regression and static checks**

Run:

```bash
env UV_CACHE_DIR=/Users/noeflandre/.cache/uv just check
env UV_CACHE_DIR=/Users/noeflandre/.cache/uv uv run ruff check --select C901 .
env UV_CACHE_DIR=/Users/noeflandre/.cache/uv uv run pre-commit run --all-files
```

Expected result: formatting, Ruff, `ty`, 100% line/branch coverage, strict
MkDocs, complexity, and all pre-commit hooks pass.

- [ ] **Step 2: Run fresh mutation testing**

Run:

```bash
env UV_CACHE_DIR=/Users/noeflandre/.cache/uv uv run mutmut run
env UV_CACHE_DIR=/Users/noeflandre/.cache/uv uv run mutmut results
```

Expected result: the complete configured mutation set finishes with zero
surviving or unresolved mutants and an empty results report.

- [ ] **Step 3: Build and inspect repository hygiene**

Run:

```bash
env UV_CACHE_DIR=/Users/noeflandre/.cache/uv uv build --wheel --out-dir /private/tmp/osm-polygon-web-search-sentence-quality-dist-20260830
git diff --check
git status --short --branch
git diff --stat
```

Expected result: the wheel builds, the diff has no whitespace errors, only the
planned files are changed, and no data or model artifact is tracked.

- [ ] **Step 4: Commit and push only after every applicable gate passes**

```bash
git add src/osm_polygon_web_search/sentence_dataset.py tests/test_sentence_dataset.py
git commit -m "refactor: isolate sentence table expansion"
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

The final local and remote commit IDs must match and the worktree must be
clean. If Docker is unavailable, report that environmental limitation rather
than treating it as a code failure.
