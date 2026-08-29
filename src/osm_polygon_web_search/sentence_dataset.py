import argparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from .pipeline import ensure_data_path
from .sentences import (
    SAT_MODEL_ID,
    BatchedSentenceModel,
    SentenceModel,
    _clean_segments,
    load_sat_model,
    split_sentences,
)


def _segment_page_texts(
    texts: Sequence[str],
    model: SentenceModel,
) -> list[list[str]]:
    if not texts:
        return []

    split_many = getattr(model, "split_many", None)
    if not callable(split_many):
        return [split_sentences(text, model) for text in texts]

    batched_model = cast(BatchedSentenceModel, model)
    grouped = list(batched_model.split_many(texts))
    if len(grouped) != len(texts):
        raise ValueError("batched sentence model must return one result per text")
    return [_clean_segments(segments) for segments in grouped]


def sentence_rows(
    rows: Iterable[Mapping[str, Any]],
    model: SentenceModel,
) -> list[dict[str, Any]]:
    """Expand page rows into one Viewer row per non-empty SAT sentence."""
    page_rows: list[Mapping[str, Any]] = []
    texts: list[str] = []
    for row in rows:
        text = row.get("text")
        if isinstance(text, str):
            page_rows.append(row)
            texts.append(text)

    sentence_groups = _segment_page_texts(texts, model)
    expanded: list[dict[str, Any]] = []
    for row, sentences in zip(page_rows, sentence_groups, strict=True):
        expanded.extend(
            {
                **row,
                "sentence": sentence,
                "sentence_index": index,
                "sentence_count": len(sentences),
                "sentence_model": SAT_MODEL_ID,
            }
            for index, sentence in enumerate(sentences)
        )
    return expanded


def transform_parquet(
    input_path: Path,
    output_path: Path,
    model: SentenceModel,
) -> int:
    """Write a sentence-level parquet table and return its row count."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    source = pq.read_table(input_path)
    rows = sentence_rows(source.to_pylist(), model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), output_path)
    return len(rows)


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
