# End-to-End Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove measured, unnecessary PBF geometry work while preserving every existing result and interface.

**Architecture:** Keep the PBF scanner and candidate boundaries intact. Reject unnamed ways and area relations immediately after reading their tags, before expensive geometry construction; pass the already-computed normalized name key through the private candidate helper. Leave all existing SAT, Arrow, LFM, network, and storage optimizations untouched.

**Tech Stack:** Python 3.12, uv, pytest, coverage.py, mutmut, Ruff, ty, pyosmium, PyArrow, MkDocs Material.

---

### Task 1: Add RED tests for early name rejection

**Files:**
- Modify: `tests/test_pbf.py`
- Read: `src/osm_polygon_web_search/pbf.py`

- [ ] Add one focused test for an unnamed closed way that monkeypatches `way_geometry` to fail if called and asserts `_way_candidate` returns `None`.
- [ ] Add one focused test for an unnamed area relation that monkeypatches `_relation_geometry` to fail if called and asserts `_relation_candidate` returns `None`.
- [ ] Run `uv run --no-cache pytest -q tests/test_pbf.py` and confirm both new tests fail because the current implementation constructs geometry before the shared name rejection.

### Task 2: Implement the minimal PBF fast path

**Files:**
- Modify: `src/osm_polygon_web_search/pbf.py`
- Test: `tests/test_pbf.py`

- [ ] Compute the normalized name before geometry in `_way_candidate` and `_relation_candidate`; return `None` for an empty key.
- [ ] Add an optional private `name_key` argument to `_candidate`, using it when supplied and preserving the existing normalization path for other callers.
- [ ] Run `uv run --no-cache pytest -q tests/test_pbf.py` and confirm all PBF tests pass.
- [ ] Run `uv run --no-cache ruff format --check .`, `uv run --no-cache ruff check .`, and `uv run --no-cache ty check` while green.

### Task 3: Benchmark and prove equivalence

**Files:**
- No repository benchmark artifacts.
- Read: `/Volumes/Seagate M3/projects/osm-polygon-web-search/liechtenstein-latest.osm.pbf`
- Read: `/Volumes/Seagate M3/projects/osm-polygon-web-search/monaco-latest.osm.pbf`

- [ ] Run a read-only before/after benchmark for both PBFs that records candidate counts, stable candidate identities, wall time, and peak RSS.
- [ ] Require candidate counts and identity sequences to match exactly; report the measured speed and memory change.
- [ ] Keep transient benchmark output under `/private/tmp` or the Seagate project root; do not create a repository artifact.

### Task 4: Run all quality gates

**Files:**
- No planned source changes; fix only evidence-backed failures in touched code/tests.

- [ ] Run the full pytest suite with line and branch coverage and require 100%.
- [ ] Run mutmut and require zero surviving or unresolved mutants.
- [ ] Run the CRAP/complexity check and require every function below 6.
- [ ] Run strict MkDocs, pre-commit, and the Docker build; if Docker is unavailable, record the exact environmental blocker rather than claiming success.
- [ ] Run `git diff --check`, review schemas/APIs/outputs/model prompts/storage, and confirm no data was added to Git.

### Task 5: Commit and publish

**Files:**
- The validated files from Tasks 1--2.

- [ ] Commit with a clear Conventional Commit message.
- [ ] Confirm the working tree is clean and inspect the commit diff.
- [ ] Push the current branch to `origin`.
- [ ] Verify the remote branch points to the pushed commit and report the exact commit and gate results.
