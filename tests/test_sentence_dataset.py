from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from osm_polygon_web_search.sentence_dataset import (
    _sentence_table,
    _source_text_inputs,
    sentence_rows,
    transform_parquet,
)
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


class CountingSegmenter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def split(self, text: str) -> list[str]:
        self.calls.append(text)
        return [text]


def test_iter_text_inputs_keeps_strings_and_skips_other_values() -> None:
    from osm_polygon_web_search.sentence_dataset import _iter_text_inputs

    assert list(
        _iter_text_inputs(
            [
                (2, ""),
                (3, None),
                (4, 42),
                (5, "First."),
            ]
        )
    ) == [(2, ""), (5, "First.")]


def _observe_text_input_calls(monkeypatch):
    import osm_polygon_web_search.sentence_dataset as module

    calls = []
    original = module._iter_text_inputs

    def observe(values):
        materialized = list(values)
        calls.append(materialized)
        return original(materialized)

    monkeypatch.setattr(module, "_iter_text_inputs", observe)
    return calls


def test_sentence_rows_uses_the_shared_text_input_boundary(monkeypatch) -> None:
    calls = _observe_text_input_calls(monkeypatch)
    row = {"page_url": "https://example.test/page", "text": "First."}

    sentence_rows([row], FakeSegmenter())

    assert calls == [[(row, "First.")]]


def test_source_text_inputs_uses_the_shared_text_input_boundary(monkeypatch) -> None:
    calls = _observe_text_input_calls(monkeypatch)
    source = pa.table({"text": pa.array(["First.", None, ""])})

    assert _source_text_inputs(source) == ([0, 2], ["First.", ""])
    assert calls == [[(0, "First."), (1, None), (2, "")]]


def test_source_text_inputs_exposes_named_fields() -> None:
    source = pa.table({"text": pa.array(["First.", None, ""])})

    inputs = _source_text_inputs(source)

    assert inputs.source_indices == [0, 2]
    assert inputs.texts == ["First.", ""]
    assert inputs == ([0, 2], ["First.", ""])


def test_sentence_metadata_has_the_persisted_field_contract() -> None:
    from osm_polygon_web_search.sentence_dataset import _sentence_metadata

    assert _sentence_metadata("First.", 0, 2) == {
        "sentence": "First.",
        "sentence_index": 0,
        "sentence_count": 2,
        "sentence_model": SAT_MODEL_ID,
    }


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
        (row["page_url"], row["sentence"], row["sentence_index"]) for row in rows
    ] == [
        ("https://example.test/one", "One.", 0),
        ("https://example.test/duplicate", "One.", 0),
        ("https://example.test/two", "Two!", 0),
    ]


def test_sentence_rows_keeps_scalar_model_calls_per_page() -> None:
    model = CountingSegmenter()

    rows = sentence_rows(
        [
            {"page_url": "https://example.test/one", "text": "One."},
            {"page_url": "https://example.test/duplicate", "text": "One."},
        ],
        model,
    )

    assert model.calls == ["One.", "One."]
    assert [row["page_url"] for row in rows] == [
        "https://example.test/one",
        "https://example.test/duplicate",
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


def test_expand_sentence_groups_preserves_arrow_row_order_and_metadata() -> None:
    from osm_polygon_web_search.sentence_dataset import _expand_sentence_groups

    assert _expand_sentence_groups(
        [4, 9],
        [["First.", "Second!"], ["Third?"]],
    ) == (
        [4, 4, 9],
        ["First.", "Second!", "Third?"],
        [0, 1, 0],
        [2, 2, 1],
    )


def test_expand_sentence_groups_exposes_named_fields() -> None:
    from osm_polygon_web_search.sentence_dataset import _expand_sentence_groups

    expansion = _expand_sentence_groups(
        [4, 9],
        [["First.", "Second!"], ["Third?"]],
    )

    assert expansion.repeated_indices == [4, 4, 9]
    assert expansion.sentence_values == ["First.", "Second!", "Third?"]
    assert expansion.sentence_indices == [0, 1, 0]
    assert expansion.sentence_counts == [2, 2, 1]


def test_source_text_inputs_keeps_string_rows_in_source_order() -> None:
    from osm_polygon_web_search.sentence_dataset import _source_text_inputs

    source = pa.table({"text": pa.array(["First.", None, ""])})

    assert _source_text_inputs(source) == ([0, 2], ["First.", ""])


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


def test_transform_parquet_expands_rows_without_materializing_mappings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.parquet"
    output_path = tmp_path / "output.parquet"
    pq.write_table(
        pa.table(
            {
                "id": pa.array([1, 2], type=pa.int64()),
                "page_url": pa.array(
                    [
                        "https://example.test/page",
                        "https://example.test/ignored",
                    ],
                    type=pa.string(),
                ),
                "text": pa.array(["First. Second!", None], type=pa.string()),
            }
        ),
        input_path,
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.sentence_dataset.sentence_rows",
        lambda *args: pytest.fail("source rows must stay in Arrow"),
    )

    count = transform_parquet(input_path, output_path, FakeSegmenter())
    output = pq.read_table(output_path)

    assert count == 2
    assert output.column_names == [
        "id",
        "page_url",
        "text",
        "sentence",
        "sentence_index",
        "sentence_count",
        "sentence_model",
    ]
    assert output.to_pylist() == [
        {
            "id": 1,
            "page_url": "https://example.test/page",
            "text": "First. Second!",
            "sentence": "First.",
            "sentence_index": 0,
            "sentence_count": 2,
            "sentence_model": SAT_MODEL_ID,
        },
        {
            "id": 1,
            "page_url": "https://example.test/page",
            "text": "First. Second!",
            "sentence": "Second!",
            "sentence_index": 1,
            "sentence_count": 2,
            "sentence_model": SAT_MODEL_ID,
        },
    ]


def test_transform_parquet_preserves_source_schema_for_empty_output(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.parquet"
    output_path = tmp_path / "output.parquet"
    pq.write_table(
        pa.table(
            {
                "id": pa.array([1], type=pa.int64()),
                "text": pa.array([None], type=pa.string()),
            }
        ),
        input_path,
    )

    count = transform_parquet(input_path, output_path, FakeSegmenter())
    output = pq.read_table(output_path)

    assert count == 0
    assert output.num_rows == 0
    assert output.column_names == [
        "id",
        "text",
        "sentence",
        "sentence_index",
        "sentence_count",
        "sentence_model",
    ]
    assert output.schema.field("sentence").type == pa.string()
    assert output.schema.field("sentence_index").type == pa.int64()
    assert output.schema.field("sentence_count").type == pa.int64()
    assert output.schema.field("sentence_model").type == pa.string()


def test_sentence_table_rejects_a_short_segmentation_result(monkeypatch) -> None:
    source = pa.table({"text": pa.array(["One.", "Two!"])})
    monkeypatch.setattr(
        "osm_polygon_web_search.sentence_dataset._segment_page_texts",
        lambda texts, model: [["One."]],
    )

    with pytest.raises(ValueError, match="argument 2 is shorter"):
        _sentence_table(source, FakeSegmenter())


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
