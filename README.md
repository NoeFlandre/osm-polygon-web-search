# OSM Polygon Web Search

A small, Apache-2.0-licensed foundation for future OSM polygon web-search data work.

The current release is intentionally metadata-only. The package exposes the
canonical local data root and does not read, create, transform, or upload
data.

## Data policy

All local and derived data stays under:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

No data files are published to GitHub or Hugging Face. The initial Hugging
Face repository contains only its dataset card and license.

## Development

    uv sync
    uv run python -m osm_polygon_web_search
    uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing
    uv run ruff format --check .
    uv run ruff check .
    uv run ty check
    uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
    uv run mutmut run
    test -z "$$(uv run mutmut results)"
    docker build -t osm-polygon-web-search:local .

## Further reading

- [Documentation](https://noeflandre.github.io/osm-polygon-web-search/)
- [Dataset card](dataset/README.md)
- [Citation](CITATION.cff)
- [License](LICENSE)
