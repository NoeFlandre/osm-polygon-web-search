# OSM Polygon Web Search

OSM Polygon Web Search is an Apache-2.0-licensed foundation for future
OpenStreetMap polygon web-search data work.

The initial release is deliberately small:

- the package exposes the canonical local data root;
- the Hugging Face dataset repository contains metadata only;
- all local and derived data stays on the Seagate volume;
- no scraper, parser, transformation, or upload pipeline is included yet.

Start with the [getting-started guide](getting-started.md), then read the
[data policy](data-layout.md) before working with local inputs.
