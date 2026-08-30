# Typed Dataset Schema Boundary Design

## Problem

The sentence and relevance transformations preserve arbitrary context columns,
but their row interfaces are currently `Mapping[str, Any]` and
`dict[str, Any]`. Their Parquet adapters also use `Any` for Arrow tables. This
lets the persisted dataset contract drift without a precise type boundary, and
it makes the two transformation stages harder to read and review.

## Decision

Add one small `dataset_schema.py` module with:

- `DatasetRow`, an open-world `Mapping[str, object]` for preserving arbitrary
  source context columns;
- `DatasetRecord`, the corresponding `dict[str, object]` output shape;
- required `TypedDict` contracts for the generated sentence and relevance
  metadata fields.

Use these aliases in both row-level transformations and keep the generated
metadata construction in small typed helpers. Annotate the private Arrow
boundaries as `pyarrow.Table` using postponed annotations and a
`TYPE_CHECKING` import, while retaining the existing lazy runtime imports.

The input remains intentionally open-world: rows may contain any existing
polygon, page, or provenance fields and rows without valid `text` or
`sentence` values continue to be skipped. No runtime validation, column
renaming, row reordering, model change, or public API change is introduced.
Only the internal data contracts become explicit; third-party model objects
remain behind their existing protocols and narrow dynamic adapters.

## Compatibility

The exact sentence and relevance output dictionaries, Parquet schemas, empty
selection behavior, batching, ordering, and filesystem boundaries remain
unchanged. The Arrow helpers still preserve source columns and use Arrow row
selection rather than materializing the source table as Python mappings.

## Verification

Tests first lock the schema aliases and generated metadata contracts. Existing
sentence and relevance tests continue to assert exact row dictionaries and
Parquet schemas. The final gate requires 100% line and branch coverage, zero
surviving mutants, Ruff including complexity checks, `ty`, strict MkDocs,
pre-commit, a successful wheel build, and a clean pushed branch. Docker is
reported separately if the local daemon is unavailable.
