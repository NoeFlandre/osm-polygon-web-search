# Behavior-Preserving Quality Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Remove concrete internal duplication and lower cyclomatic complexity without changing public behavior, while keeping 100% coverage, zero surviving mutants, and every CRAP score below 6.

**Architecture:** A shared retry policy and bounded HTTP-byte transport will own mechanics common to the search and page adapters. Candidate selection will live with the candidate domain; the pipeline will remain orchestration. Ruff C901 complexity <= 5 plus the existing 100% branch coverage enforces CRAP <= 5.

**Tech Stack:** Python 3.11+, uv, Ruff, ty, pytest/pytest-cov, mutmut, MkDocs Material, Docker.

---

## Baseline and constraints

Start from commit 638dac2 in the isolated refactor/quality-boundaries worktree.
The verified baseline is 81 passing tests, 100% line and branch coverage, and
226/226 killed mutants. Do not change query strings, retryable status codes,
retry counts, error classes, payload limits, extraction behavior, candidate
ordering, output manifests, public import paths, or the Seagate data boundary.
Do not touch runs/ or remote repositories.

### Task 1: Share retry policy and bounded HTTP transport

**Files:**

- Create: src/osm_polygon_web_search/retry.py
- Create: src/osm_polygon_web_search/http.py
- Create: tests/test_retry.py
- Create: tests/test_http.py
- Modify: src/osm_polygon_web_search/fetch.py
- Modify: src/osm_polygon_web_search/search.py
- Modify: tests/test_search_and_fetch.py
- Modify: pyproject.toml

- [ ] **Step 1: Write retry-policy RED tests**

Create tests/test_retry.py before the production module:

~~~python
from email.message import Message

from osm_polygon_web_search.retry import retry_delay, wait_before_retry


def headers(value: str | None = None) -> Message:
    result = Message()
    if value is not None:
        result["Retry-After"] = value
    return result


def test_retry_delay_prefers_valid_retry_after() -> None:
    assert retry_delay(headers("3"), 1, 2.0) == 3.0


def test_retry_delay_uses_backoff_for_missing_or_invalid_header() -> None:
    assert retry_delay(None, 1, 2.0) == 4.0
    assert retry_delay(headers("later"), 1, 2.0) == 4.0


def test_wait_before_retry_only_sleeps_for_retryable_attempts() -> None:
    sleeps: list[float] = []
    assert wait_before_retry(
        503, headers("0"), attempt=0, max_retries=1,
        backoff_seconds=2.0, sleep=sleeps.append,
    )
    assert not wait_before_retry(
        500, headers("0"), attempt=0, max_retries=1,
        backoff_seconds=2.0, sleep=sleeps.append,
    )
    assert not wait_before_retry(
        503, headers("0"), attempt=1, max_retries=1,
        backoff_seconds=2.0, sleep=sleeps.append,
    )
    assert sleeps == [0.0]
~~~

- [ ] **Step 2: Verify RED**

Run:

~~~text
/Users/noeflandre/osm-polygon-web-search/.venv/bin/pytest -q tests/test_retry.py
~~~

Expected: collection fails because osm_polygon_web_search.retry does not yet
exist.

- [ ] **Step 3: Implement the minimal retry policy**

Create retry.py with one implementation of status handling, Retry-After parsing,
and exponential backoff:

~~~python
import time
from collections.abc import Callable, Mapping

_RETRYABLE_STATUS_CODES = frozenset({429, 503})


def retry_delay(
    headers: Mapping[str, str] | None,
    attempt: int,
    backoff_seconds: float,
) -> float:
    retry_after = headers.get("Retry-After") if headers is not None else None
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    return backoff_seconds * (2**attempt)


def wait_before_retry(
    status: int,
    headers: Mapping[str, str] | None,
    *,
    attempt: int,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    if status not in _RETRYABLE_STATUS_CODES or attempt >= max_retries:
        return False
    sleep(retry_delay(headers, attempt, backoff_seconds))
    return True
~~~

Run tests/test_retry.py again; expect all three tests to pass.

- [ ] **Step 4: Write HTTP transport RED tests**

Create tests/test_http.py with a real transport contract:

~~~python
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from osm_polygon_web_search.http import HTTPRequestError, request_bytes


class Response:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.headers: dict[str, str] = {}

    def read(self, limit: int = -1) -> bytes:
        return self.payload if limit < 0 else self.payload[:limit]

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_request_bytes_returns_response_data() -> None:
    result = request_bytes(
        Request("https://example.test"),
        opener=lambda request, timeout: Response(b"ready"),
        timeout=1.0,
        max_retries=0,
        backoff_seconds=0.0,
        sleep=lambda delay: None,
    )
    assert (result.status, result.payload, result.error) == (200, b"ready", None)


def test_request_bytes_retries_http_and_response_statuses() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
        if attempts == 2:
            return Response(b"busy", status=503)
        return Response(b"ready")

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        timeout=1.0,
        max_retries=2,
        backoff_seconds=0.0,
        sleep=sleeps.append,
    )
    assert result.payload == b"ready"
    assert (attempts, sleeps) == (3, [0.0, 0.0])


