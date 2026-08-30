import argparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .data_root import ensure_data_path
from .llm_relevance import (
    RELEVANCE_MODEL_ID,
    RelevanceClassifier,
    RelevanceLabel,
)
from .relevance_model import load_lfm_classifier

CLASSIFICATION_BATCH_SIZE = 16


def _non_empty_sentence(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _classify_sentences(
    sentences: Sequence[str],
    classifier: RelevanceClassifier,
) -> list[RelevanceLabel]:
    labels: list[RelevanceLabel] = []
    for start in range(0, len(sentences), CLASSIFICATION_BATCH_SIZE):
        batch = sentences[start : start + CLASSIFICATION_BATCH_SIZE]
        batch_labels = classifier.classify_many(batch)
        if len(batch_labels) != len(batch):
            raise ValueError("classifier must return one label per sentence")
        labels.extend(batch_labels)
    return labels


def classify_rows(
    rows: Iterable[Mapping[str, Any]],
    classifier: RelevanceClassifier,
) -> list[dict[str, Any]]:
    """Add one strict local relevance label to every non-empty sentence row."""
    sentence_rows: list[dict[str, Any]] = []
    sentences: list[str] = []
    for row in rows:
        sentence = _non_empty_sentence(row.get("sentence"))
        if sentence is None:
            continue
        sentence_rows.append(dict(row))
        sentences.append(sentence)

    labels = _classify_sentences(sentences, classifier)
    return [
        {
            **sentence_rows[index],
            "relevance_label": labels[index],
            "relevance_model": RELEVANCE_MODEL_ID,
        }
        for index in range(len(sentence_rows))
    ]


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
    sentence_values = (
        source["sentence"].to_pylist() if "sentence" in source.column_names else []
    )
    valid_indices: list[int] = []
    sentences: list[str] = []
    for index, value in enumerate(sentence_values):
        sentence = _non_empty_sentence(value)
        if sentence is not None:
            valid_indices.append(index)
            sentences.append(sentence)

    selected = source.take(pa.array(valid_indices, type=pa.int64()))
    labels = _classify_sentences(sentences, classifier)
    classified = selected.append_column(
        "relevance_label",
        pa.array(labels, type=pa.string()),
    ).append_column(
        "relevance_model",
        pa.array([RELEVANCE_MODEL_ID] * len(labels), type=pa.string()),
    )
    relevant = classified.filter(
        pa.array((label == "yes" for label in labels), type=pa.bool_())
    )
    for output_path, rows in (
        (classified_output_path, classified),
        (relevant_output_path, relevant),
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(rows, output_path)
    return classified.num_rows, relevant.num_rows


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
