# Focused Quality Refactor Plan

## Goal

Remove the remaining concrete coupling and duplicated validation identified by
the 2026-08-30 audit without changing public APIs, output schemas, search
behavior, or the Seagate-only data boundary.

## Design

1. Extract the shared candidate-only plan construction from `build_plan` and
   `build_variant_plan`. Variant planning will no longer construct and discard
   an ordinary query.
2. Centralize the definition of a non-empty sentence and use it in both the
   mapping-row and Arrow/Parquet classification paths.
3. Rename shadowed sentence-expansion indices for direct, unambiguous intent.

The refactor is deliberately narrow: the existing domain boundaries, provider
interfaces, schemas, and runtime policies are already cohesive and protected
by full branch coverage. No new abstraction is added without a concrete
duplicate or coupling problem.

## TDD and verification

For each production change: add a focused failing regression test, verify the
red failure, implement the smallest change, verify green, then refactor while
the suite remains green. Finish with full tests and coverage, Ruff, `ty`,
strict MkDocs, mutation testing, the CRAP/complexity check, pre-commit, and a
Docker build when the local daemon is available.
