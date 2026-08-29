# Throughput and Efficiency Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing POC pipeline substantially faster and more memory-efficient while preserving its output schema, row order, prompt, model, provider behavior, and Seagate-only data boundary.

**Architecture:** Add a bounded page-fetching boundary with successful URL reuse, add an optional batched interface to the existing sentence-model boundary, and keep relevance Parquet transformations in Arrow after extracting only the sentence values needed for classification. Preserve scalar test doubles and public helper behavior as compatibility seams.

**Tech Stack:** Python 3.12, uv, Ruff, ty, pytest, coverage.py, mutmut, PyArrow, wtpsplit, urllib, MkDocs Material.

---

## Task 1: Establish the isolated implementation baseline

**Files:**
- Create: no source files; use `.worktrees/perf-full-speed/`.
- Read: `docs/superpowers/specs/2026-08-29-throughput-efficiency-design.md`.

- [ ] Commit the approved design and this plan on `main`.
- [ ] Verify `.worktrees/` is ignored, create branch `perf/full-speed`, and run the baseline test/coverage gate from the worktree.
- [ ] Record the baseline as 131 passing tests and 100% line/branch coverage before implementation.

Commands:

```bash
git check-ignore -q .worktrees
git worktree add .worktrees/perf-full-speed -b perf/full-speed
PYTHONPATH=src VIRTUAL_ENV=/Users/noeflandre/osm-polygon-web-search/.venv \
  UV_NO_SYNC=1 uv run --active --no-sync pytest -q \
  --cov=osm_polygon_web_search --cov-branch --cov-report=term-missing
```

## Task 2: Add batched SAT segmentation with scalar compatibility

**Files:**
- Modify: `src/osm_polygon_web_search/sentences.py`.
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`.
- Test: `tests/test_sentences.py`.
- Test: `tests/test_sentence_dataset.py`.

- [ ] RED: add tests for a loaded SAT adapter, `split_many` ordering, fixed batch settings, and `sentence_rows` preferring the optional batched capability while retaining scalar-only model support.
- [ ] GREEN: wrap the loaded `SaT` instance in a small adapter exposing `split` and `split_many`; make `sentence_rows` batch valid page texts and normalize each returned segment with the existing trimming and empty filtering rules.
- [ ] GREEN: add a strict count check for one segmentation result per input text and preserve sentence order, indices, counts, context, and `SAT_MODEL_ID`.
- [ ] REFACTOR: centralize segment normalization so scalar and batched paths cannot drift.
- [ ] Run focused sentence tests and commit the completed task.

Expected adapter call:

```python
sat.split(list(texts), batch_size=32, outer_batch_size=1000)
```

The loaded model remains `segment-any-text/sat-3l-sm` with the existing CPU
ONNX provider. No model cache or output is written outside the configured
Seagate project root.

## Task 3: Fetch unique pages with bounded concurrency and deterministic output

**Files:**
- Modify: `src/osm_polygon_web_search/fetch.py`.
- Modify: `src/osm_polygon_web_search/pipeline.py`.
- Test: `tests/test_search_and_fetch.py`.
- Test: `tests/test_pipeline.py`.

- [ ] RED: add tests showing duplicate URLs are fetched once, four is the maximum default worker count, results retain provider order, `PageFetchError` pages are omitted, failed URLs are not cached, and a positive configured fetch delay forces serial retrieval.
- [ ] GREEN: add a small `fetch_pages` helper that deduplicates missing URLs, uses at most four workers, catches only `PageFetchError`, and returns successful pages keyed by exact URL.
- [ ] GREEN: pass one run-scoped successful-page cache through all query variants; serialize records by the original provider result sequence so concurrency cannot reorder output.
- [ ] GREEN: leave Brave search calls sequential and preserve the existing retry, timeout, response-size, and hard-error behavior.
- [ ] REFACTOR: keep the helper independent of search/query code and avoid caching failures or introducing persistent state.
- [ ] Run focused fetch/pipeline tests, then commit the completed task.

The concurrency path is used only when the fetcher has no positive request
delay. A configured positive delay remains meaningful and therefore selects
serial fetching.

## Task 4: Keep relevance Parquet work Arrow-native

**Files:**
- Modify: `src/osm_polygon_web_search/relevance_dataset.py`.
- Test: `tests/test_relevance_dataset.py`.

- [ ] RED: add tests for preserving source columns and order, dropping invalid sentence rows, appending the same label/model columns, yes-only filtering, empty valid input, and existing 16-row classifier batches.
- [ ] GREEN: identify valid sentence indices from the Arrow sentence column, classify only those values in existing batches, and construct outputs with `Table.take`, `append_column`, and Arrow filtering.
- [ ] GREEN: preserve the public `classify_rows` dictionary API and its strict classifier-result validation.
- [ ] REFACTOR: share one batching helper between the public mapping path and the Arrow path without reconstructing all source rows as Python dictionaries.
- [ ] Run focused relevance tests and commit the completed task.

## Task 5: Document the runtime behavior and perform targeted benchmarks

**Files:**
- Modify: `docs/architecture.md`.
- Modify: `docs/development.md` only if the existing workflow needs a precise performance-gate note.
- Add: no benchmark artifacts to the repository; use read-only scripts/results under `/private/tmp` and model/data inputs under the Seagate root.

- [ ] Document bounded page concurrency, successful exact-URL reuse, deterministic result ordering, serial behavior under positive delay, and batched SAT compatibility.
- [ ] Run a synthetic delayed-fetch comparison and assert the concurrent and serial outputs are identical.
- [ ] Run a real Seagate SAT scalar-versus-batched comparison on the existing 708-sentence POC source and assert exact sentence equality.
- [ ] Confirm no new runtime dependency, persistent cache, or non-Seagate project artifact was introduced.
- [ ] Run focused tests and commit documentation/benchmark-ready code.

## Task 6: Run the complete quality and regression gates

**Files:**
- No planned source changes; fix only evidence-backed failures in the touched modules/tests.

- [ ] Run `uv run ruff format --check .` and `uv run ruff check .`.
- [ ] Run `uv run ty check`.
- [ ] Run the complete pytest suite with line and branch coverage; require 100% coverage.
- [ ] Run the repository CRAP gate and require every reported function below 6.
- [ ] Run mutmut over the repository; require zero surviving mutants.
- [ ] Run strict MkDocs and all pre-commit hooks.
- [ ] Run `git diff --check` and repository contract tests.
- [ ] Review the final diff for dead code, duplicate code, accidental data/model paths, schema changes, and prompt/model changes.

## Task 7: Integrate the verified branch

- [ ] Commit all verified implementation changes with Conventional Commits.
- [ ] Confirm the worktree is clean and the branch contains only this performance pass.
- [ ] Fast-forward local `main` to the verified branch, preserving the existing five unpushed commits and not pushing GitHub unless separately requested.
- [ ] Re-run the final status and key quality summary from `main` before reporting completion.
