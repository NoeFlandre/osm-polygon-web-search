# PBF Web Search Proof of Concept Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scan the pinned Liechtenstein PBF for named polygon candidates, keep one name-unique candidate, build the deterministic query `"<polygon name>" "Liechtenstein" "landuse description"`, optionally search through Brave, and extract page text with Trafilatura while keeping all generated data on the Seagate.

**Architecture:** Use a PBF-first pipeline with pure selection and query modules, a pyosmium adapter for closed ways and area relations, a provider protocol with a Brave Search implementation, and a Trafilatura-based page extractor. The first run is sequential and resumable through explicit Seagate output paths; network access is opt-in and absent from tests.

**Tech Stack:** Python 3.11, uv, pyosmium, Trafilatura, urllib, pytest, Ruff, ty, mutmut, MkDocs Material, Docker.

---

### Task 1: Add the failing selection and query tests

**Files:**
- Create: `tests/test_candidates.py`
- Create: `tests/test_queries.py`
- Create: `tests/test_country.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_candidates.py
from osm_polygon_web_search.candidates import PolygonCandidate, unique_candidates
from osm_polygon_web_search.names import normalize_name


def candidate(osm_type: str, osm_id: int, name: str) -> PolygonCandidate:
    return PolygonCandidate(
        osm_type=osm_type,
        osm_id=osm_id,
        name_raw=name,
        name_key=normalize_name(name),
        tags={"name": name},
        geometry={"type": "Polygon", "coordinates": []},
    )


def test_duplicate_names_are_all_excluded_across_ways_and_relations() -> None:
    candidates = [
        candidate("way", 1, "Parking"),
        candidate("relation", 2, " parking "),
        candidate("way", 3, "Unique Meadow"),
    ]

    assert unique_candidates(candidates) == [candidates[2]]


def test_name_normalization_is_case_and_unicode_stable() -> None:
    assert normalize_name("  Café\u0301  ") == "café"


def test_candidate_identity_includes_osm_type_and_id() -> None:
    item = candidate("relation", 42, "A place")

    assert item.identity == ("relation", 42)
```

```python
# tests/test_queries.py
from osm_polygon_web_search.queries import build_query


def test_query_quotes_place_and_country_and_includes_keywords() -> None:
    assert build_query("Alp X", "Liechtenstein", ["geology", "terrain"]) == (
        '"Alp X" "Liechtenstein" (geology OR terrain)'
    )


def test_query_escapes_embedded_quotes() -> None:
    assert build_query('A "B"', "Liechtenstein", ["geology"]) == (
        '"A B" "Liechtenstein" geology'
    )
```

```python
# tests/test_country.py
from pathlib import Path

from osm_polygon_web_search.country import country_from_pbf


def test_country_comes_from_the_pbf_basename() -> None:
    assert country_from_pbf(Path("liechtenstein-latest.osm.pbf")) == "Liechtenstein"


def test_country_does_not_call_a_geocoder_or_inspect_the_filesystem() -> None:
    assert country_from_pbf(Path("liechtenstein.osm.pbf")) == "Liechtenstein"
```

- [ ] **Step 2: Run the focused tests and verify the expected RED failure**

Run: `uv run pytest -q tests/test_candidates.py tests/test_queries.py tests/test_country.py`

Expected: collection fails because the new modules and functions do not exist.

### Task 2: Implement pure candidate, name, country, and query behavior

**Files:**
- Create: `src/osm_polygon_web_search/candidates.py`
- Create: `src/osm_polygon_web_search/names.py`
- Create: `src/osm_polygon_web_search/country.py`
- Create: `src/osm_polygon_web_search/queries.py`

- [ ] **Step 1: Implement the smallest production code for the failing tests**

Implement frozen dataclasses for `PolygonCandidate`, Unicode NFKC/casefold/whitespace name keys, a basename-only country resolver, and deterministic quoted query construction. Count normalized names with `collections.Counter` and return only candidates whose count is exactly one.

