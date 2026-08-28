import argparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .pipeline import ensure_data_path
from .sentences import (
    SAT_MODEL_ID,
    SentenceModel,
    load_sat_model,
    split_sentences,
)


def sentence_rows(
    rows: Iterable[Mapping[str, Any]],
    model: SentenceModel,
) -> list[dict[str, Any]]:
    """Expand page rows into one Viewer row per non-empty SAT sentence."""
    expanded: list[dict[str, Any]] = []
    for row in rows:
        text = row.get("text")
        if not isinstance(text, str):
            continue
        sentences = split_sentences(text, model)
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
