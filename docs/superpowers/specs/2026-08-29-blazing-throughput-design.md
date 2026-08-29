# Blazing Throughput and Memory Design

## Goal

Make the existing POC pipeline substantially faster and more memory-efficient
for repeated page content and larger Parquet inputs without changing its
observable results.

## Measured context

The existing Seagate-backed POC contains 18 page rows but only 8 unique page
texts. Its 708 sentence rows contain 352 unique sentence values. The pipeline
currently sends every repeated value through SAT and LFM, even though both
approved local models receive the same input and produce one output per value.

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
2. **Deterministic content reuse plus Arrow-native expansion.** Segment each
   exact page text once, classify each exact sentence once, fan results back to
   their original rows, and build sentence Parquet output with Arrow index
   selection. Stream JSON serialization as a small memory improvement. This is
   the selected design because it removes the measured duplicate work while
   preserving the public table contract.
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
- Content reuse uses exact strings only. Repeated page text and repeated
  sentence text receive the same result they would receive in the existing
  deterministic local model path; results are expanded back to all original
  contexts.
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

The sentence expansion boundary first keeps the original page-row order,
builds a first-seen unique list of non-null text values, and sends only that
list through the scalar or batched model boundary. It maps each unique group
back to every original page row before emitting sentence rows. This keeps
duplicate query/page contexts in the output while avoiding duplicate SAT work.

### Reuse LFM labels by exact sentence

The Parquet transformation keeps the public mapping API unchanged. Its Arrow
path builds the valid sentence sequence, classifies a first-seen unique
sentence list in the existing bounded batches, and expands the labels back to
the valid source-row positions. A sentence remains attached to its original
polygon, query, URL, and other context; only the deterministic model call is
deduplicated.

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
- Tests prove duplicate LFM sentence inputs are classified once and labels are
  expanded to every original row.
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
