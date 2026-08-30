# Sentence-expansion boundary

## Problem

`sentence_dataset.py` returns four related lists from
`_expand_sentence_groups`. The positional tuple is easy to misread or
reorder, and `_sentence_table` must keep the destructuring order synchronized
with the producer.

## Decision

Represent the existing four-value result with a private `NamedTuple` named
`_SentenceExpansion`. It remains tuple-compatible, so the private helper's
existing sequence shape and equality behavior are preserved, while callers can
use descriptive attributes. `_sentence_table` will consume those attributes.

## Compatibility boundary

- Preserve source row order, sentence values, sentence indices, sentence
  counts, Arrow schemas, and output rows exactly.
- Keep `_expand_sentence_groups` private and retain its four-item tuple
  semantics for existing callers.
- Do not change segmentation, batching, Parquet I/O, dependencies, or public
  APIs.