- [ ] **Step 2: Run the focused tests and verify GREEN**

Run: `uv run pytest -q tests/test_candidates.py tests/test_queries.py tests/test_country.py`

Expected: all focused tests pass.

### Task 3: Add the PBF scanner and its pure geometry tests

**Files:**
- Modify: `pyproject.toml`
- Create: `src/osm_polygon_web_search/pbf.py`
- Create: `tests/test_pbf.py`

- [ ] **Step 1: Add runtime dependency and write RED geometry tests**

Add `osmium>=4.3.1` and `trafilatura>=2.0.0` to the project dependencies. Test that a closed ring becomes a GeoJSON Polygon, an open ring is rejected, and an `area=no` closed way is rejected.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest -q tests/test_pbf.py`

Expected: collection or assertion failure because the geometry conversion functions do not exist.

- [ ] **Step 3: Implement the PBF scanner**

Use `osmium.FileProcessor(pbf_path).with_areas()` and collect named closed ways from their original way objects plus named `type=multipolygon` or `type=boundary` relations from assembled area objects. Reject missing coordinates, non-closed rings, and `area=no`. Preserve all tags and emit GeoJSON geometry in each candidate.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `uv run pytest -q tests/test_pbf.py tests/test_candidates.py`

Expected: all candidate and geometry tests pass.

- [ ] **Step 5: Run the real Seagate PBF scan without network access**

Run: `uv run python -m osm_polygon_web_search --pbf '/Volumes/Seagate M3/projects/osm-polygon-web-search/liechtenstein-latest.osm.pbf' --plan-only`

Expected: the command reports candidate and unique-name counts, the filename-derived country `Liechtenstein`, and one deterministic selected candidate without making an HTTP request.

### Task 4: Add Trafilatura extraction and relevance evidence

**Files:**
- Create: `src/osm_polygon_web_search/text.py`
- Create: `src/osm_polygon_web_search/relevance.py`
- Create: `tests/test_text_and_relevance.py`

- [ ] **Step 1: Write RED tests**

Test that Trafilatura extracts article text from a small HTML string, empty extraction returns no evidence, and a sentence mentioning the place plus a physical-geography term receives the matching criterion.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest -q tests/test_text_and_relevance.py`

Expected: collection fails because the extraction and relevance modules do not exist.

- [ ] **Step 3: Implement the minimal extraction and evidence classifier**

Call `trafilatura.extract` with comments and tables disabled. Split extracted text into sentences and emit multi-label evidence for the configured land-cover, soil/surface, vegetation/ecosystem, terrain/geomorphology, infrastructure, and physical-setting vocabularies when the candidate name and criterion terms occur in the same sentence.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `uv run pytest -q tests/test_text_and_relevance.py`

Expected: all extraction and evidence tests pass.

### Task 5: Add Brave search, bounded fetching, and no raw-response cache

**Files:**
- Create: `src/osm_polygon_web_search/search.py`
- Create: `src/osm_polygon_web_search/fetch.py`
- Create: `tests/test_search_and_fetch.py`

- [ ] **Step 1: Write RED provider contract tests**

Test parsing of a Brave-shaped JSON response through an injected opener, missing API-key failure, and that a non-network fake provider can supply deterministic results. Test the page fetcher uses a timeout and passes HTML to the Trafilatura extractor.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest -q tests/test_search_and_fetch.py`

Expected: collection fails because the provider and fetcher modules do not exist.

- [ ] **Step 3: Implement the provider and fetcher**

Use `urllib.request` for the Brave `/res/v1/web/search` endpoint, read `BRAVE_SEARCH_API_KEY` only from the environment, map web results into a provider-neutral dataclass, and raise a clear error for missing credentials or non-success responses. Add bounded page fetching with a user agent, timeout, maximum response bytes, sequential delay, and retry handling for 429/503. Do not persist raw provider/page responses in the POC; a future cache requires an explicit provider-terms review because Brave’s current documentation distinguishes plans with storage rights.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `uv run pytest -q tests/test_search_and_fetch.py tests/test_text_and_relevance.py`

Expected: all provider, fetch, extraction, and evidence tests pass without network access.

### Task 6: Wire the one-candidate POC CLI and Seagate artifacts

**Files:**
- Modify: `src/osm_polygon_web_search/__main__.py`
- Create: `src/osm_polygon_web_search/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write RED pipeline and CLI contract tests**

