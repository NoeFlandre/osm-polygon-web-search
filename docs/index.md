# OSM Polygon Web Search

OSM Polygon Web Search is an Apache-2.0-licensed PBF-first proof of concept
for OpenStreetMap polygon web-search data work.

The approved first pipeline is deliberately small:

- scans the Liechtenstein PBF already stored on the Seagate;
- keeps named closed ways and valid area relations;
- excludes every polygon whose normalized name is duplicated in the PBF;
- derives `Liechtenstein` from the PBF filename;
- builds nine exact-place query variants: land cover, land use, vegetation,
  terrain, soil surface, ecosystem, physical geography, buildings
  infrastructure, and landscape environment;
- uses a Brave Search API adapter for opt-in live queries;
- retrieves up to ten result pages per variant by default (`--results` accepts
  1–20; `--all-variants` runs V1–V9);
- removes exact duplicate URLs per polygon, keeping the first ordered
  occurrence while keeping URL scopes independent between polygons;
- extracts page text with Trafilatura, removes obvious extraction scaffolding,
  and expands it into sentence-level rows with `segment-any-text/sat-3l-sm`;
- classifies every sentence locally with `LiquidAI/LFM2.5-2.6B` using the
  approved strict yes/no prompt;
- all local and derived data stays on the Seagate volume;
- the approved Hugging Face table contains only `yes` sentences and includes
  polygon geometry, the exact Brave query, URL, full parsed page text,
  sentence-level fields, and model provenance; extracted evidence and criteria,
  raw HTML, and provider responses are not published.

Start with the [getting-started guide](getting-started.md), then read the
[architecture](architecture.md) and [data policy](data-layout.md).
