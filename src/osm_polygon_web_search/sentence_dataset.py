import argparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .pipeline import ensure_data_path
from .sentences import (
    SAT_MODEL_ID,
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

    unique_texts = list(dict.fromkeys(texts))
    split_many = getattr(model, "split_many", None)
    if callable(split_many):
        grouped = list(split_many(unique_texts))
        if len(grouped) != len(unique_texts):
            raise ValueError("batched sentence model must return one result per text")
        unique_groups = [_clean_segments(segments) for segments in grouped]
    else:
        unique_groups = [split_sentences(text, model) for text in unique_texts]

    groups_by_text = dict(zip(unique_texts, unique_groups, strict=True))
    return [groups_by_text[text] for text in texts]


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
    for index, row in enumerate(page_rows):
        sentences = sentence_groups[index]
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