Test that plan-only mode scans the requested PBF, derives `Liechtenstein`, emits a deterministic query, and does not call a provider; test that output paths outside `DATA_ROOT` are rejected.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest -q tests/test_pipeline.py`

Expected: collection fails because the pipeline and CLI contracts do not exist.

- [ ] **Step 3: Implement the pipeline and CLI**

Add `--pbf`, `--keyword`, `--plan-only`, `--search`, `--results`, and `--output-dir` arguments. Default the PBF to the Seagate Liechtenstein file, default the query keyword to `landuse description`, write JSON run artifacts only beneath `DATA_ROOT`, and keep the existing no-argument smoke command unchanged. Retrieve five result pages by default, with `--results` bounded to 1–20.

- [ ] **Step 4: Run the focused tests and the real plan-only POC**

Run: `uv run pytest -q tests/test_pipeline.py`

Expected: all pipeline tests pass.

Run: `uv run python -m osm_polygon_web_search --pbf '/Volumes/Seagate M3/projects/osm-polygon-web-search/liechtenstein-latest.osm.pbf' --plan-only --output-dir '/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc'

Expected: one JSON artifact is written under the Seagate path, with no GitHub, Hugging Face, or external-data writes.

### Task 7: Update documentation and repository contracts

**Files:**
- Modify: `README.md`
- Modify: `docs/index.md`
- Modify: `docs/getting-started.md`
- Modify: `docs/data-layout.md`
- Modify: `docs/development.md`
- Modify: `mkdocs.yml`
- Modify: `dataset/README.md`
- Modify: `tests/test_repository_contracts.py`

- [ ] **Step 1: Write a failing documentation contract test**

Require the docs to state the PBF-first flow, basename country resolution, Trafilatura extraction, Brave’s opt-in API key, and the fact that raw web content is not published to Hugging Face by default.

- [ ] **Step 2: Run the documentation contract test and verify RED**

Run: `uv run pytest -q tests/test_repository_contracts.py`

Expected: the new assertions fail against the metadata-only documentation.

- [ ] **Step 3: Update the documentation**

Document the exact plan-only and opt-in live commands, Seagate-only artifact layout, query/caching policy, and source-specific licensing caveat for OSM/web-derived data. Add an architecture page to the MkDocs navigation.

- [ ] **Step 4: Run the documentation tests and strict build**

Run: `uv run pytest -q tests/test_repository_contracts.py`

Expected: all repository contract tests pass.

Run: `uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site`

Expected: strict MkDocs build exits with status 0.

### Task 8: Run the complete quality gate

**Files:**
- Modify: `uv.lock`

- [ ] **Step 1: Refresh the locked environment**

Run: `uv lock`

Expected: `uv.lock` includes pyosmium and trafilatura without changing unrelated dependency declarations.

- [ ] **Step 2: Run the complete project gate**

Run: `just check`

Expected: formatting, Ruff, ty, tests with 100% coverage, and strict documentation build pass.

- [ ] **Step 3: Run mutation testing**

Run: `just mutation`

Expected: mutmut completes and reports no surviving or unresolved mutants.

- [ ] **Step 4: Run Docker and pre-commit checks**

Run: `just docker`

Expected: the image builds successfully without copying Seagate data into the image.

Run: `uv run pre-commit run --all-files`

Expected: all configured hooks pass.

- [ ] **Step 5: Review scope before handoff**

Run: `git diff --check && git status --short --branch`

Expected: no whitespace errors; only source, tests, docs, plan, and lockfile changes are present. Seagate PBFs and generated run artifacts remain outside Git.
