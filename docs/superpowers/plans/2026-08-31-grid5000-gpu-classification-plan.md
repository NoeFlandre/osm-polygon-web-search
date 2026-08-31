# Grid’5000 GPU relevance classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify the expanded two-polygon sentence table on one bounded Nantes Grid’5000 GPU reservation and publish the validated yes-only result.

**Architecture:** The Seagate runner sends a deterministic gzip JSON payload containing only valid sentence row indices and sentence text to a checked-out worker in a unique Grid’5000 `/home` run directory. One OAR job runs the existing LFM prompt/model on CUDA, checkpoints labels per batch, and returns labels; the local runner joins them with the original Parquet table and uploads only the relevant subset to Hugging Face.

**Tech Stack:** Python 3.12, uv, PyTorch, Transformers, CUDA, Grid’5000 OAR, SSH/SCP, PyArrow, pytest, Ruff, ty, mutmut, MkDocs.

---

### Task 1: Add failing tests for the Seagate payload contract

**Files:**
- Create: `tests/test_grid5000.py`
- Modify: `src/osm_polygon_web_search/grid5000.py` only after RED

- [ ] **Step 1: Write failing tests** for skipping blank/non-string sentences, deterministic gzip payloads, payload metadata, and exact data-root enforcement.
- [ ] **Step 2: Run** `uv run pytest -q tests/test_grid5000.py` and verify failure because the new payload API does not exist.
- [ ] **Step 3: Implement** the smallest typed payload encoder/decoder in `grid5000.py`.
- [ ] **Step 4: Run** the focused tests and then the existing relevance dataset tests.

### Task 2: Add failing tests for GPU loading and worker checkpointing

**Files:**
- Modify: `tests/test_relevance_model.py`
- Create: `tests/test_grid5000_worker.py`
- Modify: `src/osm_polygon_web_search/relevance_model.py` only after RED
- Create: `src/osm_polygon_web_search/grid5000_worker.py` only after RED
- Create: `scripts/grid5000_relevance_worker.py` as a thin CLI wrapper

- [ ] **Step 1: Write failing tests** for an explicit `cuda` device, exact model kwargs, ordered batch labels, checkpoint writes, resume from a complete prefix, and malformed checkpoint rejection.
- [ ] **Step 2: Run** the focused tests and verify the expected missing-API failures.
- [ ] **Step 3: Add** the optional device argument while preserving the no-argument auto-device API; implement the worker around `LfmRelevanceClassifier`.
- [ ] **Step 4: Run** worker and relevance-model tests, then refactor only while green.

### Task 3: Add failing tests for OAR/SSH command and result contracts

**Files:**
- Modify: `tests/test_grid5000.py`
- Modify: `src/osm_polygon_web_search/grid5000.py` only after RED

- [ ] **Step 1: Write failing tests** for the exact Nantes resource request, shell-quoted remote paths, job-ID parsing, terminal-state handling, policy output validation, duplicate-run refusal, and label-order validation.
- [ ] **Step 2: Run** focused tests and verify they fail for the missing command helpers.
- [ ] **Step 3: Implement** pure command builders and strict parsers with no live subprocess calls.
- [ ] **Step 4: Run** focused tests and inspect the diff for credential/path leaks.

### Task 4: Add failing tests for local Parquet materialization

**Files:**
- Modify: `tests/test_relevance_dataset.py`
- Modify: `src/osm_polygon_web_search/relevance_dataset.py` only after RED
- Modify: `tests/test_grid5000.py`
- Modify: `src/osm_polygon_web_search/grid5000.py` only after RED

- [ ] **Step 1: Write failing tests** for applying ordered labels to valid source rows, preserving Arrow schema, writing complete and yes-only tables, and rejecting count/index/label mismatches.
- [ ] **Step 2: Run** the focused tests and verify the expected failures.
- [ ] **Step 3: Implement** one shared Arrow materialization helper and call it from both local and Grid’5000 paths.
- [ ] **Step 4: Run** all relevance and Grid’5000 tests and refactor duplication only while green.

### Task 5: Implement the bounded Grid’5000 runner and documentation

**Files:**
- Create: `scripts/run_grid5000_relevance.py`
- Modify: `README.md`
- Modify: `docs/getting-started.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data-layout.md`

- [ ] **Step 1:** Add a CLI that validates Seagate paths, creates the payload, runs policy check, checks out the exact pushed commit, transfers the payload/worker, submits one OAR job, polls without duplicate submission, retrieves labels/logs, validates them, and materializes outputs.
- [ ] **Step 2:** Add a remote job script using `uv`, `cuda-toolkit`, a `/tmp` model cache, per-batch checkpointing, and exact cleanup.
- [ ] **Step 3:** Run local command-construction and worker tests; do not submit until every local gate passes.

### Task 6: Validate, commit, and push the implementation

- [ ] **Step 1:** Run `uv run ruff format --check .`, `uv run ruff check .`, `uv run ty check`, full pytest/coverage, strict MkDocs, and mutmut with complete status accounting.
- [ ] **Step 2:** Commit only the scoped code/docs/tests with a Conventional Commit message and push `main`.
- [ ] **Step 3:** Verify local and GitHub commit IDs match before the live reservation.

### Task 7: Run one Grid’5000 job and publish the refreshed dataset

- [ ] **Step 1:** Run `usagepolicycheck -t` on Nantes, submit exactly one `host=1/gpu=1,walltime=0:30` job, and record the OAR ID.
- [ ] **Step 2:** Poll the single job, retrieve and validate its labels/checkpoint/logs, run the post-job policy check, and clean only confirmed project-owned remote temporary files.
- [ ] **Step 3:** Analyze local counts, URL diversity, sentence yield, and yes-rate against the prior Seagate run.
- [ ] **Step 4:** Replace the HF `train.parquet` and source card, push the dataset, download it to Seagate for hash/schema/row verification, and report the exact remote commit and job ID.
