from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from .data_root import ensure_data_path
from .dataset_schema import DatasetRecord, DatasetRow, RelevanceMetadata
from .llm_relevance import (
    RELEVANCE_MODEL_ID,
    RelevanceClassifier,
    RelevanceLabel,
)
from .relevance_model import load_lfm_classifier

if TYPE_CHECKING:
    import pyarrow as pa


CLASSIFICATION_BATCH_SIZE = 16
SourceT = TypeVar("SourceT")


def _collect_sentence_inputs(
    values: Iterable[tuple[SourceT, object]],
) -> tuple[list[SourceT], list[str]]:
    sources: list[SourceT] = []
    sentences: list[str] = []
    for source, sentence in values:
        if isinstance(sentence, str) and sentence.strip():
            sources.append(source)
            sentences.append(sentence)
    return sources, sentences


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


def _relevance_metadata(label: RelevanceLabel) -> RelevanceMetadata:
    return {
        "relevance_label": label,
        "relevance_model": RELEVANCE_MODEL_ID,
    }


def classify_rows(
    rows: Iterable[DatasetRow],
    classifier: RelevanceClassifier,
) -> list[DatasetRecord]:
    """Add one strict local relevance label to every non-empty sentence row."""
    source_rows, sentences = _collect_sentence_inputs(
        (row, row.get("sentence")) for row in rows
    )
    sentence_rows: list[DatasetRecord] = [dict(row) for row in source_rows]

    labels = _classify_sentences(sentences, classifier)
    for index, row in enumerate(sentence_rows):
        row.update(_relevance_metadata(labels[index]))
    return sentence_rows


def relevant_rows(rows: Iterable[DatasetRow]) -> list[DatasetRecord]:
    """Keep only rows whose validated model label is yes."""
    return [dict(row) for row in rows if row.get("relevance_label") == "yes"]


def _source_sentence_inputs(source: pa.Table) -> tuple[list[int], list[str]]:
    sentence_values = (
        source["sentence"].to_pylist() if "sentence" in source.column_names else []
    )
    return _collect_sentence_inputs(enumerate(sentence_values))


def _relevance_tables(
    source: pa.Table,
    row_indices: Sequence[int],
    labels: Sequence[RelevanceLabel],
) -> tuple[pa.Table, pa.Table]:
    import pyarrow as pa

    if len(row_indices) != len(labels):
        raise ValueError("label count does not match sentence rows")
    selected = source.take(pa.array(row_indices, type=pa.int64()))
    classified = selected.append_column(
        "relevance_label",
        pa.array(labels, type=pa.string()),
    ).append_column(
        "relevance_model",
        pa.array([RELEVANCE_MODEL_ID] * len(labels), type=pa.string()),
    )
    relevant = classified.filter(
        pa.array([label == "yes" for label in labels], type=pa.bool_())
    )
    return classified, relevant


def _write_relevance_tables(
    classified_output_path: Path,
    relevant_output_path: Path,
    classified: pa.Table,
    relevant: pa.Table,
) -> None:
    import pyarrow.parquet as pq

    for output_path, rows in (
        (classified_output_path, classified),
        (relevant_output_path, relevant),
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(rows, output_path)


def transform_parquet(
    input_path: Path,
    classified_output_path: Path,
    relevant_output_path: Path,
    classifier: RelevanceClassifier,
) -> tuple[int, int]:
    """Write full local labels and the yes-only Viewer table."""
    import pyarrow.parquet as pq

    source = pq.read_table(input_path)
    valid_indices, sentences = _source_sentence_inputs(source)
    labels = _classify_sentences(sentences, classifier)
    classified, relevant = _relevance_tables(source, valid_indices, labels)
    _write_relevance_tables(
        classified_output_path,
        relevant_output_path,
        classified,
        relevant,
    )
    return classified.num_rows, relevant.num_rows


def transform_labeled_parquet(
    input_path: Path,
    classified_output_path: Path,
    relevant_output_path: Path,
    row_indices: Sequence[int],
    labels: Sequence[RelevanceLabel],
) -> tuple[int, int]:
    """Join externally produced labels onto the exact valid source rows."""
    import pyarrow.parquet as pq

    source = pq.read_table(input_path)
    valid_indices, _ = _source_sentence_inputs(source)
    if list(row_indices) != valid_indices:
        raise ValueError("label row indices do not match sentence rows")
    classified, relevant = _relevance_tables(source, valid_indices, labels)
    _write_relevance_tables(
        classified_output_path,
        relevant_output_path,
        classified,
        relevant,
    )
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
