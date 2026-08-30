# Sentence-input collection boundary

## Problem

`relevance_dataset.py` applies the shared `_iter_sentence_inputs` boundary in
two places, but each caller repeats the same parallel-list accumulation. The
repetition is unnecessary and makes it easier for row-oriented and Parquet
processing to diverge in ordering or filtering.

## Decision

Add one private `_collect_sentence_inputs` helper in
`src/osm_polygon_web_search/relevance_dataset.py`. It will consume the existing
validated iterator and return `(sources, sentences)` in source order. Both
`classify_rows` and `transform_parquet` will use it; the existing iterator and
all public functions remain unchanged.

## Compatibility boundary

- Keep `_non_empty_sentence` and `_iter_sentence_inputs` behavior unchanged.
- Preserve skipped values, source indices, sentence order, classifier batching,
  Arrow row order, output schemas, labels, errors, and CLI behavior.
- Do not change dependencies, data paths, model configuration, or published
  dataset artifacts.
