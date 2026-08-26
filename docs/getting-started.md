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
filename, builds the query, and writes `runs/poc/run.json` on the Seagate.
The default query is exactly:

    "<polygon name>" "Liechtenstein" "landuse description"

With live search enabled, the POC retrieves up to five result pages for the
selected polygon. Use `--results N` to request between 1 and 20 pages.

Live search is opt-in and requires a Brave API key:

    BRAVE_SEARCH_API_KEY=... uv run python -m osm_polygon_web_search --search

The standard Brave Search API currently charges per search request after its
included monthly credits. The program does not make a live request unless
`--search` is supplied and the key is present. See the [architecture
page](architecture.md) for query, rate-limit, and storage policy.

## Current remote scope

The GitHub repository contains source and documentation. The Hugging Face
dataset repository contains the explicitly approved Viewer-ready
`train.parquet` table: one row per fetched page with the polygon image,
geometry, query, URL, and full parsed text. It never contains the local PBF,
raw HTML, or provider response.
