# Source Text Input Result Design

## Problem

`sentence_dataset._source_text_inputs` currently returns two related lists in a positional tuple. The caller must remember which list is the source-row index list and which is the text list. That is a small but avoidable coupling at a data boundary: swapping the unpacking order would remain syntactically valid while corrupting sentence-to-source alignment.

## Decision

Return a private `NamedTuple` named `_SourceTextInputs` with the fields `source_indices` and `texts`. It remains tuple-compatible, so the existing value-level behavior and any private callers that compare or unpack the result continue to work, while the production caller can use names at the boundary.

The result stays private because it is an implementation detail of the sentence-table transformation. No public API, schema, output ordering, filtering, or serialization behavior changes.

## Verification

The contract test checks both named access and the existing tuple-shaped values. The existing sentence-dataset tests continue to cover empty, null, and valid text handling and the complete test suite continues to enforce 100% line and branch coverage.
