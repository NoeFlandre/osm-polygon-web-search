# Architecture

## PBF-first flow

The proof of concept uses one complete local PBF rather than an online OSM
query:

    PBF → polygon candidates → name counts → unique candidate → query variants → pages → Trafilatura text → SAT sentence rows

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

Each query is the polygon name, the country derived from the PBF basename, and
one approved keyword phrase. The variants are:

    V1  "Alpe Vermales" "Liechtenstein" "land cover"
    V2  "Alpe Vermales" "Liechtenstein" "land use"
    V3  "Alpe Vermales" "Liechtenstein" vegetation
    V4  "Alpe Vermales" "Liechtenstein" terrain
    V5  "Alpe Vermales" "Liechtenstein" "soil surface"
    V6  "Alpe Vermales" "Liechtenstein" ecosystem
    V7  "Alpe Vermales" "Liechtenstein" "physical geography"
    V8  "Alpe Vermales" "Liechtenstein" "buildings infrastructure"
    V9  "Alpe Vermales" "Liechtenstein" "landscape environment"

Live search retrieves up to five result pages per variant by default when
`--all-variants` is supplied. The `--results` option allows 1–20 pages per
variant; fewer may be returned when the provider has fewer results or a page
fetch fails.

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

The original retrieval analysis also includes a transparent lexical baseline
that produces evidence sentences and criterion labels. The current published
table uses the local LFM yes/no classifier described below instead of exposing
those baseline evidence fields.

### Sentence-level output

The approved Viewer transformation loads `segment-any-text/sat-3l-sm` through
`wtpsplit` once and segments each distinct non-empty Trafilatura page text
through its bounded batch interface. The first-seen results are restored to
every original page/query row, so duplicate contexts remain visible without
repeating deterministic model work. A scalar compatibility interface remains
available for injected models. Each sentence becomes one output row. The
original full page text remains in `text` for provenance; `sentence`,
`sentence_index`, `sentence_count`, and `sentence_model` expose the model output
and its position. Empty extracted text produces no sentence row. Parquet
expansion uses Arrow row selection and typed appended columns rather than
materializing the complete source table as Python dictionaries.

### Local relevance classification

The current downstream step sends each non-empty `sentence` to one local
`LiquidAI/LFM2.5-2.6B` instance with the approved land-use/land-cover prompt.
Generation is deterministic and the parser accepts only `yes` or `no` as the
final answer, allowing the model's closing `</think>` wrapper. Any other
output fails hard. The complete table adds `relevance_label` and
`relevance_model` and remains on the Seagate; the Hugging Face `train.parquet`
is the filtered `relevance_label == "yes"` subset. The Parquet path sends each
distinct sentence string through the bounded local classifier once and fans
labels back to all original rows. The public mapping API remains scalar-input
compatible.

## Network and scale controls

The first run is plan-only by default. Live search requires `--search` and
`BRAVE_SEARCH_API_KEY`; a missing key is a hard configuration error. Brave
search requests remain sequential. After each search response, page downloads
are deduplicated by exact URL and use at most four in-memory workers; the
results are serialized back in provider rank order. A configured positive
page-fetch delay switches that stage to serial execution so rate limits remain
meaningful. Only successful pages are reused within one all-variants run;
failed URLs are retried by the existing fetch policy and are not persisted in
the cache. At scale, provider budgets, per-host concurrency, checkpointed jobs, and
a content-addressed cache should be added only when provider terms permit
storing responses. The approved Hugging Face table contains relevant-only
sentence rows with polygon geometry, the exact Brave query, URL, full
Trafilatura-parsed text, sentence metadata, and model provenance for
inspection. The published table omits extracted evidence and criteria. Raw
HTML and provider responses are not published to Hugging Face.

The POC intentionally does not introduce a queue, database server, browser
automation, or embeddings. The pure candidate, query, provider, fetch, SAT,
and relevance boundaries are the scale seam.
