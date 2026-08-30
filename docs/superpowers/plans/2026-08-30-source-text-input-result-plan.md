# Source Text Input Result Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the positional source-index/text pair in sentence extraction with a named private result while preserving all existing behavior and compatibility.

**Architecture:** Add `_SourceTextInputs(NamedTuple)` beside the existing sentence-dataset helpers. Make `_source_text_inputs` return that result and update `_sentence_table` to read its named fields. Keep the result tuple-compatible and leave the Arrow schema, row ordering, filtering, and model calls unchanged.

**Tech Stack:** Python 3.11+, `NamedTuple`, PyArrow, pytest, pytest-cov, Ruff, ty, mutmut, MkDocs, uv.

---

## Task 1: Lock the named boundary with a failing test

**Files:**
- Modify: `tests/test_sentence_dataset.py`

- [x] Add `test_source_text_inputs_exposes_named_fields` near the existing `_source_text_inputs` tests.
- [x] Build a small PyArrow table containing valid, null, and empty text values.
- [x] Assert `source_indices == [0, 2]`, `texts == ["First.", ""]`, and tuple equality with the existing pair shape.
- [x] Run `uv run pytest tests/test_sentence_dataset.py -q` and confirm the new test fails because the current tuple has no named fields.

## Task 2: Implement the smallest green change

**Files:**
- Modify: `src/osm_polygon_web_search/sentence_dataset.py`

- [x] Add the private `_SourceTextInputs(NamedTuple)` with `source_indices: list[int]` and `texts: list[str]`.
- [x] Return `_SourceTextInputs(source_indices, texts)` from `_source_text_inputs`.
- [x] Update `_sentence_table` to use `inputs.source_indices` and `inputs.texts`.
- [x] Run the focused sentence-dataset tests and confirm they pass without changing outputs.

## Task 3: Refactor and verify the repository

**Files:**
- Modify only the two implementation/test files above, plus this design note and plan.

- [x] Run formatting, linting, type checking, the full test suite with coverage, strict documentation build, and the focused complexity checks.
- [x] Run fresh mutation testing and confirm no surviving, untested, or timed-out mutants.
- [x] Build the wheel and attempt the Docker build; record any local Docker-daemon limitation without changing behavior.
- [x] Inspect the diff, stage only the approved files, commit with a Conventional Commit message, push `main`, and verify the remote commit matches the local commit.

### Verification notes

- The repository gate passed with 216 tests and 100% line and branch coverage.
- Ruff format, Ruff lint, `ty`, pre-commit, strict MkDocs, and the focused complexity checks passed.
- Fresh mutation testing killed 1,555 of 1,555 mutants; `mutmut results` was empty.
- The wheel built successfully as `dist/osm_polygon_web_search-0.1.0-py3-none-any.whl`.
- Docker verification was attempted but the local Docker daemon socket was unavailable at `/Users/noeflandre/.docker/run/docker.sock`.
