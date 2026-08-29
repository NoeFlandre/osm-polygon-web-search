from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from osm_polygon_web_search.sentence_dataset import sentence_rows, transform_parquet
from osm_polygon_web_search.sentences import SAT_MODEL_ID


class FakeSegmenter:
    def split(self, text: str) -> list[str]:
        return {
            "First. Second!": [" First. ", "Second!"],
            "First.": ["First."],
            "": [],
        }[text]


class FakeBatchedSegmenter:
    def __init__(self, groups: list[list[str]]) -> None:
        self.groups = groups
        self.inputs: list[list[str]] = []

    def split(self, text: str) -> list[str]:
        raise AssertionError(f"scalar split used for {text}")

    def split_many(self, texts: list[str]) -> list[list[str]]:
        self.inputs.append(texts)
        return self.groups


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


def test_sentence_rows_uses_batch_segmentation_when_available() -> None:
    pages = [
        {"page_url": "https://example.test/one", "text": "One."},
        {"page_url": "https://example.test/two", "text": "Two!"},
    ]
    model = FakeBatchedSegmenter([[" One. "], [" Two! ", ""]])

    rows = sentence_rows(pages, model)

    assert model.inputs == [["One.", "Two!"]]
    assert [(row["page_url"], row["sentence"]) for row in rows] == [
        ("https://example.test/one", "One."),
        ("https://example.test/two", "Two!"),
    ]
    assert [row["sentence_count"] for row in rows] == [1, 1]


def test_sentence_rows_segments_duplicate_text_once() -> None:
    pages = [
        {"page_url": "https://example.test/one", "text": "One."},
        {"page_url": "https://example.test/duplicate", "text": "One."},
        {"page_url": "https://example.test/two", "text": "Two!"},
    ]
    model = FakeBatchedSegmenter([[" One. "], [" Two! "]])

    rows = sentence_rows(pages, model)

    assert model.inputs == [["One.", "Two!"]]
    assert [
        (row["page_url"], row["sentence"], row["sentence_index"])
        for row in rows
    ] == [
        ("https://example.test/one", "One.", 0),
        ("https://example.test/duplicate", "One.", 0),
        ("https://example.test/two", "Two!", 0),
    ]


def test_sentence_rows_rejects_a_batch_result_count_mismatch() -> None:
    model = FakeBatchedSegmenter([["Only one result"]])

    with pytest.raises(
        ValueError,
        match="^batched sentence model must return one result per text$",
    ):
        sentence_rows(
            [
                {"page_url": "https://example.test/one", "text": "One."},
                {"page_url": "https://example.test/two", "text": "Two!"},
            ],
            model,
        )


def test_sentence_rows_does_not_call_a_batch_model_without_page_text() -> None:
    model = FakeBatchedSegmenter([])

    assert sentence_rows([{"page_url": "https://example.test/missing"}], model) == []
    assert model.inputs == []


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
