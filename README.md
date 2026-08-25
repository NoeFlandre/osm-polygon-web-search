# OSM Polygon Web Search

A small, Apache-2.0-licensed PBF-first proof of concept for OSM polygon web-search data work.

The proof of concept scans one local PBF, keeps named closed ways and area
relations whose normalized name is unique within that PBF, derives the country
from the PBF basename, builds a physical-geography query, and can optionally
search Brave and extract page text with Trafilatura.

## Data policy

All local and derived data stays under:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

No local PBF, raw HTML, search response, or raw web content is published to
GitHub or Hugging Face. The initial Hugging Face repository contains only its
dataset card and license.

## Development

    uv sync
    uv run python -m osm_polygon_web_search
    uv run python -m osm_polygon_web_search --plan-only
    BRAVE_SEARCH_API_KEY=... uv run python -m osm_polygon_web_search --search
    uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing
    uv run ruff format --check .
    uv run ruff check .
    uv run ty check
    uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
    uv run mutmut run
    ! uv run mutmut results | rg -q .
    docker build -t osm-polygon-web-search:local .

## Further reading

- [Documentation](https://noeflandre.github.io/osm-polygon-web-search/)
- [Dataset card](dataset/README.md)
- [Citation](CITATION.cff)
- [License](LICENSE)
