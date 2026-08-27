# Architecture

## PBF-first flow

The proof of concept uses one complete local PBF rather than an online OSM
query:

    PBF → polygon candidates → name counts → unique candidate → query → pages → evidence

Closed ways are accepted when they form a finite closed ring and are not tagged
`area=no`. Relations are accepted only when pyosmium can assemble them as
`type=multipolygon` or `type=boundary` areas. Every candidate keeps its OSM
type, ID, original tags, normalized name, and GeoJSON geometry.

Name uniqueness is exact after conservative Unicode NFKC normalization,
case-folding, trimming, and whitespace collapsing. All duplicates are removed;
the POC scope is the pinned PBF snapshot. At scale, this becomes a materialized
name index with an explicit country or multi-PBF scope.

The country label is deliberately derived from the PBF basename. For example,
`liechtenstein-latest.osm.pbf` produces `Liechtenstein`; no reverse-geocoder is
called.

## Query and page processing

The default query is the polygon name, the country derived from the PBF
basename, and the exact phrase `landuse description`:

    "Alpe Vermales" "Liechtenstein" "landuse description"

Live search retrieves up to five result pages per polygon by default. The
`--results` option allows 1–20 pages; fewer may be returned when the provider
has fewer results or a page fetch fails.

The search engine is accessed through a provider adapter. The first adapter is
the [Brave Search API](https://brave.com/search/api/), using its JSON web-search
endpoint. The key is never stored in the repository. The standard Search plan
is currently priced at $5 per 1,000 requests and includes $5 in monthly
credits; exact account terms and storage rights are controlled by Brave.

Search results are only discovery metadata. Selected pages are fetched with a
bounded timeout and response size, then readable text is extracted with
[Trafilatura](https://trafilatura.readthedocs.io/). Evidence is retained only
when the same sentence mentions the target place and one of these criteria:

- land use or land cover;
- soil or surface;
- vegetation or ecosystems;
- terrain or geomorphology;
- visible buildings or infrastructure;
- physical geographic setting, shape, position, or extent.

The first classifier is a transparent lexical baseline. It produces evidence
sentences and criterion labels rather than an unexplained binary score. A
stronger classifier can later be added behind the same evidence contract.

## Network and scale controls

The first run is sequential and plan-only by default. Live search requires
`--search`. The adapters already bound timeouts and response sizes, retry
selected 429/503 responses with `Retry-After` or exponential backoff, and
apply sequential delays. Future batch execution should add provider budgets,
per-host concurrency, URL deduplication, checkpointed jobs, and a
content-addressed cache only when the provider terms permit storing responses.
The approved Hugging Face table contains the polygon image, geometry, query,
URL, and full Trafilatura-parsed text for inspection. The published table omits
extracted evidence and criteria. Raw HTML and provider responses are not
published to Hugging Face.

The POC intentionally does not introduce a queue, database server, browser
automation, embeddings, or an LLM. The pure candidate, query, provider, fetch,
and evidence boundaries are the scale seam.
