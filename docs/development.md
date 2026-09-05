# Development

## Test-first workflow

New behavior starts with a focused failing test. Run the test and confirm the
failure is caused by the missing behavior, add the smallest implementation,
run the test again, and refactor only while the suite remains green.

The PBF scanner uses pyosmium; page text extraction uses Trafilatura. Plan-only
tests never make network requests. Live search is exercised only with an
injected provider or an explicitly supplied `BRAVE_SEARCH_API_KEY`.

## Quality gate

Run the complete local gate from the repository root:

    uv run ruff format --check .
    uv run ruff check .
    uv run ty check --extra-search-path src
    uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing
    uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
    uv run mutmut run
    ! uv run mutmut results | rg -q .
    docker build -t osm-polygon-web-search:local .
    uv run pre-commit run --all-files

Mutation testing must complete with zero surviving or unresolved mutants in
every runtime module under `tool.mutmut.source_paths`. New modules are included
automatically. The `SearchProvider`
protocol signature is a non-executable typing boundary and is explicitly
excluded with a `# pragma: no mutate block`; all generated mutants are still
tested. A partial run is reported as incomplete, not as a passing quality gate.

Ruff's C90 gate caps cyclomatic complexity at 5. Together with the required
100% line and branch coverage, this keeps each covered function's CRAP score
below 6 (CRAP = complexity squared times uncovered-coverage cubed, plus
complexity).

The same commands are available through the justfile for local convenience.
