# OSM Polygon Web Search

A small, Apache-2.0-licensed PBF-first proof of concept for OSM polygon web-search data work.

The proof of concept scans one local PBF, keeps named closed ways and area
relations whose normalized name is unique within that PBF, derives the country
from the PBF basename, builds nine place-scoped query variants for land cover,
land use, vegetation, terrain, soil/surface, ecosystems, physical geography,
buildings/infrastructure, and landscape/environment, and can optionally search
Brave, extract page text with Trafilatura, split it into sentence-level rows
with `segment-any-text/sat-3l-sm`, and classify each sentence locally with
`LiquidAI/LFM2.5-2.6B`.

## Data policy

All local and derived data stays under:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The local PBF, raw HTML, provider response, model cache, and complete yes/no
classification table remain on the Seagate. The explicitly approved Hugging
Face Viewer table contains only sentences classified `yes`, together with
polygon geometry, the exact Brave query, URL, title, full Trafilatura-parsed
page text, sentence position, SAT model, relevance label, and relevance model.
The published table omits extracted evidence and criteria. Raw HTML and
provider responses are not published.

## Development

    uv sync
    uv run python -m osm_polygon_web_search
    uv run python -m osm_polygon_web_search --plan-only
    uv run python -m osm_polygon_web_search --all-variants --plan-only
    BRAVE_SEARCH_API_KEY=... uv run python -m osm_polygon_web_search --search
    uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing
    uv run ruff format --check .
    uv run ruff check .
    uv run ty check
    uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
    uv run mutmut run
    ! uv run mutmut results | rg -q .
    docker build -t osm-polygon-web-search:local .

For the bounded remote GPU pass, use the Grid'5000 runner after the repository
commit is pushed and the Seagate sentence table is ready:

    uv run python scripts/run_grid5000_relevance.py \
      --input "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/<run>/segmented/train.parquet" \
      --classified-output "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/<run>/grid5000/classified.parquet" \
      --relevant-output "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/<run>/grid5000/relevant.parquet" \
      --run-dir "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/<run>/grid5000"

The runner performs policy checks, uses one Nantes `host=1/gpu=1` reservation
with a 30-minute walltime, and sends only compressed sentence text plus row
indices. The model and all remote caches stay in node-local `/tmp`; labels and
logs are copied back to the Seagate before the exact remote temporary directory
is removed.

## Further reading

- [Documentation](https://noeflandre.github.io/osm-polygon-web-search/)
- [Dataset card](dataset/README.md)
- [Citation](CITATION.cff)
- [License](LICENSE)
