# Development

## Test-first workflow

New behavior starts with a focused failing test. Run the test and confirm the
failure is caused by the missing behavior, add the smallest implementation,
run the test again, and refactor only while the suite remains green.

## Quality gate

Run the complete local gate from the repository root:

    uv run ruff format --check .
    uv run ruff check .
    uv run ty check
    uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing
    uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
    uv run mutmut run
    test -z "$$(uv run mutmut results)"
    docker build -t osm-polygon-web-search:local .
    uv run pre-commit run --all-files

Mutation testing must complete with zero surviving or unresolved mutants. A
partial run is reported as incomplete, not as a passing quality gate.

The same commands are available through the justfile for local convenience.
