# Search-Record Serialization Boundary

## Context

`pipeline._search_records` currently performs four responsibilities in one
function: validating the selected plan, running a search, fetching result
pages, and converting successful pages into JSON-ready records. The final
conversion is deterministic and has no dependency on the provider or fetcher,
so it is a useful pure boundary for tests and maintenance.

## Decision

Extract `_serialize_search_results` in
`src/osm_polygon_web_search/pipeline.py`. It will accept the ordered search
results, the fetched-page mapping, and the selected place name, then return the
existing JSON-ready records. `_search_records` will retain plan validation,
provider calls, fetch concurrency selection, and cache handling, and delegate
only the final conversion.

## Invariants

- Invalid or incomplete plans still return an empty list without calling either
  dependency.
- The provider is called once with the existing query and result count.
- Fetching still receives the provider's URL order, shared cache, and existing
  worker count.
- Output records retain provider order, skip missing pages, contain the same
  `result`, `page`, and `evidence` keys, and serialize dataclasses exactly as
  before.
- Evidence matching continues to use the selected candidate's raw name.
- No public API, CLI option, output schema, or runtime dependency changes.

## Non-goals

This change does not alter search queries, page fetching, evidence matching,
concurrency, caching, error handling, or JSON serialization policy.

## Quality-gate integrity

Mutation testing must include every package module that contains executable
functions or classes, including the CLI, orchestration, search, fetch, and text
boundaries. The package initializer contains only metadata and re-exports and
is not a relevant function boundary.

The mutation configuration excludes only the JSON-dump expression because
json.dump treats ensure_ascii=None like the required false value. HTTP header
names and values are represented by module constants, while focused tests
assert the emitted headers and Unicode JSON.
