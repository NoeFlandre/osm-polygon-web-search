from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from osm_polygon_web_search.sentence_dataset import sentence_rows, transform_parquet
from osm_polygon_web_search.sentences import SAT_MODEL_ID


class FakeSegmenter:
    def split(self, text: str) -> list[str]:
        return {
            "First. Second!": [" First. ", "Second!"],
            "First.": ["First."],
            "": [],
        }[text]


def test_sentence_rows_expands_pages_and_retains_page_context() -> None:
    pages = [
        {
            "polygon_name": "Missing text",
            "page_url": "https://example.test/missing",
            "text": None,
        },
        {
            "polygon_name": "Alpe Vermales",
            "page_url": "https://example.test/page",
            "text": "First. Second!",
        },
    ]

    rows = sentence_rows(pages, FakeSegmenter())

    assert rows == [
        {
            "polygon_name": "Alpe Vermales",
            "page_url": "https://example.test/page",
            "text": "First. Second!",
            "sentence": "First.",
            "sentence_index": 0,
            "sentence_count": 2,
            "sentence_model": SAT_MODEL_ID,
        },
        {
            "polygon_name": "Alpe Vermales",
            "page_url": "https://example.test/page",
            "text": "First. Second!",
            "sentence": "Second!",
            "sentence_index": 1,
            "sentence_count": 2,
            "sentence_model": SAT_MODEL_ID,
        },
    ]


def test_transform_parquet_writes_the_expanded_rows(tmp_path: Path) -> None:
    input_path = tmp_path / "input.parquet"
    output_path = tmp_path / "nested" / "deeper" / "output.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [{"page_url": "https://example.test/page", "text": "First. Second!"}]
        ),
        input_path,
    )

    count = transform_parquet(input_path, output_path, FakeSegmenter())
    output = pq.read_table(output_path)

    assert count == 2
    assert output.to_pylist() == [
        {
            "page_url": "https://example.test/page",
            "text": "First. Second!",
            "sentence": "First.",
            "sentence_index": 0,
            "sentence_count": 2,
            "sentence_model": SAT_MODEL_ID,
        },
        {
            "page_url": "https://example.test/page",
            "text": "First. Second!",
            "sentence": "Second!",
            "sentence_index": 1,
            "sentence_count": 2,
            "sentence_model": SAT_MODEL_ID,
        },
    ]


def test_transform_parquet_allows_an_existing_output_directory(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.parquet"
    output_path = tmp_path / "output.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [{"page_url": "https://example.test/page", "text": "First."}]
        ),
        input_path,
    )

    count = transform_parquet(input_path, output_path, FakeSegmenter())

    assert count == 1
