---
license: apache-2.0
pretty_name: OSM Polygon Web Search
tags:
  - openstreetmap
  - geospatial
---

# OSM Polygon Web Search

This public Hugging Face dataset contains one explicitly approved POC table at
`train.parquet`, with one row per fetched web page. It is designed for the
Hugging Face Dataset Viewer: the table exposes the polygon geometry, exact Brave
query, page URL, title, HTTP status, and full page text parsed by Trafilatura.

The rows cover nine query variants: V1 `land cover`, V2 `land use`, V3
`vegetation`, V4 `terrain`, V5 `soil surface`, V6 `ecosystem`, V7 `physical
geography`, V8 `buildings infrastructure`, and V9 `landscape environment`.

The table includes these main fields:

| Field | Purpose |
| --- | --- |
| `polygon_geojson`, centroid, and bounding-box fields | Polygon geometry and map context |
| `polygon_name`, `country`, `osm_type`, `osm_id`, `landuse` | OSM identity and tags |
| `query_keyword`, `query` | Approved keyword phrase and exact Brave query used for the search |
| `page_rank`, `title`, `page_url`, `http_status` | Retrieved-page metadata |
| `text`, `text_char_count` | Full page text extracted by Trafilatura and its length |

The extracted evidence and criteria fields are intentionally omitted from this
revision. The full parsed `text` remains available for inspection.

The source PBF and local working artifacts remain local. The uploaded table
contains only the PBF basename in `source_pbf`, not a local filesystem path, and
does not contain raw HTML or the provider response. Full parsed page text is
included explicitly for this POC so the results can be inspected in the Viewer.
The Apache-2.0 license applies to the project’s original code and
documentation; OSM-derived fields and web-derived text retain their
source-specific terms and should not be treated as Apache-2.0 content.
