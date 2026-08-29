# Blazing Throughput Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove proven-safe duplicate SAT work and full Python Parquet materialization while preserving every output contract.

**Architecture:** Keep the existing scalar and batched model boundaries. Add first-seen exact-content reuse only at the SAT sentence boundary, restore output multiplicity with stable indices, and use Arrow `Table.take` for sentence expansion. Keep per-row LFM inference because the stored output contains conflicting labels for duplicate sentence strings. Stream the existing JSON representation directly to disk.

**Tech Stack:** Python 3.12, uv, pytest, coverage.py, mutmut, PyArrow, wtpsplit, Transformers, standard-library JSON.

---

## Task 1: Establish the RED tests for deterministic SAT reuse

**Files:**
- Modify: `tests/test_sentence_dataset.py`
- Read: `src/osm_polygon_web_search/sentence_dataset.py`

- [ ] Add `test_sentence_rows_segments_duplicate_text_once` with three page rows (`One.`, duplicate `One.`, and `Two!`), a batched segmenter that records inputs, and assertions for one first-seen model input plus two restored page contexts.
- [ ] Run `uv run --no-cache pytest -q tests/test_sentence_dataset.py::test_sentence_rows_segments_duplicate_text_once` and confirm the current implementation fails because it passes the duplicate text to the model.
- [ ] Keep the test focused on observable output and the model-call boundary; do not change production code before the expected RED result.

## Task 2: Implement and refactor SAT reuse

**Files:**
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`
- Test: `tests/test_sentence_dataset.py`

- [ ] Add a first-seen unique-text mapping inside `_segment_page_texts`, use the existing scalar or optional `split_many` path once per unique text, and restore groups with the original text sequence.
- [ ] Run the focused sentence-dataset test and the complete `tests/test_sentence_dataset.py`; expected result is all tests passing with duplicate rows preserved.
- [ ] Refactor only while green so scalar and batched paths share the same exact-text reuse behavior and existing segment cleaning.
- [ ] Commit with `git add src/osm_polygon_web_search/sentence_dataset.py tests/test_sentence_dataset.py && git commit -m "perf: reuse duplicate sentence segmentation"`.

## Task 3: Verify that LFM label reuse is unsafe

**Files:**
- Read: `/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/classified/train.parquet`
- No production or test changes.

- [ ] Read the stored `sentence` and `relevance_label` columns and group labels by exact sentence value.
- [ ] Confirm the two observed duplicate values with conflicting labels and record that per-row inference must remain unchanged.

## Task 4: Retain the existing LFM transformation

**Files:**
- Read: `src/osm_polygon_web_search/relevance_dataset.py`
- Test: `tests/test_relevance_dataset.py`

- [ ] Keep `_classify_sentences` and `transform_parquet` unchanged so each valid source sentence retains its existing batch position and model call.
- [ ] Run `uv run --no-cache pytest -q tests/test_relevance_dataset.py` and confirm all existing output and batch-contract tests pass.

## Task 5: Establish and implement Arrow-native SAT Parquet expansion

**Files:**
- Modify: `tests/test_sentence_dataset.py`
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`

- [ ] Add a test with multiple source rows and an extra typed column that asserts exact source-column order, duplicate source-row restoration, sentence metadata, and typed empty output.
- [ ] Run the focused test before implementation and confirm the current Python-row reconstruction does not satisfy the Arrow-native boundary assertion.
- [ ] Implement `_sentence_table(source, model)` using only `source["text"].to_pylist()` for model input, repeated source indices, `source.take(pa.array(..., type=pa.int64()))`, and typed `append_column` calls; preserve empty-source columns with `source.slice(0, 0)`.
- [ ] Change `transform_parquet` to write `_sentence_table` directly and retain its count return value and parent-directory creation.
- [ ] Run all sentence-dataset tests and inspect `pq.read_table(output).to_pylist()` for exact equality with the pre-refactor expected rows.
- [ ] Commit with `git add src/osm_polygon_web_search/sentence_dataset.py tests/test_sentence_dataset.py && git commit -m "perf: expand sentence parquet with Arrow"`.

## Task 6: Stream plan JSON without changing its artifact

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `src/osm_polygon_web_search/pipeline.py`

- [ ] Add a test that runs the plan-only path, parses `run.json`, and asserts the artifact ends with exactly one newline and has the same plan values as the returned path.
- [ ] Run the focused test before implementation and confirm it exercises the existing JSON artifact contract.
- [ ] Replace the intermediate `json.dumps(...)+"\\n"` with `output_path.open("w", encoding="utf-8")`, `json.dump(plan, handle, indent=2, ensure_ascii=False)`, and `handle.write("\\n")`.
- [ ] Run all pipeline tests and commit with `git add src/osm_polygon_web_search/pipeline.py tests/test_pipeline.py && git commit -m "perf: stream pipeline json output"`.

## Task 7: Verify exact equivalence and throughput

**Files:**
- No benchmark artifacts in the repository; use `/private/tmp` for transient scripts and the existing Seagate PBF/Parquet inputs.
- Modify documentation only if measured behavior requires a correction to the design or architecture page.

- [ ] Run a read-only comparison of the current committed output fixtures and the optimized sentence/relevance transformations; assert row values, row order, schemas, and counts are equal.
- [ ] Report the measured first-seen counts for the 18-page/708-sentence Seagate POC, the avoided SAT inputs, and the two conflicting LFM duplicate labels without uploading or rewriting HF data.
- [ ] Run `uv run --no-cache ruff format --check .`, `uv run --no-cache ruff check .`, and `uv run --no-cache ty check`.
- [ ] Run `uv run --no-cache pytest -q --cov=osm_polygon_web_search --cov-branch --cov-report=term-missing` and require 100% line and branch coverage.
- [ ] Run the strict MkDocs build, pre-commit, CRAP check, and full mutmut gate; require CRAP below 6 and zero surviving or unresolved mutants.
- [ ] Run `git diff --check`, review the diff for output/schema/prompt/model/storage regressions, and confirm no data or cache was created outside the configured Seagate root except transient `/private/tmp` verification output.

## Task 8: Integrate the verified local pass

**Files:**
- No additional files beyond the committed tasks.

- [ ] Confirm `git status --short --branch` is clean and the branch contains only this optimization pass on top of the previously pushed `main`.
- [ ] Re-run the final test and quality summary from the resulting local `main` before reporting the measured result.
- [ ] Do not push GitHub or update Hugging Face unless separately requested.
