import argparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .llm_relevance import RELEVANCE_MODEL_ID, RelevanceClassifier
from .pipeline import ensure_data_path
from .relevance_model import load_lfm_classifier

CLASSIFICATION_BATCH_SIZE = 8


def classify_rows(
    rows: Iterable[Mapping[str, Any]],
    classifier: RelevanceClassifier,
) -> list[dict[str, Any]]:
    """Add one strict local relevance label to every non-empty sentence row."""
    sentence_rows = []
    for row in rows:
        sentence = row.get("sentence")
        if not isinstance(sentence, str) or not sentence.strip():
            continue
        sentence_rows.append(dict(row))

    classified: list[dict[str, Any]] = []
    for start in range(0, len(sentence_rows), CLASSIFICATION_BATCH_SIZE):
        batch = sentence_rows[start : start + CLASSIFICATION_BATCH_SIZE]
        labels = classifier.classify_many([row["sentence"] for row in batch])
        classified.extend(
            {
                **row,
                "relevance_label": label,
                "relevance_model": RELEVANCE_MODEL_ID,
            }
            for row, label in zip(batch, labels, strict=True)
        )
    return classified


def relevant_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep only rows whose validated model label is yes."""
    return [dict(row) for row in rows if row.get("relevance_label") == "yes"]


def transform_parquet(
    input_path: Path,
    classified_output_path: Path,
    relevant_output_path: Path,
    classifier: RelevanceClassifier,
) -> tuple[int, int]:
    """Write full local labels and the yes-only Viewer table."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    source = pq.read_table(input_path)
    classified = classify_rows(source.to_pylist(), classifier)
    relevant = relevant_rows(classified)
    for output_path, rows in (
        (classified_output_path, classified),
        (relevant_output_path, relevant),
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), output_path)
    return len(classified), len(relevant)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Classify SAT sentence rows with the local LFM relevance model"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--classified-output", type=Path, required=True)
    parser.add_argument("--relevant-output", type=Path, required=True)
    args = parser.parse_args(argv)
    input_path = ensure_data_path(args.input)
    classified_output_path = ensure_data_path(args.classified_output)
    relevant_output_path = ensure_data_path(args.relevant_output)
    classified_count, relevant_count = transform_parquet(
        input_path,
        classified_output_path,
        relevant_output_path,
        load_lfm_classifier(),
    )
    print(f"classified={classified_count} relevant={relevant_count}")


if __name__ == "__main__":  # pragma: no cover
    main()
