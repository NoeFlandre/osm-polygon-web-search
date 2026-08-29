# End-to-End Performance Design

## Goal

Reduce the measured PBF scan cost without changing candidate selection,
geometry, output order, schemas, public APIs, model behavior, network policy,
or the Seagate-only data boundary.

## Baseline evidence

The current full suite passes 152 tests with 100% line and branch coverage.
Ruff, ty, and strict MkDocs also pass before implementation.

On the Seagate-backed PBF snapshots, Liechtenstein scans returned 588
candidates in approximately 31--33 seconds per unprofiled run. A call-graph
profile showed approximately 361,000 object-candidate dispatches and most
Python-visible scan time in pyosmium tag iteration and node-coordinate
iteration. The current way path builds geometry before checking whether the
way has a usable name. The current named-area relation path similarly builds
relation geometry before the name check in the shared candidate helper.

The existing SAT exact-text reuse, Arrow-native sentence expansion, bounded
page fetching, JSON streaming, and one-forward-pass LFM classification are
already validated. LFM sentence reuse is explicitly unsafe because stored
duplicate sentence values have conflicting labels across query variants.

## Selected change

In `pbf.py`, compute `normalize_name(tags.get("name", ""))` before any
expensive geometry operation for both closed ways and area relations. Return
`None` immediately for an empty normalized key. For named ways, pass the
computed key into the private candidate constructor so the name is normalized
only once. For relations, retain the existing `dict(obj.tags)` and area/type
checks, then apply the same early name gate before assembling GeoJSON.

This is behavior-preserving because an object with an empty normalized name
was already rejected by `_candidate`; the change only removes work that could
not affect the result. Named-object geometry validation and all candidate
fields remain unchanged.

## Non-goals and preserved contracts

- Do not change OSM predicates, geometry validation, name normalization, name
  uniqueness, candidate ordering, or serialized fields.
- Do not change SAT, LFM, prompts, classifier batch sizes, Parquet schemas,
  network concurrency, retry behavior, or provider rate-limit behavior.
- Do not add runtime dependencies, persistent caches, queues, databases, or
  files outside `/Volumes/Seagate M3/projects/osm-polygon-web-search`.
- Do not rewrite pyosmium bindings, replace the local models, or trade exact
  output equivalence for speculative throughput.

## Verification

RED tests must prove unnamed ways and unnamed area relations skip geometry.
GREEN must preserve the existing PBF fixture output. A real before/after
benchmark on the two Seagate PBF snapshots must report candidate counts,
output equivalence, wall time, and peak resident memory. The full gate must
retain 100% line/branch coverage, zero surviving or unresolved mutants, CRAP
below 6, Ruff, ty, strict MkDocs, pre-commit, and a clean Git diff.
