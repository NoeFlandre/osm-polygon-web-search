# Data-root Boundary Quality Refactor

**Date:** 2026-08-30
**Status:** Approved by the explicit autonomous quality-refactor request

## Goal

Make the Seagate-only path policy live in the module that owns the data root,
without changing the function's behavior, import compatibility, output paths,
or public pipeline behavior.

## Design

Move `ensure_data_path` from `pipeline.py` to `data_root.py`, alongside
`DATA_ROOT` and `data_root`. `pipeline.py` will import the function so its
existing `pipeline.ensure_data_path` attribute remains available as a
compatibility alias. `sentence_dataset.py` and `relevance_dataset.py` will
depend directly on `data_root.py`, removing their unnecessary dependency on
the orchestration module.

The implementation, path expansion/resolution order, containment check, and
error message remain unchanged. No new path abstraction, configuration, or
filesystem behavior is introduced.

## Testing and quality

Add a failing test for the new data-root boundary and a compatibility test
that the pipeline exposes the same function object. Run the focused red test,
make the smallest relocation, then run the focused green tests and the full
quality gate. Include `data_root.py` in the configured mutation scope so the
moved policy is subject to the same zero-survivor requirement.

## Out of scope

This refactor does not change the Seagate root, accepted/rejected paths,
dataset schemas, CLI behavior, pipeline plans, search behavior, or any remote
artifact.
