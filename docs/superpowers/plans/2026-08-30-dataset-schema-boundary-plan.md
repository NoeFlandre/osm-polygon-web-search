# Typed Dataset Schema Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the sentence and relevance dataset boundaries explicit and typed without changing any row, Parquet, API, or filesystem behavior.

**Architecture:** Add one small schema module containing open-world row aliases and required generated-field `TypedDict`s. Keep arbitrary source context columns in `Mapping[str, object]` records, add typed metadata helpers, and annotate the private Arrow table adapters as `pyarrow.Table` while keeping their runtime imports lazy.

**Tech Stack:** Python 3.11+, `typing`, `TypedDict`, PyArrow, pytest, coverage.py, Ruff, ty, mutmut, MkDocs, uv.

---

## Task 1: Add the typed schema contract test first

**Files:**
- Create: `tests/test_dataset_schema.py`

- [x] **Step 1: Write the failing schema contract test**

```python
from collections.abc import Mapping
from typing import get_type_hints

from osm_polygon_web_search.dataset_schema import (
    DatasetRecord,
    DatasetRow,
    RelevanceMetadata,
    SentenceMetadata,
)


def test_dataset_schema_declares_open_rows_and_required_generated_fields() -> None:
    assert DatasetRow == Mapping[str, object]
    assert DatasetRecord == dict[str, object]
    assert set(SentenceMetadata.__required_keys__) == {
        "sentence",
        "sentence_index",
        "sentence_count",
        "sentence_model",
    }
    assert get_type_hints(SentenceMetadata) == {
        "sentence": str,
        "sentence_index": int,
        "sentence_count": int,
        "sentence_model": str,
    }
    assert set(RelevanceMetadata.__required_keys__) == {
        "relevance_label",
        "relevance_model",
    }
```

- [x] **Step 2: Run the test and verify the expected RED failure**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_dataset_schema.py -q
```

Expected: collection fails because `osm_polygon_web_search.dataset_schema`
does not exist yet.

## Task 2: Implement the smallest schema module and make its contract GREEN

**Files:**
- Create: `src/osm_polygon_web_search/dataset_schema.py`
- Test: `tests/test_dataset_schema.py`

- [x] **Step 1: Add the exact typed aliases and metadata contracts**

```python
from collections.abc import Mapping
from typing import TypeAlias, TypedDict

from .llm_relevance import RelevanceLabel

DatasetRow: TypeAlias = Mapping[str, object]
DatasetRecord: TypeAlias = dict[str, object]


class SentenceMetadata(TypedDict):
    sentence: str
    sentence_index: int
    sentence_count: int
    sentence_model: str


class RelevanceMetadata(TypedDict):
    relevance_label: RelevanceLabel
    relevance_model: str
```

- [x] **Step 2: Run the schema test and verify GREEN**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_dataset_schema.py -q
```

Expected: one test passes.

## Task 3: Type the sentence transformation boundary

**Files:**
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`
- Modify: `tests/test_sentence_dataset.py`

- [x] **Step 1: Add the sentence metadata behavior test before implementation**

```python
def test_sentence_metadata_has_the_persisted_field_contract() -> None:
    from osm_polygon_web_search.sentence_dataset import _sentence_metadata

    assert _sentence_metadata("First.", 0, 2) == {
        "sentence": "First.",
        "sentence_index": 0,
        "sentence_count": 2,
        "sentence_model": SAT_MODEL_ID,
    }
```

- [x] **Step 2: Run the focused test and verify the expected RED failure**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_sentence_dataset.py::test_sentence_metadata_has_the_persisted_field_contract -q
```

Expected: collection or runtime failure because `_sentence_metadata` does not
exist yet.

- [x] **Step 3: Add the smallest typed sentence implementation**

Add postponed annotations and the schema imports:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypeVar

from .dataset_schema import DatasetRecord, DatasetRow, SentenceMetadata

if TYPE_CHECKING:
    import pyarrow as pa
```

Add the pure metadata helper:

```python
def _sentence_metadata(
    sentence: str,
    sentence_index: int,
    sentence_count: int,
) -> SentenceMetadata:
    return {
        "sentence": sentence,
        "sentence_index": sentence_index,
        "sentence_count": sentence_count,
        "sentence_model": SAT_MODEL_ID,
    }
```

Change the row and Arrow signatures and use the helper without changing the
existing output shape:

```python
def sentence_rows(
    rows: Iterable[DatasetRow],
    model: SentenceModel,
) -> list[DatasetRecord]:
def _source_text_inputs(source: pa.Table) -> _SourceTextInputs:
def _sentence_table(source: pa.Table, model: SentenceModel) -> pa.Table:
```

Inside the existing sentence-row generator, replace only the four generated
literal fields with:

```python
            {
                **row,
                **_sentence_metadata(
                    sentence,
                    sentence_index,
                    len(sentences),
                ),
            }
```

- [x] **Step 4: Run the focused sentence test and the full sentence suite**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_sentence_dataset.py::test_sentence_metadata_has_the_persisted_field_contract tests/test_sentence_dataset.py -q
```

Expected: the focused test and all existing sentence tests pass with their
exact row and Parquet assertions unchanged.

## Task 4: Type the relevance transformation boundary

**Files:**
- Modify: `src/osm_polygon_web_search/relevance_dataset.py`
- Modify: `tests/test_relevance_dataset.py`

- [x] **Step 1: Add the relevance metadata behavior test before implementation**

