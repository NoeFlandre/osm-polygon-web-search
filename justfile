set shell := ["zsh", "-cu"]

format:
    uv run ruff format --check .

lint:
    uv run ruff check .

type:
    uv run ty check

test:
    uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing

docs:
    uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site

mutation:
    uv run mutmut run
    ! uv run mutmut results | rg -q .

docker:
    docker build -t osm-polygon-web-search:local .

check: format lint type test docs
