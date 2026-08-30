# Typed HTTP I/O Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the remaining `Any` opener and response annotations at the shared HTTP/provider boundary without changing runtime behavior or public APIs.

**Architecture:** Define one structural response protocol and one structural opener protocol in `http.py`. Reuse them in the transport, page fetcher, and Brave provider while retaining the existing `urlopen` defaults, lazy behavior, fallback handling, and domain-specific errors.

**Tech Stack:** Python 3.11+, `typing.Protocol`, `typing.Self`, urllib, pytest, coverage.py, Ruff, ty, mutmut, MkDocs, uv.

---

### Task 1: Add the failing HTTP-boundary contract test

**Files:**
- Modify: `tests/test_http.py`

- [x] **Step 1: Write the failing test**

Add the protocol and adapter imports, then add:

```python
def test_external_http_boundaries_have_typed_protocols() -> None:
    assert get_type_hints(request_bytes)["opener"] is HTTPOpener
    assert get_type_hints(_read_payload)["response"] is HTTPResponseLike
    assert get_type_hints(PageFetcher.__init__)["opener"] is HTTPOpener
    assert get_type_hints(BraveSearchProvider.__init__)["opener"] is HTTPOpener
```

- [x] **Step 2: Run the focused test and verify the expected RED failure**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_http.py::test_external_http_boundaries_have_typed_protocols -q
```

Expected: collection fails because `HTTPResponseLike` and `HTTPOpener` do not
exist yet.

### Task 2: Implement the minimal structural protocols

**Files:**
- Modify: `src/osm_polygon_web_search/http.py`
- Modify: `src/osm_polygon_web_search/fetch.py`
- Modify: `src/osm_polygon_web_search/search.py`

- [x] **Step 1: Add the response and opener protocols**

In `http.py`, define the protocols beside `HTTPResponse`:

```python
from typing import Protocol, Self, cast


class HTTPResponseLike(Protocol):
    status: int
    headers: HeaderValues

    def read(self, limit: int = -1) -> bytes: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: object) -> None: ...


class HTTPOpener(Protocol):
    def __call__(self, request: Request, *, timeout: float) -> HTTPResponseLike: ...


DEFAULT_HTTP_OPENER: HTTPOpener = cast(HTTPOpener, urlopen)
```

Replace the transport's opener and response `Any` annotations with these
protocols. Use `DEFAULT_HTTP_OPENER` for the three existing `urlopen`
defaults, import `HTTPOpener` in `fetch.py` and `search.py`, use it for each
constructor opener parameter, and remove only the now-unused `Any` imports.

- [x] **Step 2: Run the focused test and the HTTP/provider regression tests**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pytest tests/test_http.py::test_external_http_boundaries_have_typed_protocols tests/test_http.py tests/test_search_and_fetch.py -q
```

Expected: the new contract test and all existing transport, retry, fetch, and
search tests pass with the same exception messages and response values.

### Task 3: Refactor review and quality verification

**Files:**
- Modify only the three source modules, `tests/test_http.py`, this design note,
  and this plan.

- [x] **Step 1: Review the boundary and confirm no network behavior changed**

Run:

```bash
rg -n "\bAny\b|HTTPResponseLike|HTTPOpener|def _read_payload|opener:" src/osm_polygon_web_search/http.py src/osm_polygon_web_search/fetch.py src/osm_polygon_web_search/search.py
git diff --check
```

Expected: the three network modules contain no `Any` annotations, the two
protocols are used at every opener/response boundary, and only annotations and
imports changed outside the new test.

- [x] **Step 2: Run all static, behavioral, and documentation gates**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just check
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run ruff check --select C901,FURB .
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run pre-commit run --all-files
```

Expected: all tests pass with 100% line and branch coverage, Ruff, `ty`,
strict MkDocs, the complexity gate, and pre-commit pass.

- [x] **Step 3: Run mutation testing and build artifacts**

Run:

```bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut run --max-children 4
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv run mutmut results
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 uv build --wheel
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/osm-polygon-web-search-uv-cache-20260830 just docker
```

Expected: zero surviving or unresolved mutants, a successful wheel build, and
either a successful Docker build or a documented local-daemon limitation.

Observed: 1,574 of 1,574 mutants were killed, `mutmut results` was empty, and
the wheel build succeeded. Docker was unavailable because the local daemon
socket did not exist.

- [ ] **Step 4: Commit, push, and verify only the scoped changes**

Run:

```bash
git add src/osm_polygon_web_search/http.py src/osm_polygon_web_search/fetch.py src/osm_polygon_web_search/search.py tests/test_http.py docs/superpowers/specs/2026-08-30-http-io-boundary-design.md docs/superpowers/plans/2026-08-30-http-io-boundary-plan.md
git commit -m "refactor: type HTTP I/O boundaries"
git push origin main
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected: only the scoped files are committed, local and remote SHAs match,
and the worktree is clean.
