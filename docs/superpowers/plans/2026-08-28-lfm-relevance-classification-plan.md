# LFM2.5 Sentence Relevance Classification Plan

> **Execution note:** This plan is being executed in the existing clean
> checkout because the user approved the design and requested uninterrupted
> completion through HF publication.

## Task 1: Record the contract and add RED tests

Files:

- `src/osm_polygon_web_search/relevance.py`
- `src/osm_polygon_web_search/relevance_model.py`
- `src/osm_polygon_web_search/relevance_dataset.py`
- `tests/test_relevance.py`
- `tests/test_relevance_model.py`
- `tests/test_relevance_dataset.py`
- `tests/test_repository_contracts.py`

Write tests for the exact prompt substitution, strict `yes`/`no` parsing,
reasoning-wrapper handling, model adapter calls, row preservation, yes-only
filtering, parquet output, and documentation schema. Run the focused tests and
capture the expected RED collection failure before adding implementation.

```bash
uv run pytest tests/test_relevance.py tests/test_relevance_model.py tests/test_relevance_dataset.py -q
```

## Task 2: Implement the smallest GREEN path

Add the pure prompt/parser functions, the local Transformers adapter, and the
row/parquet transformation. Add direct runtime dependencies for the local
model and update the lockfile. Keep the CLI thin and fail hard on invalid
model output.

```bash
uv lock
uv run pytest tests/test_relevance.py tests/test_relevance_model.py tests/test_relevance_dataset.py -q
```

## Task 3: Update documentation and refactor

Document the new local classification fields and relevant-only HF contract in
the repository and dataset cards. Run formatting and static checks, then
refactor only where the checks or review identify duplication or unnecessary
complexity.

```bash
uv run ruff format .
uv run ruff check .
uv run ty check
uv run mkdocs build --strict
```

## Task 4: Verify quality gates

Run the full tests, coverage, mutation, CRAP, and pre-commit surfaces. Do not
publish until all applicable checks pass and no mutation survives.

```bash
just check
just mutation
just crap
pre-commit run --all-files
```

## Task 5: Run local inference and build publication artifacts

Use Seagate-only model/cache paths. Classify the current SAT table sequentially
with one loaded `LiquidAI/LFM2.5-2.6B` instance, write the full yes/no table,
write the filtered yes-only Viewer parquet, and validate the schema and counts.

```bash
uv run python -m osm_polygon_web_search.relevance_dataset \
  --input /Volumes/Seagate\ M3/projects/osm-polygon-web-search/runs/poc-20260828-sat-3l-sm/hf-viewer/train.parquet \
  --classified-output /Volumes/Seagate\ M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/classified/train.parquet \
  --relevant-output /Volumes/Seagate\ M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/hf-viewer/train.parquet
```

## Task 6: Overwrite and verify HF

Stage only the generated `train.parquet` and updated dataset card in a
Seagate-hosted HF staging clone, push the replacement commit, download the
public parquet again, and compare bytes, schema, row count, and metadata with
the local publication artifact.

```bash
git -C /Volumes/Seagate\ M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/hf-repo push origin main
curl -fsSL 'https://huggingface.co/NoeFlandre/osm-polygon-web-search/resolve/main/train.parquet?download=true' \
  -o /Volumes/Seagate\ M3/projects/osm-polygon-web-search/runs/poc-20260828-lfm2.5-2.6b-relevance/remote-verify/train.parquet
```
