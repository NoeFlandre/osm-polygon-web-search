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

## Selected changes

### Native entity filtering

The fresh profile after the first optimization showed that pyosmium still
constructed Python wrappers for every node and raw relation even though the
Python boundary only handles ways and assembled areas. A read-only probe using
`osmium.filter.EntityFilter(WAY | AREA)` reduced the scan from 1.27 to 0.296
seconds for Liechtenstein and from 0.286 to 0.063 seconds for Monaco, with
exact candidate equality. A second native `KeyFilter("name")` probe reduced
the entity-filtered median by another 1.76x for Liechtenstein and 1.47x for
Monaco, again with exact candidate equality. The production processor will
retain its location cache and area assembly, restrict the second-pass reader
to `NODE | WAY` (the area manager still reads relations in its internal first
pass), and filter the iterator before the Python loop so only named ways and
assembled areas cross that boundary.

This is behavior-preserving because node and way objects remain available to
the location-cache handler and area assembly, relation processing remains in
the area manager's first pass, and only objects that `_object_candidate`
already ignored for their entity type or missing name are excluded from the
consumer loop. Objects with a present but blank name still cross the native
key filter and retain the Python normalization behavior.

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
GREEN must preserve the existing PBF fixture output and prove that the native
entity and name filters are configured for ways and areas. A real before/after
benchmark on the two Seagate PBF snapshots must report candidate counts,
output equivalence, wall time, and peak resident memory. The full gate must
retain 100% line/branch coverage, zero surviving or unresolved mutants, CRAP
below 6, Ruff, ty, strict MkDocs, pre-commit, and a clean Git diff.
