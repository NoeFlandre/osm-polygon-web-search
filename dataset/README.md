---
license: apache-2.0
pretty_name: OSM Polygon Web Search
tags:
  - openstreetmap
  - geospatial
---

# OSM Polygon Web Search

This public Hugging Face dataset contains one explicitly approved POC table at
`train.parquet`, with one row per non-empty SAT sentence classified as
relevant-only by the local `LiquidAI/LFM2.5-2.6B` model. It is designed for the
Hugging Face Dataset Viewer: the table exposes polygon geometry, the exact
Brave query, page URL, title, HTTP status, full page text parsed by Trafilatura,
the SAT sentence, and the strict relevance result. The complete yes/no
classification table remains on the Seagate project volume.

The rows cover nine query variants: V1 `land cover`, V2 `land use`, V3
`vegetation`, V4 `terrain`, V5 `soil surface`, V6 `ecosystem`, V7 `physical
geography`, V8 `buildings infrastructure`, and V9 `landscape environment`.

The table includes these main fields:

| Field | Purpose |
| --- | --- |
| `polygon_geojson`, centroid, and bounding-box fields | Polygon geometry and map context |
| `polygon_name`, `country`, `osm_type`, `osm_id` | OSM identity |
| `query_keyword`, `query` | Approved keyword phrase and exact Brave query used for the search |
| `page_rank`, `title`, `page_url`, `http_status` | Retrieved-page metadata |
| `text`, `text_char_count` | Full page text extracted by Trafilatura and its length |
| `sentence`, `sentence_index`, `sentence_count` | SAT sentence and its position within the page |
| `sentence_model` | `segment-any-text/sat-3l-sm` model identifier |
| `relevance_label` | Local LFM classification; every published row is `yes` |
| `relevance_model` | `LiquidAI/LFM2.5-2.6B` model identifier |

The extracted evidence and criteria fields are intentionally omitted. The full
parsed `text` remains available for inspection, while `sentence` is the
primary downstream text unit. Before SAT segmentation, obvious Trafilatura
scaffolding is removed from the segmentation input: headings, menu and call-to-
action fragments, metadata, identifiers, symbols, and very short fragments.
The raw parsed `text` column is retained unchanged for provenance and review.

The source PBF and local working artifacts remain local. The uploaded table
contains only the PBF basename in `source_pbf`, not a local filesystem path, and
does not contain raw HTML or the provider response. Full parsed page text is
included explicitly for this POC so the results can be inspected in the Viewer;
the sentence-level `sentence` field is the primary downstream text unit.
The Apache-2.0 license applies to the project’s original code and
documentation; OSM-derived fields and web-derived text retain their
source-specific terms and should not be treated as Apache-2.0 content.
