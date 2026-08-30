# Sentence-table Boundary Quality Refactor

**Date:** 2026-08-30
**Status:** Approved by the explicit autonomous quality-refactor request

## Goal

Make the Arrow sentence-table transformation easier to understand and test
without changing its public API, output schema, row ordering, batching,
sentence model behavior, or Seagate-only storage policy.

## Problem

`sentence_dataset._sentence_table` currently owns three distinct operations:
selecting source rows that contain string text, expanding each model result into
sentence metadata, and assembling the Arrow table. The function is correct and
covered, but the expansion bookkeeping is embedded in the storage adapter,
which makes the ordering and index contract harder to inspect independently.

## Design

Add two private, deterministic helpers in `sentence_dataset.py`:

- `_source_text_inputs` returns the source row indices and string texts in their
  existing order. It preserves the current rule that every string, including
  an empty string, is passed to the segmentation boundary.
- `_expand_sentence_groups` converts source indices and cleaned sentence groups
  into the four ordered Arrow inputs: repeated source indices, sentence text,
  zero-based sentence indices, and per-sentence group counts.

`_sentence_table` will call those helpers and retain responsibility only for
model segmentation, Arrow row selection, typed column construction, and the
existing column order. The helpers will use ordinary lists and a tuple return
value; no new public type, storage abstraction, cache, or runtime policy will
be introduced.

## Compatibility and non-goals

The scalar and batched sentence-model interfaces remain unchanged. Empty and
duplicate source texts retain their current model-call and row-expansion
behavior. `transform_parquet`, `sentence_rows`, output paths, schemas, model
metadata, and error behavior remain unchanged. No new dependency, feature,
CLI option, or dataset field is part of this refactor.

## Testing and quality

Start with a focused failing test for the pure expansion contract, then add the
smallest implementation, verify green, and refactor `_sentence_table` while
keeping the full suite green. Existing Arrow integration tests remain regression
coverage for exact schemas and rows. Finish with full tests and branch
coverage, Ruff including C901, `ty`, strict MkDocs, pre-commit, mutation
testing, the repository CRAP contract, wheel build, and Docker verification if
the local daemon is available.
