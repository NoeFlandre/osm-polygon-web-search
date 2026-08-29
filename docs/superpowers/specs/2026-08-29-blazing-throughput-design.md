# Blazing Throughput and Memory Design

## Goal

Make the existing POC pipeline substantially faster and more memory-efficient
for repeated page content and larger Parquet inputs without changing its
observable results.

## Measured context

The existing Seagate-backed POC contains 18 page rows but only 8 unique page
texts. Its 708 sentence rows contain 352 unique sentence values. The pipeline
currently sends every repeated page text through SAT. A regression audit found
that two repeated sentence values have conflicting labels in the stored LFM
output across query variants, so LFM calls cannot be deduplicated without
changing results on this runtime.

The previous pass already bounds web-page concurrency, reuses successful URLs,
batches SAT, uses one LFM forward pass per batch, and keeps relevance
transforms Arrow-native. A controlled SAT probe on the current machine showed
that increasing the SAT batch size is not monotonically faster: batch sizes 16,
32, and 64 took approximately 194, 205, and 168 seconds for the same 18 pages.
The local LFM environment selected CPU and remained too slow for a useful
multi-size probe, so model-runtime rewrites, quantization, and unbounded batch
growth are excluded from this no-regression pass.

## Options considered

1. **Micro-optimizations only.** Reduce small Python allocations and stream
   JSON output. This is very low risk but leaves repeated model inference and
   full Python row materialization untouched.
2. **Safe SAT reuse plus Arrow-native expansion.** Segment each exact page text
   once, restore the results to their original rows, and build sentence
   Parquet output with Arrow index selection. Stream JSON serialization as a
   small memory improvement, while retaining per-row LFM inference because
   the observed labels are not stable for duplicate sentence values. This is
   the selected design because it removes only proven-safe duplicate work.
3. **Model/runtime replacement.** Change model precision, quantization,
   device policy, or compilation settings. This could be faster on one machine
   but risks label drift, unsupported hardware, OOM failures, new dependencies,
   and non-reproducible results; it is not justified by the current POC.

## Invariants

- Every input row that previously produced output still produces output with
  the same values, order, row multiplicity, and sentence indices/counts.
- SAT remains `segment-any-text/sat-3l-sm` with its existing batch settings,
  whitespace normalization, empty-segment filtering, and scalar compatibility
  path.
- LFM remains `LiquidAI/LFM2.5-2.6B` with the exact existing prompt, left
  padding, final-logit comparison, binary labels, and bounded classifier
  batches.
- SAT content reuse uses exact page-text strings only. Repeated page text
  receives the same segmentation result and is expanded back to all original
  contexts. LFM classification remains per-row because the existing stored
  output demonstrates conflicting labels for some repeated sentence strings.
- Sentence Parquet output keeps all source columns and appends the same four
  sentence columns. Relevance Parquet output keeps its existing columns and
  yes-only filter.
- Brave requests remain sequential. Page fetching remains bounded at four
  workers, preserves provider order, reuses only successful exact URLs, and
  retains hard failures and retry behavior.
- No runtime dependency, persistent cache, external service, schema field, or
  storage location is added. All project data and model caches remain under the
  configured Seagate root.

## Design

### Reuse SAT segmentation by exact page text

The sentence expansion boundary first keeps the original page-row order. When
the model exposes the optional batched interface, it builds a first-seen unique
list of non-null text values and sends only that list through the batched SAT
boundary. It maps each unique group back to every original page row before
emitting sentence rows. Scalar-only compatibility models retain one call per
page. This keeps duplicate query/page contexts in the output while avoiding
duplicate production SAT work.

### Preserve per-row LFM inference

The Parquet transformation keeps the existing valid sentence sequence and
bounded batches. It does not deduplicate sentence strings: the current stored
classification table contains duplicate sentence values with different labels
across query variants. Retaining one model call per source row is therefore a
required no-regression invariant until classifier determinism is separately
established.

### Arrow-native sentence table construction

The Parquet path reads the `text` column into Python only to drive SAT. It
collects repeated source indices and the generated sentence metadata, selects
the source rows with `Table.take`, and appends typed Arrow columns. It no
longer converts the complete source table to nested Python dictionaries or
reconstructs the output with `Table.from_pylist`.

### Bounded serialization

`run_poc` writes the existing indented JSON representation directly to the
validated output file with `json.dump`, followed by the existing final newline.
This preserves the readable artifact while avoiding a second full-size JSON
string in memory.

## Testing and acceptance

Each implementation change follows RED -> GREEN -> REFACTOR:

- Tests prove duplicate SAT inputs are called once and all duplicate contexts
  retain identical output rows and indices.
- A regression audit proves that duplicate LFM sentence values with conflicting
  stored labels are not deduplicated.
- Tests prove Arrow sentence output preserves source columns, row order, row
  multiplicity, typed empty output, and exact sentence values.
- Tests prove the JSON artifact parses to the same plan and retains its final
  newline.
- The full repository gate must pass with 100% line and branch coverage,
  zero surviving mutants, CRAP below 6, Ruff, ty, strict MkDocs, pre-commit,
  and repository contract checks.
- A read-only Seagate benchmark must report duplicate counts and compare the
  old and optimized sentence outputs for exact equality without writing any
  benchmark artifact to the repository.
