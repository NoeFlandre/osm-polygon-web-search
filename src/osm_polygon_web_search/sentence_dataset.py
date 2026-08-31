from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TypeVar

from .data_root import ensure_data_path
from .dataset_schema import DatasetRecord, DatasetRow, SentenceMetadata
from .sentences import (
    SAT_MODEL_ID,
    SentenceModel,
    _clean_segments,
    load_sat_model,
    prepare_for_segmentation,
    split_sentences,
)

if TYPE_CHECKING:
    import pyarrow as pa

SourceT = TypeVar("SourceT")


def _iter_text_inputs(
    values: Iterable[tuple[SourceT, object]],
) -> Iterator[tuple[SourceT, str]]:
    for source, value in values:
        if isinstance(value, str):
            yield source, value


def _segment_page_texts(
    texts: Sequence[str],
    model: SentenceModel,
) -> list[list[str]]:
    if not texts:
        return []

    prepared_texts = [prepare_for_segmentation(text) for text in texts]

    split_many = getattr(model, "split_many", None)
    if not callable(split_many):
        return [split_sentences(text, model) for text in prepared_texts]

    unique_texts = list(dict.fromkeys(prepared_texts))
    grouped = list(split_many(unique_texts))
    if len(grouped) != len(unique_texts):
        raise ValueError("batched sentence model must return one result per text")
    unique_groups = [_clean_segments(segments) for segments in grouped]

    groups_by_text = {
        text: unique_groups[index] for index, text in enumerate(unique_texts)
    }
    return [groups_by_text[text] for text in prepared_texts]


class _SentenceExpansion(NamedTuple):
    repeated_indices: list[int]
    sentence_values: list[str]
    sentence_indices: list[int]
    sentence_counts: list[int]


def _expand_sentence_groups(
    source_indices: Sequence[int],
    sentence_groups: Sequence[Sequence[str]],
) -> _SentenceExpansion:
    repeated_indices: list[int] = []
    sentence_values: list[str] = []
    sentence_indices: list[int] = []
    sentence_counts: list[int] = []
    for source_index, sentences in zip(source_indices, sentence_groups, strict=True):
        count = len(sentences)
        repeated_indices.extend([source_index] * count)
        sentence_values.extend(sentences)
        sentence_indices.extend(range(count))
        sentence_counts.extend([count] * count)
    return _SentenceExpansion(
        repeated_indices,
        sentence_values,
        sentence_indices,
        sentence_counts,
    )


def _sentence_metadata(
    sentence: str,
    sentence_index: int,
    sentence_count: int,
) -> SentenceMetadata:
    return {
        "sentence": sentence,
        "sentence_index": sentence_index,
        "sentence_count": sentence_count,
        "sentence_model": SAT_MODEL_ID,
    }


def sentence_rows(
    rows: Iterable[DatasetRow],
    model: SentenceModel,
) -> list[DatasetRecord]:
    """Expand page rows into one Viewer row per non-empty SAT sentence."""
    page_rows: list[DatasetRow] = []
    texts: list[str] = []
    inputs = ((row, row.get("text")) for row in rows)
    for row, text in _iter_text_inputs(inputs):
        page_rows.append(row)
        texts.append(text)

    sentence_groups = _segment_page_texts(texts, model)
    expanded: list[DatasetRecord] = []
    for page_index, row in enumerate(page_rows):
        sentences = sentence_groups[page_index]
        expanded.extend(
            {
                **row,
                **_sentence_metadata(sentence, sentence_index, len(sentences)),
            }
            for sentence_index, sentence in enumerate(sentences)
        )
    return expanded


class _SourceTextInputs(NamedTuple):
    source_indices: list[int]
    texts: list[str]


def _source_text_inputs(source: pa.Table) -> _SourceTextInputs:
    text_values = source["text"].to_pylist() if "text" in source.column_names else []
    source_indices: list[int] = []
    texts: list[str] = []
    for index, text in _iter_text_inputs(enumerate(text_values)):
        source_indices.append(index)
        texts.append(text)
    return _SourceTextInputs(source_indices, texts)


def _sentence_table(source: pa.Table, model: SentenceModel) -> pa.Table:
    import pyarrow as pa

    inputs = _source_text_inputs(source)
    sentence_groups = _segment_page_texts(inputs.texts, model)
    expansion = _expand_sentence_groups(inputs.source_indices, sentence_groups)

    selected = source.take(pa.array(expansion.repeated_indices, type=pa.int64()))
    return (
        selected.append_column(
            "sentence",
            pa.array(expansion.sentence_values, type=pa.string()),
        )
        .append_column(
            "sentence_index",
            pa.array(expansion.sentence_indices, type=pa.int64()),
        )
        .append_column(
            "sentence_count",
            pa.array(expansion.sentence_counts, type=pa.int64()),
        )
        .append_column(
            "sentence_model",
            pa.array(
                [SAT_MODEL_ID] * len(expansion.sentence_values),
                type=pa.string(),
            ),
        )
    )


def transform_parquet(
    input_path: Path,
    output_path: Path,
    model: SentenceModel,
) -> int:
    """Write a sentence-level parquet table and return its row count."""
    import pyarrow.parquet as pq

    source = pq.read_table(input_path)
    rows = _sentence_table(source, model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(rows, output_path)
    return rows.num_rows


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Split a Viewer parquet table into SAT sentence rows"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    input_path = ensure_data_path(args.input)
    output_path = ensure_data_path(args.output)
    count = transform_parquet(input_path, output_path, load_sat_model())
    print(f"{count} sentence rows written")
