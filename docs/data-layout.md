# Data layout

All local and derived data stays under this exact Seagate path:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The PBF-first proof of concept reads the selected PBF from this path and writes
only run manifests below this path. The path remains the single explicit local
data boundary.

The initial layout is:

    liechtenstein-latest.osm.pbf       immutable source snapshot
    runs/poc/run.json                   candidate and query manifest

No local PBF, raw HTML, search response, or raw web content is published to
GitHub or Hugging Face; these files are never uploaded. The initial Hugging
Face dataset card is metadata-only.
The live search adapter is opt-in, and its credentials are read only from the
`BRAVE_SEARCH_API_KEY` environment variable.

Future processing work must preserve this boundary and receive a separate
approved design, tests, documentation, and mutation-testing review.
