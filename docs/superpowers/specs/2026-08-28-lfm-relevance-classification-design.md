# LFM2.5 Sentence Relevance Classification Design

## Goal

Classify every non-empty `sentence` in the current SAT sentence-level POC
table with `LiquidAI/LFM2.5-2.6B` running locally. The classifier uses the
approved yes/no land-use and land-cover prompt and does not call a hosted LLM
or a web-search fallback.

## Scope and output

The input is the existing sentence-level table under the Seagate project
root. Each classified local row preserves the existing polygon, search, page,
text, and SAT fields and adds:

- `relevance_label`: the strict model result, `yes` or `no`;
- `relevance_model`: `LiquidAI/LFM2.5-2.6B`.

The complete yes/no table is retained locally on the Seagate drive for
reproducibility. The Hugging Face `train.parquet` is replaced with only rows
whose `relevance_label` is `yes`, so the public table contains the requested
relevant sentences and remains easy to inspect in the Dataset Viewer.

## Architecture

The implementation has three small boundaries:

1. A pure relevance module owns the exact prompt template, the model ID, and
   strict output parsing. It accepts an optional reasoning wrapper ending in
   `</think>` but rejects missing, extra, or non-`yes`/`no` final output.
2. A local model adapter loads the tokenizer and causal language model once,
   applies the tokenizer chat template for each sentence, runs deterministic
   generation, and delegates label validation to the pure parser.
3. A table transformation classifies rows, writes the complete local table,
   filters `yes` rows, and writes the HF Viewer table. It writes outputs only
   after classification succeeds for all input sentences.

Inference is sequential and bounded to one loaded model. This is appropriate
for the small POC and gives a simple scale-up seam: a future worker or batch
runner can replace the model adapter without changing the table contract.

## Failure behavior

The run fails hard when the model cannot be loaded, generation fails, or the
model does not produce exactly one valid final label. No guessed label,
fallback provider, or partial published table is allowed. The HF upload is
performed only after the local full and filtered artifacts pass schema checks.

## Data, storage, and licensing

All input data, model caches, intermediate files, logs, and generated outputs
remain under `/Volumes/Seagate M3/projects/osm-polygon-web-search`. Temporary
software environments and diagnostics are removed after the run. The project
code and documentation remain Apache-2.0; the model, OSM-derived fields, and
web-derived text retain their own terms.

## Verification

The change follows RED→GREEN→REFACTOR. Pure transformation logic is tested at
100% line and branch coverage, mutation-tested with no surviving mutants, and
kept below the repository CRAP complexity threshold of 6. Ruff, ty, MkDocs,
pre-commit, and the repository contract tests are run before publication. The
published parquet bytes are downloaded again from HF and compared with the
local Seagate artifact.