```python
def test_relevance_metadata_has_the_persisted_field_contract() -> None:
    from osm_polygon_web_search.relevance_dataset import _relevance_metadata

    assert _relevance_metadata("yes") == {
        "relevance_label": "yes",
        "relevance_model": RELEVANCE_MODEL_ID,
    }
```

- [x] **Step 2: Run the focused test and verify the expected RED failure**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_relevance_dataset.py::test_relevance_metadata_has_the_persisted_field_contract -q
```

Expected: collection or runtime failure because `_relevance_metadata` does not
exist yet.

- [x] **Step 3: Add the relevance Arrow-boundary test before implementation**

Add this test beside the existing `_collect_sentence_inputs` tests:

```python
def test_source_sentence_inputs_returns_valid_rows_in_source_order() -> None:
    from osm_polygon_web_search.relevance_dataset import _source_sentence_inputs

    source = pa.table({"sentence": pa.array(["First.", None, "  ", "Last."])})

    assert _source_sentence_inputs(source) == ([0, 3], ["First.", "Last."])
```

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_relevance_dataset.py::test_source_sentence_inputs_returns_valid_rows_in_source_order -q
```

Expected: collection fails because `_source_sentence_inputs` does not exist
yet.

- [x] **Step 4: Add the smallest typed relevance implementation**

Add postponed annotations, the type-checking Arrow import, and schema imports:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from .dataset_schema import DatasetRecord, DatasetRow, RelevanceMetadata

if TYPE_CHECKING:
    import pyarrow as pa
```

Add the pure metadata helper:

```python
def _relevance_metadata(label: RelevanceLabel) -> RelevanceMetadata:
    return {
        "relevance_label": label,
        "relevance_model": RELEVANCE_MODEL_ID,
    }
```

Add the typed private Arrow adapter:

```python
def _source_sentence_inputs(source: pa.Table) -> tuple[list[int], list[str]]:
    sentence_values = (
        source["sentence"].to_pylist() if "sentence" in source.column_names else []
    )
    return _collect_sentence_inputs(enumerate(sentence_values))
```

Change the row signatures:

```python
def classify_rows(
    rows: Iterable[DatasetRow],
    classifier: RelevanceClassifier,
) -> list[DatasetRecord]:
def relevant_rows(rows: Iterable[DatasetRow]) -> list[DatasetRecord]:
```

In `transform_parquet`, replace the inline sentence-column extraction with:

```python
    valid_indices, sentences = _source_sentence_inputs(source)
```

Replace only the generated row literal in `classify_rows` with:

```python
            {
                **sentence_rows[index],
                **_relevance_metadata(labels[index]),
            }
```

- [x] **Step 5: Run the focused relevance tests and the full relevance suite**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_relevance_dataset.py::test_relevance_metadata_has_the_persisted_field_contract tests/test_relevance_dataset.py::test_source_sentence_inputs_returns_valid_rows_in_source_order tests/test_relevance_dataset.py -q
```

Expected: the focused test and all existing relevance tests pass with their
exact row, batch, and Parquet assertions unchanged.

## Task 5: Refactor review and complete quality verification

**Files:**
- Modify only `pyproject.toml`, `src/osm_polygon_web_search/dataset_schema.py`, `src/osm_polygon_web_search/sentence_dataset.py`, `src/osm_polygon_web_search/relevance_dataset.py`, `tests/test_dataset_schema.py`, `tests/test_sentence_dataset.py`, `tests/test_relevance_dataset.py`, `tests/test_search_and_fetch.py`, this design note, and this plan.

- [x] **Step 1: Review the type boundary and diff**

Run:

```bash
rg -n "Any|DatasetRow|DatasetRecord|SentenceMetadata|RelevanceMetadata|pyarrow as pa|def _sentence_table|def _source_text_inputs" src/osm_polygon_web_search/dataset_schema.py src/osm_polygon_web_search/sentence_dataset.py src/osm_polygon_web_search/relevance_dataset.py
git diff --check
```

Expected: dataset row APIs use `DatasetRow`/`DatasetRecord`, generated fields
use typed metadata helpers, Arrow table annotations are present, and no
`Any` remains in the two dataset transformation modules.

- [x] **Step 2: Run all static, behavioral, and documentation gates**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ruff check --select C901,FURB .
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pre-commit run --all-files
```

Expected: all tests pass with 100% line and branch coverage, Ruff, `ty`,
strict MkDocs, the complexity gate, and pre-commit all pass.

- [x] **Step 3: Run mutation testing and build artifacts**

Move generated mutation artifacts out of the repository, then run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut run --max-children 4
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut results
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just docker
```

Expected: zero surviving or unresolved mutants, a successful wheel build, and
either a successful Docker build or a documented local-daemon limitation.

- [x] **Step 4: Commit and publish only the scoped changes**

Run:

```bash
git add pyproject.toml src/osm_polygon_web_search/dataset_schema.py src/osm_polygon_web_search/sentence_dataset.py src/osm_polygon_web_search/relevance_dataset.py tests/test_dataset_schema.py tests/test_sentence_dataset.py tests/test_relevance_dataset.py tests/test_search_and_fetch.py docs/superpowers/specs/2026-08-30-dataset-schema-boundary-design.md docs/superpowers/plans/2026-08-30-dataset-schema-boundary-plan.md
git commit -m "refactor: type dataset transformation boundaries"
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected: only the scoped files are committed, local and remote SHAs match,
and the worktree is clean.