def test_request_bytes_returns_nonretryable_http_error() -> None:
    def opener(request, timeout):
        raise HTTPError(request.full_url, 404, "missing", {}, None)

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        timeout=1.0,
        max_retries=1,
        backoff_seconds=0.0,
        sleep=lambda delay: None,
    )
    assert result.status == 404
    assert result.error is not None


def test_request_bytes_wraps_transport_errors() -> None:
    def opener(request, timeout):
        raise URLError("offline")

    with pytest.raises(HTTPRequestError, match="request failed"):
        request_bytes(
            Request("https://example.test"),
            opener=opener,
            timeout=1.0,
            max_retries=0,
            backoff_seconds=0.0,
            sleep=lambda delay: None,
        )
~~~

- [ ] **Step 5: Verify HTTP RED**

Run:

~~~text
/Users/noeflandre/osm-polygon-web-search/.venv/bin/pytest -q tests/test_http.py
~~~

Expected: collection fails because osm_polygon_web_search.http does not yet
exist.

- [ ] **Step 6: Implement the minimal transport**

Create http.py with HTTPRequestError, HTTPResponse, request_bytes,
_request_once, and _read_payload. The transport retries via
wait_before_retry, returns non-success HTTP responses to the adapters for
their existing domain-specific messages, converts HTTPError into
HTTPResponse.error, and wraps only URLError/OSError as HTTPRequestError. The
read_limit argument must be passed to the response object when present.

Use this request loop:

~~~python
for attempt in range(max_retries + 1):
    response = _request_once(
        request, opener=opener, timeout=timeout, read_limit=read_limit
    )
    if wait_before_retry(
        response.status,
        response.headers,
        attempt=attempt,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        sleep=sleep,
    ):
        continue
    return response
raise HTTPRequestError(f"request retries exhausted for {request.full_url}")
~~~

Run both new test files; expect them GREEN before touching the adapters.

- [ ] **Step 7: Refactor adapters after GREEN**

Replace both local retry loops and both private _retry_delay functions with
request_bytes. Preserve the existing request headers, constructor arguments,
error classes/messages, status checks, page-size check, and JSON mapping. Keep
PageFetcher.html in FetchedPage. Extract search JSON mapping into a small
_parse_results helper so search remains simple. Update adapter tests to import
shared retry functions from retry.py, and retain every existing rate-limit,
HTTP, transport, and parsing regression test.

- [ ] **Step 8: Verify focused GREEN**

Run:

~~~text
/Users/noeflandre/osm-polygon-web-search/.venv/bin/pytest -q tests/test_retry.py tests/test_http.py tests/test_search_and_fetch.py
~~~

Expected: all focused tests pass.

- [ ] **Step 9: Include new modules in mutation scope and commit**

Add both new source files to tool.mutmut.only_mutate, rerun the focused tests,
then commit:

~~~text
git add src/osm_polygon_web_search/retry.py src/osm_polygon_web_search/http.py src/osm_polygon_web_search/fetch.py src/osm_polygon_web_search/search.py tests/test_retry.py tests/test_http.py tests/test_search_and_fetch.py pyproject.toml
git commit -m "refactor: share HTTP retry transport"
~~~

### Task 2: Move candidate selection into its domain module

**Files:**

- Modify: src/osm_polygon_web_search/candidates.py
- Modify: src/osm_polygon_web_search/pipeline.py
- Modify: tests/test_candidates.py
- Modify: tests/test_pipeline.py

- [ ] **Step 1: Write the candidate-boundary RED test**

Import select_candidate from osm_polygon_web_search.candidates in
tests/test_candidates.py and add:

~~~python
def test_selection_prefers_physical_landscape_tags_after_uniqueness() -> None:
    building = PolygonCandidate(
        "way", 1, "A building", "a building",
        {"name": "A building", "building": "yes"},
        {"type": "Polygon", "coordinates": []},
    )
    meadow = PolygonCandidate(
        "way", 2, "B meadow", "b meadow",
        {"name": "B meadow", "landuse": "meadow"},
        {"type": "Polygon", "coordinates": []},
    )
    assert select_candidate([building, meadow]) is meadow
