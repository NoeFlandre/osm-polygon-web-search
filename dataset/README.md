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
Hugging Face Dataset Viewer: the `polygon_image` column renders the selected
polygon, while the table exposes the polygon geometry, query, page URL, title,
HTTP status, full page text parsed by Trafilatura, and criterion-level evidence.

The table includes these main fields:

| Field | Purpose |
| --- | --- |
| `polygon_image` | Rendered polygon preview for the selected OSM object |
| `polygon_geojson`, centroid, and bounding-box fields | Polygon geometry and map context |
| `polygon_name`, `country`, `osm_type`, `osm_id`, `landuse` | OSM identity and tags |
| `query`, `executed_query`, `search_provider`, `fallback_reason` | Search provenance |
| `page_rank`, `title`, `page_url`, `http_status` | Retrieved-page metadata |
| `text`, `text_char_count` | Full page text extracted by Trafilatura and its length |
| `evidence`, `criteria` | Relevant sentences and matched physical-geography criteria |

The source PBF and local working artifacts stay under:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The uploaded table does not contain the local PBF, raw HTML, or provider
response. Full parsed page text is included explicitly for this POC so the
results can be inspected in the Viewer; raw HTML and provider responses are
not published to Hugging Face.
The Apache-2.0 license applies to the project’s original code and
documentation; OSM-derived fields and web-derived evidence retain their
source-specific terms and should not be treated as Apache-2.0 content.
