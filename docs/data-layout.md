# Data layout

All local and derived data stays under this exact Seagate path:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The PBF-first proof of concept reads the selected PBF from this path and writes
only run manifests below this path. The path remains the single explicit local
data boundary.

The initial layout is:

    liechtenstein-latest.osm.pbf       immutable source snapshot
    runs/poc/run.json                   candidate, query, and review manifest
    runs/poc/hf-viewer/train.parquet   Viewer-ready one-row-per-page table
    runs/poc/hf-viewer/*.png           polygon preview used by the table

The PBF, raw HTML, and provider response remain on the Seagate. The explicitly
approved `runs/poc/hf-viewer/train.parquet` table is copied to Hugging Face as
`train.parquet`; it contains one row per fetched page, a rendered polygon
image, geometry, query and URL fields, and full page text parsed by Trafilatura.
The published table omits extracted evidence and criteria. Raw HTML and
provider responses are not published to GitHub or Hugging Face.
The live search adapter is opt-in, and its credentials are read only from the
`BRAVE_SEARCH_API_KEY` environment variable.

Future processing work must preserve this boundary and receive a separate
approved design, tests, documentation, and mutation-testing review.
