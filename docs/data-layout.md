# Data layout

All local and derived data stays under this exact Seagate path:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The PBF-first proof of concept reads the selected PBF from this path and writes
only run manifests below this path. The path remains the single explicit local
data boundary.

The initial layout is:

    liechtenstein-latest.osm.pbf       immutable source snapshot
    runs/poc/run.json                   candidate, query, and review manifest

The PBF, raw HTML, provider response, and full parsed page text remain on the
Seagate. The explicitly approved `runs/poc/run.json` review artifact is copied
to Hugging Face as `poc/run.json`; it contains selected metadata, result
metadata, statuses, extracted-text lengths, and criterion-level evidence.
Raw web content is not published to GitHub or Hugging Face.
The live search adapter is opt-in, and its credentials are read only from the
`BRAVE_SEARCH_API_KEY` environment variable.

Future processing work must preserve this boundary and receive a separate
approved design, tests, documentation, and mutation-testing review.
