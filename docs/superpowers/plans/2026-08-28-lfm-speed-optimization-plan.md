# LFM Sentence Classification Speed Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Speed up the local LFM sentence classifier without changing its prompt, labels, dataset schema, or publication contract.

**Architecture:** Keep the existing deep boundaries: the model adapter owns tokenizer/model mechanics, while the dataset transformer owns bounded row batching and Parquet outputs. Replace one-token generation with a single batched next-token logit comparison restricted to the tokenizer's `yes` and `no` tokens, and adopt batch size 16 only after a real memory smoke test.

**Tech Stack:** Python 3.11+, PyTorch, Transformers, uv, Ruff, ty, pytest/pytest-cov, mutmut, MkDocs Material, Hugging Face Hub.

---

### Task 1: Add red tests for logit-only scoring

**Files:**
- Modify: `tests/test_relevance_model.py`
- Modify: `src/osm_polygon_web_search/relevance_model.py`

- [ ] **Step 1: Write the failing tests**

Add fake tokenizer/model outputs that expose two final logits and assert that
the classifier calls the model with `logits_to_keep=1`, does not call
`generate`, maps the larger answer logit to `yes` or `no`, and resolves the
two single-token answer IDs once.

- [ ] **Step 2: Run the focused tests and verify the expected red failure**

Run:

```bash
UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-lfm-uv-cache-20260828 uv run pytest -q tests/test_relevance_model.py
```

Expected: the new logit-scoring behavior fails because the current adapter
still calls `generate` and has no final-logit path.

- [ ] **Step 3: Implement the smallest model-adapter change**

Resolve `yes` and `no` with `tokenizer.encode(..., add_special_tokens=False)`;
reject non-single-token answers; call the model with `logits_to_keep=1` under
`inference_mode`; compare only the final-position answer logits; and keep the
existing left-padding, prompt construction, device map, and strict batch-size
checks.

- [ ] **Step 4: Run the focused tests and verify green**

Run the same focused pytest command. Expected: all model-adapter tests pass,
including the existing prompt, padding, device, and batch behavior tests.

- [ ] **Step 5: Commit the focused implementation**

```bash
git add src/osm_polygon_web_search/relevance_model.py tests/test_relevance_model.py
git commit -m "perf: score local relevance labels from logits"
```

### Task 2: Measure a safe larger batch

**Files:**
- Modify: `src/osm_polygon_web_search/relevance_dataset.py`
- Modify: `tests/test_relevance_dataset.py`

- [ ] **Step 1: Write the failing batch-boundary test**

Change the bounded-batch test to use 17 rows and expect a 16-row first batch
and a one-row remainder, preserving a direct proof that the transformer does
not make unbounded calls.

- [ ] **Step 2: Run the focused dataset test and verify red**

Run:

```bash
UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-lfm-uv-cache-20260828 uv run pytest -q tests/test_relevance_dataset.py
```

Expected: the 17-row batch-size expectation fails while production still uses
8.

- [ ] **Step 3: Implement the bounded batch-size change**

Set `CLASSIFICATION_BATCH_SIZE = 16` and leave the strict `zip(...,
strict=True)` length check unchanged.

- [ ] **Step 4: Run focused tests and the real 16-sentence smoke**

Run the focused dataset tests, then load the cached model from Seagate and
classify 16 short sentences. The smoke must finish without an MPS memory
failure and return 16 labels in order. If it fails, restore batch size 8 and
rerun the focused tests; the logit-only adapter remains the optimization.

- [ ] **Step 5: Commit the measured batch change**

```bash
git add src/osm_polygon_web_search/relevance_dataset.py tests/test_relevance_dataset.py
git commit -m "perf: increase bounded relevance batch"
```

### Task 3: Run the repository quality gates

**Files:**
- No source changes expected.

- [ ] **Step 1: Run the complete standard gate**

```bash
UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-lfm-uv-cache-20260828 just check
```

Expected: Ruff format/check, `ty`, pytest with 100% line/branch coverage, and
strict MkDocs all pass.

- [ ] **Step 2: Run mutation testing and pre-commit**

```bash
UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-lfm-uv-cache-20260828 just mutation
PRE_COMMIT_HOME=/private/tmp/osm-polygon-web-search-lfm-precommit-20260828 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-lfm-uv-cache-20260828 uv run pre-commit run --all-files
```

Expected: zero surviving mutants and all hooks pass.

### Task 4: Classify and publish the verified results

**Files:**
- Create on Seagate only: `/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/classified/train.parquet`
- Create on Seagate only: `/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/hf-viewer/train.parquet`

- [ ] **Step 1: Run the full 708-sentence local classifier**

Use the existing SAT sentence table, Seagate-only HF/Torch caches, offline
mode, and the approved local model. Do not upload or replace remote data until
the command exits successfully.

- [ ] **Step 2: Validate both Parquet outputs**

Verify 708 classified rows, every label is `yes` or `no`, the relevant output
contains only `yes`, the original columns are preserved, and the model column
is exactly `LiquidAI/LFM2.5-2.6B`.

- [ ] **Step 3: Replace and verify the existing HF artifact**

Copy only the validated relevant table into a fresh Seagate HF staging clone,
commit the replacement `train.parquet`, push to
`NoeFlandre/osm-polygon-web-search`, download the remote artifact directly,
and compare bytes, schema, row count, and commit metadata.
