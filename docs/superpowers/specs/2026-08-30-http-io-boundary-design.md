# Typed HTTP I/O boundary design

## Problem

The shared HTTP transport and both network adapters accept opener and response
objects through `Any`. The response value is already normalized into the
typed `HTTPResponse` dataclass, but the external boundary before that point is
unconstrained. This weakens static checking exactly where request, retry, and
payload behavior meet the standard-library transport.

## Decision

Define two small structural protocols in `http.py`:

- `HTTPResponseLike` describes the context-managed response used by the
  transport: `read`, `status`, and `headers`.
- `HTTPOpener` describes a callable accepting a `Request` and keyword timeout
  and returning an `HTTPResponseLike`.

Use these protocols for `request_bytes`, `_request_once`, `_read_payload`,
`PageFetcher`, and `BraveSearchProvider`. Keep the existing lazy/default
`urlopen` wiring, status/header fallbacks, retry policy, error translation,
payload limits, and public constructor/method signatures unchanged.

Because typeshed exposes `urlopen` as an overloaded function with a broader
signature, adapt it once with a module-level `DEFAULT_HTTP_OPENER`. `cast`
returns the same callable at runtime, so this is a static typing bridge rather
than a wrapper or a behavior change.

## Compatibility

This is an annotation-only boundary refactor. It adds no runtime validation,
network calls, retries, caching, concurrency, dependencies, or output fields.
The existing fake response objects remain valid at runtime, including the
status/header-less response covered by the transport tests.

## Verification

Add a contract test for the four typed opener/response annotations, then run
the complete test and branch-coverage suite, Ruff including complexity checks,
`ty`, strict MkDocs, pre-commit, mutation testing, and the wheel build. The
Docker check remains environment-dependent on the local daemon.
