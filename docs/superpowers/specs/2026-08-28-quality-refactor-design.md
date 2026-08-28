# Behavior-Preserving Quality Refactor Design

**Date:** 2026-08-28
**Status:** Approved for implementation from the explicit refactor request

## Goal

Improve the internal structure of the OSM polygon web-search package without
changing its public behavior, output contracts, network policy, or data
boundary. The refactor must leave no known duplicate implementation logic,
must not introduce dead production code, and must keep every CRAP score below
6.

## Baseline

The clean baseline at commit `638dac2` is:

- 81 tests passing;
- 100% line and branch coverage;
- 226 of 226 configured mutants killed;
- Ruff, ty, and strict MkDocs passing;
- three functions above the desired cyclomatic-complexity threshold of 5:
  `PageFetcher.fetch`, `BraveSearchProvider.search`, and `scan_pbf`.

## Design

### Shared HTTP retry boundary

Add a small `retry.py` policy module that owns the retryable status codes,
`Retry-After` parsing, exponential-backoff calculation, and sleep decision.
Add an `http.py` transport module that performs one bounded byte request with
the injected opener and applies that retry policy. It returns a typed response
including status, headers, payload, and an HTTP error when the server raised one;
transport failures remain explicit exceptions.

`PageFetcher` and `BraveSearchProvider` retain their existing constructors,
domain-specific exceptions, status validation, payload limits, parsing, and
observable messages. They become adapters around the shared transport instead
of carrying duplicate retry loops. No new provider, retry status, cache, or
concurrency behavior is added.

### Candidate-domain ownership

Move the physical/secondary tag priorities and `select_candidate` into
`candidates.py`, where candidate selection belongs. `pipeline.py` imports that
function so the existing import path remains usable while the pipeline keeps
only orchestration and output-manifest responsibilities. Selection ordering
and uniqueness behavior remain byte-for-byte equivalent.

### Documentation contract

Remove the stale `landuse` field from the Hugging Face dataset-card field table
so the checked-in card matches the currently published 20-column artifact.
Add a repository quality contract for the complexity threshold and document
the relationship between the threshold, 100% coverage, and CRAP.

## Testing and quality gates

Each production change starts with a focused failing test, followed by the
smallest implementation and a green refactor. Shared retry/transport behavior
gets direct contract tests; existing adapter tests remain as regression tests.
Candidate-selection tests move to the candidate module while the pipeline
contract continues to cover its use of the function. The dataset-card contract
test is added before the stale field is removed.

The final gates are:

```text
just check
just mutation
docker build -t osm-polygon-web-search:quality-refactor .
uv run pre-commit run --all-files
```

The Ruff McCabe gate is configured at 5. With the required 100% branch
coverage, the CRAP formula reduces to cyclomatic complexity, so every function
has CRAP <= 5 and therefore below 6.

## Out of scope

This work does not change query variants, candidate eligibility, search
provider policy, rate limits, extraction behavior, dataset contents, remote
repositories, public API names, or the Seagate-only data boundary. It does not
remove `FetchedPage.html`, which remains part of the page-provider value
object, or add a new abstraction without a direct duplication or complexity
problem to solve.
