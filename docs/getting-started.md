# Getting started

## Install

The project uses uv. From the repository root, run:

    uv sync

## Smoke command

The package reports the only permitted local data root:

    uv run python -m osm_polygon_web_search

Expected output:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The command only returns a path value. It does not create the directory,
inspect its contents, or copy any data.

## PBF-first proof of concept

The default input is:

    /Volumes/Seagate M3/projects/osm-polygon-web-search/liechtenstein-latest.osm.pbf

Run the offline plan first:

    uv run python -m osm_polygon_web_search --plan-only

This scans the PBF, counts normalized names across named polygon candidates,
selects one unique physical-place candidate, derives `Liechtenstein` from the
filename, builds the V1 query, and writes `runs/poc/run.json` on the Seagate.
The default query is exactly:

    "<polygon name>" "Liechtenstein" "land cover"

To include every approved query variant in the plan, use:

    uv run python -m osm_polygon_web_search --all-variants --plan-only

The nine variants are V1 `land cover`, V2 `land use`, V3 `vegetation`, V4
`terrain`, V5 `soil surface`, V6 `ecosystem`, V7 `physical geography`, V8
`buildings infrastructure`, and V9 `landscape environment`.

To create a sentence-level Viewer table from the approved POC parquet, run:

    HF_HOME="/Volumes/Seagate M3/projects/osm-polygon-web-search/.hf-home" \
    uv run python scripts/segment_dataset.py \
      --input "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc-20260827-stausee-steg-no-landuse/hf-viewer/train.parquet" \
      --output "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc-20260828-sat-3l-sm/hf-viewer/train.parquet"

The command loads `segment-any-text/sat-3l-sm` once, keeps the original page
text in `text`, and emits one row per non-empty sentence with
`sentence_index`, `sentence_count`, and `sentence_model`.

With live search enabled, the POC retrieves up to five result pages for the
selected polygon in V1 mode. Add `--all-variants` to search all nine variants;
use `--results N` to request between 1 and 20 pages per variant.

Live search is opt-in and requires a Brave API key:

    BRAVE_SEARCH_API_KEY=... uv run python -m osm_polygon_web_search --search --all-variants

The standard Brave Search API currently charges per search request after its
included monthly credits. The program does not make a live request unless
`--search` is supplied and the key is present. See the [architecture
page](architecture.md) for query, rate-limit, and storage policy.

## Current remote scope

The GitHub repository contains source and documentation. The Hugging Face
dataset repository contains the explicitly approved Viewer-ready
`train.parquet` table: one row per segmented sentence with polygon geometry, the
exact Brave query, URL, full parsed page text, and sentence metadata. It never
contains the local PBF, raw HTML, or provider response.
