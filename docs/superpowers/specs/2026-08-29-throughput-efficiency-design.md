# Throughput and Efficiency Pass

## Goal

Make the existing OSM polygon web-search pipeline substantially faster and
more memory-efficient without changing its public behavior, row order, output
schema, relevance prompt, model, or Seagate-only data boundary.

## Measured context

The Liechtenstein POC measured the following local costs:

- PBF candidate scanning: approximately 5.6 seconds for 588 candidates.
- SAT segmentation: approximately 163 seconds when each page is split alone
  versus approximately 129 seconds when the same 18 pages are passed through
  SaT's supported batched API; the resulting 708 sentences were identical.
- Local LFM classification already uses one final-logit forward pass with a
  bounded batch of 16, so this pass does not change its prompt or model path.

The existing POC sentence table contains 16 query-page pairs and 8 unique
page URLs. Reusing successful page responses therefore removes duplicate
fetches without changing the rows emitted for each query.

## Options considered

1. **Micro-optimizations only.** Remove small Python allocations and repeated
   string work. This has very low risk but does not address the measured SAT
   and network costs.
2. **Bounded I/O, model batching, and Arrow-native transforms.** Fetch unique
   pages concurrently with a small fixed worker limit, batch SAT calls, and
   keep Parquet columns in Arrow rather than converting every row to nested
   Python dictionaries. This is the selected design because it targets the
   measured costs while keeping the existing module boundaries and dependency
   set.
3. **Full asynchronous/dependency rewrite.** Replace the standard-library HTTP
   path and orchestration with an async client and new connection-pooling
   dependencies. This could increase throughput, but it expands the attack
   surface, complicates provider rate limits, and is not justified for the
   current POC.

## Invariants

- Brave search requests remain sequential and use the existing retry and
  hard-failure behavior.
- Page fetch concurrency is bounded at four workers. If the configured page
  fetcher has a positive request delay, fetching remains serial so the delay
  remains meaningful.
- Successful page responses are reused by exact URL within one pipeline run;
  failed URLs are not cached and retain the existing skip/retry behavior.
- Search-result output remains in provider rank order even when page fetches
  complete out of order.
- SAT keeps the same model, segmentation settings, trimming, empty-segment
  filtering, sentence indices, and output order. Models that expose only the
  existing scalar interface continue to work; the production SaT adapter also
  exposes a batched interface.
- The LFM prompt, `LiquidAI/LFM2.5-2.6B` model, binary labels, left padding,
  direct final-logit scoring, and batch size 16 remain unchanged.
- Parquet output keeps the same columns and row values. Arrow-native selection,
  label appending, and yes-only filtering replace Python row reconstruction.
- No new runtime dependency, disk cache, queue, database, or web feature is
  introduced. Temporary and persistent project artifacts remain under the
  configured Seagate root.

## Design

### Page retrieval

Add one small fetch-batch boundary that accepts a sequence of result URLs and
returns successful `FetchedPage` objects keyed by URL. It deduplicates missing
URLs, submits at most four fetches, and collects results by the original unique
URL list. `_search_records` then walks the original search results to serialize
records in exactly the previous order. `_search_variant_records` owns one
successful-page cache for the entire run, allowing duplicate URLs across query
variants to avoid a second network request.

Only `PageFetchError` is treated as an omitted page, as before. Unexpected
exceptions still propagate. The cache is in-memory and run-scoped so it does
not add stale disk state or change the project’s storage policy.

### SAT segmentation

Keep `split_sentences(text, model)` as the scalar compatibility boundary. The
approved loaded SaT model is wrapped in a small adapter with `split_many`,
calling SaT with a bounded batch of page texts. `sentence_rows` detects that
optional capability and uses it for all valid page rows; injected scalar test
models continue through the original path. A strict result-count check and the
existing whitespace normalization preserve exact sentence-row order.

### Arrow-native Parquet work

The relevance transformer will read only the `sentence` column into Python to
identify valid sentence indices, classify those sentences in existing batches,
and use `Table.take`, `append_column`, and Arrow filtering to build the full
and yes-only tables. It will not materialize every source row as a Python
dictionary. The public `classify_rows` mapping boundary remains unchanged for
callers and focused tests.

## Testing and acceptance

Each behavior change follows RED → GREEN → REFACTOR:

- Tests prove page deduplication, bounded concurrency, failure handling, and
  deterministic result order.
- Tests prove scalar SAT compatibility, batched SAT ordering, exact sentence
  equivalence, and bounded batching.
- Tests prove Arrow output preserves rows, columns, labels, and filtering.
- Existing tests continue to cover prompt/model behavior and all CLI paths.
- The full repository gate must pass with 100% line and branch coverage,
  mutation testing with zero survivors, CRAP below 6, Ruff, ty, strict
  MkDocs, pre-commit, and the repository contract checks.
- A synthetic timing probe must show concurrent fetch speedup and a real
  Seagate SAT comparison must show equal output before the branch is merged.