~~~

Run pytest -q tests/test_candidates.py; expected RED import failure.

- [ ] **Step 2: Move implementation without changing behavior**

Move _PRIMARY_PHYSICAL_TAGS, _SECONDARY_PLACE_TAGS, and the exact
select_candidate sort key into candidates.py. Import select_candidate into
pipeline.py so pipeline.select_candidate continues to resolve for existing
consumers. Remove the old local constants and function. Move the selection-only
tests from test_pipeline.py to test_candidates.py, retaining pipeline tests for
orchestration.

- [ ] **Step 3: Verify GREEN and commit**

Run:

~~~text
/Users/noeflandre/osm-polygon-web-search/.venv/bin/pytest -q tests/test_candidates.py tests/test_pipeline.py
~~~

Expected: all tests pass. Commit:

~~~text
git add src/osm_polygon_web_search/candidates.py src/osm_polygon_web_search/pipeline.py tests/test_candidates.py tests/test_pipeline.py
git commit -m "refactor: move selection into candidate domain"
~~~

### Task 3: Enforce CRAP ceiling and correct the checked-in schema contract

**Files:**

- Modify: pyproject.toml
- Modify: dataset/README.md
- Modify: docs/development.md
- Modify: tests/test_repository_contracts.py
- Modify: src/osm_polygon_web_search/fetch.py
- Modify: src/osm_polygon_web_search/search.py
- Modify: src/osm_polygon_web_search/pbf.py

- [ ] **Step 1: Add failing contract tests**

Add:

~~~python
def test_ruff_enforces_the_crap_complexity_ceiling() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    assert '"C90"' in text
    assert "max-complexity = 5" in text


def test_dataset_card_matches_the_published_schema() -> None:
    assert "landuse" not in (ROOT / "dataset" / "README.md").read_text()
~~~

Run both test node IDs; both must fail before the config/card edits.

- [ ] **Step 2: Add the executable complexity gate**

Add "C90" to Ruff's selected rules and add:

~~~toml
[tool.ruff.lint.mccabe]
max-complexity = 5
~~~

- [ ] **Step 3: Split and verify the remaining complex function**

Task 1 splits PageFetcher.fetch and BraveSearchProvider.search while preserving
their behavior. Now refactor scan_pbf into single-purpose private helpers for
way handling and relation handling. Keep all inputs, outputs, exceptions,
ordering, and side effects unchanged, then verify all three functions are at or
below the threshold. Run:

~~~text
/Users/noeflandre/osm-polygon-web-search/.venv/bin/ruff check src tests --select C901
~~~

Expected: no C901 errors.

- [ ] **Step 4: Correct documentation and verify GREEN**

Remove landuse from the dataset-card field table. Document in docs/development.md
that C901 <= 5 plus required 100% branch coverage enforces CRAP below 6. Run:

~~~text
/Users/noeflandre/osm-polygon-web-search/.venv/bin/pytest -q tests/test_repository_contracts.py
~~~

Expected: all repository contract tests pass. Commit:

~~~text
git add pyproject.toml dataset/README.md docs/development.md tests/test_repository_contracts.py src/osm_polygon_web_search/fetch.py src/osm_polygon_web_search/search.py src/osm_polygon_web_search/pbf.py
git commit -m "build: enforce low-complexity quality gate"
~~~

### Task 4: Full verification and integration

- [ ] **Step 1: Run every quality gate**

From the worktree:

~~~text
UV_CACHE_DIR=/Volumes/Seagate\ M3/projects/osm-polygon-web-search/.uv-cache-quality-refactor-20260828 just check
UV_CACHE_DIR=/Volumes/Seagate\ M3/projects/osm-polygon-web-search/.uv-cache-quality-refactor-20260828 just mutation
docker build -t osm-polygon-web-search:quality-refactor .
uv run pre-commit run --all-files
~~~

Expected: all commands exit 0; report exact test, coverage, complexity, and
mutation counts.

- [ ] **Step 2: Audit duplicate and dead paths**

Run:

~~~text
rg -n '_retry_delay|_PRIMARY_PHYSICAL_TAGS|_SECONDARY_PLACE_TAGS|select_candidate' src tests
ruff check src tests --select F
git diff --check
git status --short
~~~

Expected: one retry-policy implementation, one selection implementation, no
unused-import diagnostics, no whitespace errors, and only intended changes.

- [ ] **Step 3: Review and merge**

Request final spec-compliance and code-quality review. Fix every Critical or
Important finding, rerun all gates, then merge this branch into main locally.
Do not push remote repositories; this request authorizes local code quality work
only.
