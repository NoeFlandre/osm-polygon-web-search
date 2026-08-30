# Typed Pipeline Execution Design

## Problem

The pipeline has a typed `_SelectionPlan`, but `build_plan` and
`build_variant_plan` immediately erase it into a mutable `dict[str, Any]`.
`run_poc`, `_search_records`, and `_search_variant_records` then coordinate
through magic dictionary keys such as `query`, `selected`, and
`query_variants`. This couples search execution to the JSON representation and
makes invalid state expressible at the main orchestration boundary.

## Decision

Add two private immutable value objects:

- `_QueryVariant` owns one variant's `id`, `keyword`, and rendered `query` and
  can serialize itself to the existing dictionary shape.
- `_PipelinePlan` owns the typed `_SelectionPlan`, the optional ordinary query,
  and an optional tuple of typed variants. `None` means ordinary planning and
  an empty tuple means variant planning with no selected polygon, preserving
  the existing distinction between an absent `query_variants` key and an
  empty `query_variants` value.

Private builders return `_PipelinePlan`. The public `build_plan` and
`build_variant_plan` functions keep their existing signatures and return the
same JSON-compatible dictionaries by calling `as_dict()`. `run_poc` keeps the
typed plan through search execution and converts it once at the output
boundary. Private search helpers consume `_PipelinePlan` directly.

The output keys, values, insertion order, query construction, candidate
selection, provider calls, page caching, error handling, file location, and
JSON formatting remain unchanged. This is an internal representation refactor
only; no new runtime behavior or public API is introduced.

## Verification

Tests first lock the typed value-object serialization and prove that
`run_poc` passes the same typed plan to search before serializing it. Existing
pipeline tests continue to assert the exact public dictionaries and search
records, including no-selection, ordinary-query, variant, cache, concurrency,
and output-file paths. The complete repository gates must retain 100% line and
branch coverage, zero surviving mutants, and the CRAP ceiling.
