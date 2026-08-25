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

## Current remote scope

The GitHub repository contains source and documentation. The Hugging Face
dataset repository is metadata-only: its initial publication contains the
dataset card and Apache-2.0 license, never local or derived data.
