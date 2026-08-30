from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from osm_polygon_web_search.llm_relevance import RELEVANCE_MODEL_ID, RelevanceLabel
from osm_polygon_web_search.relevance_dataset import (
    _collect_sentence_inputs,
    _non_empty_sentence,
    classify_rows,
    relevant_rows,
    transform_parquet,
)


class FakeClassifier:
    def __init__(self, labels: dict[str, RelevanceLabel]) -> None:
        self.labels = labels
        self.batch_calls: list[list[str]] = []

    def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
        batch = list(sentences)
        self.batch_calls.append(batch)
        return [self.labels[sentence] for sentence in batch]


class ShortClassifier:
    def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
        del sentences
        return ["yes"]


class LongClassifier:
    def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
        return ["yes"] * (len(sentences) + 1)


def _observe_sentence_input_calls(monkeypatch):
    import osm_polygon_web_search.relevance_dataset as module

    calls = []
    original = module._iter_sentence_inputs

    def observe(values):
        materialized = list(values)
        calls.append(materialized)
        return original(materialized)

    monkeypatch.setattr(module, "_iter_sentence_inputs", observe)
    return calls


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("A sentence.", "A sentence."),
        ("  A sentence.  ", "  A sentence.  "),
        ("  ", None),
        (None, None),
        (42, None),
    ],
)
def test_non_empty_sentence_accepts_only_nonblank_strings(
    value: object,
    expected: str | None,
) -> None:
    assert _non_empty_sentence(value) == expected


def test_iter_sentence_inputs_keeps_sources_and_skips_blank_values() -> None:
    from osm_polygon_web_search.relevance_dataset import _iter_sentence_inputs

    assert list(
        _iter_sentence_inputs(
            [
                (4, "A sentence."),
                (5, "  "),
                (6, None),
                (7, "  Another sentence.  "),
            ]
        )
    ) == [
        (4, "A sentence."),
        (7, "  Another sentence.  "),
    ]


def test_collect_sentence_inputs_preserves_valid_source_order() -> None:
    assert _collect_sentence_inputs(
        [
            (4, "A sentence."),
            (5, "  "),
            (6, None),
            (7, "  Another sentence.  "),
        ]
    ) == (
        [4, 7],
        ["A sentence.", "  Another sentence.  "],
    )


def test_classify_rows_uses_the_shared_sentence_input_boundary(monkeypatch) -> None:
    calls = _observe_sentence_input_calls(monkeypatch)
    classifier = FakeClassifier({"A sentence.": "yes"})

    assert (
        classify_rows([{"id": 1, "sentence": "A sentence."}], classifier)[0][
            "relevance_label"
        ]
        == "yes"
    )
    assert calls == [
        [
            (
                {"id": 1, "sentence": "A sentence."},
                "A sentence.",
            )
        ]
    ]


def test_transform_parquet_uses_the_shared_sentence_input_boundary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.parquet"
    classified_path = tmp_path / "classified.parquet"
    relevant_path = tmp_path / "relevant.parquet"
    pq.write_table(
        pa.table({"sentence": pa.array(["A sentence."])}),
        input_path,
    )

    calls = _observe_sentence_input_calls(monkeypatch)
    transform_parquet(
        input_path,
        classified_path,
        relevant_path,
        FakeClassifier({"A sentence.": "yes"}),
    )

    assert calls == [[(0, "A sentence.")]]


def test_classify_rows_preserves_context_and_skips_rows_without_sentences() -> None:
    classifier = FakeClassifier(
        {
            "A forest covers the slope.": "yes",
            "The place was mentioned in 1840.": "no",
        }
    )

    rows = classify_rows(
        [
            {"id": 1, "sentence": "A forest covers the slope."},
            {"id": 2, "sentence": None},
            {"id": 3, "sentence": "The place was mentioned in 1840."},
            {"id": 4, "sentence": "  "},
            {"id": 5},
        ],
        classifier,
    )

    assert rows == [
        {
            "id": 1,
            "sentence": "A forest covers the slope.",
            "relevance_label": "yes",
            "relevance_model": RELEVANCE_MODEL_ID,
        },
        {
            "id": 3,
            "sentence": "The place was mentioned in 1840.",
            "relevance_label": "no",
            "relevance_model": RELEVANCE_MODEL_ID,
        },
    ]
    assert classifier.batch_calls == [
        [
            "A forest covers the slope.",
            "The place was mentioned in 1840.",
        ]
    ]


def test_classify_rows_splits_large_inputs_into_bounded_batches() -> None:
    sentences = [f"Sentence {index}." for index in range(17)]
    classifier = FakeClassifier(dict.fromkeys(sentences, "no"))

    rows = classify_rows(
        [
            {"id": index, "sentence": sentence}
            for index, sentence in enumerate(sentences)
        ],
        classifier,
    )

    assert len(rows) == 17
    assert classifier.batch_calls == [sentences[:16], sentences[16:]]


def test_classify_rows_rejects_a_batch_with_too_few_labels() -> None:
    with pytest.raises(
        ValueError,
        match="^classifier must return one label per sentence$",
    ):
        classify_rows(
            [
                {"id": 1, "sentence": "A forest covers the slope."},
                {"id": 2, "sentence": "A road crosses the valley."},
            ],
            ShortClassifier(),
        )


def test_classify_rows_rejects_a_batch_with_too_many_labels() -> None:
    with pytest.raises(
        ValueError,
        match="^classifier must return one label per sentence$",
    ):
        classify_rows(
            [
                {"id": 1, "sentence": "A forest covers the slope."},
                {"id": 2, "sentence": "A road crosses the valley."},
            ],
            LongClassifier(),
        )


def test_relevant_rows_keeps_only_yes_labels() -> None:
    rows = [
        {"id": 1, "relevance_label": "yes"},
        {"id": 2, "relevance_label": "no"},
        {"id": 3},
    ]

    assert relevant_rows(rows) == [{"id": 1, "relevance_label": "yes"}]


def test_transform_parquet_writes_full_and_relevant_tables(tmp_path: Path) -> None:
    input_path = tmp_path / "input.parquet"
    output_directory = tmp_path / "nested" / "deeper"
    classified_path = output_directory / "classified.parquet"
    relevant_path = output_directory / "relevant.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"id": 1, "sentence": "A forest covers the slope."},
                {"id": 2, "sentence": "The place was mentioned in 1840."},
            ]
        ),
        input_path,
    )

    counts = transform_parquet(
        input_path,
        classified_path,
        relevant_path,
        FakeClassifier(
            {
                "A forest covers the slope.": "yes",
                "The place was mentioned in 1840.": "no",
            }
        ),
    )

    assert counts == (2, 1)
    assert pq.read_table(classified_path).to_pylist() == [
        {
            "id": 1,
            "sentence": "A forest covers the slope.",
            "relevance_label": "yes",
            "relevance_model": RELEVANCE_MODEL_ID,
        },
        {
            "id": 2,
            "sentence": "The place was mentioned in 1840.",
            "relevance_label": "no",
            "relevance_model": RELEVANCE_MODEL_ID,
        },
    ]
    assert pq.read_table(relevant_path).to_pylist() == [
        {
            "id": 1,
            "sentence": "A forest covers the slope.",
            "relevance_label": "yes",
            "relevance_model": RELEVANCE_MODEL_ID,
        }
    ]


def test_transform_parquet_keeps_source_rows_in_arrow(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.parquet"
    classified_path = tmp_path / "classified.parquet"
    relevant_path = tmp_path / "relevant.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"id": 1, "sentence": "A forest covers the slope."},
                {"id": 2, "sentence": None},
                {"id": 3, "sentence": "  "},
                {"id": 4, "sentence": "The place was mentioned in 1840."},
            ]
        ),
        input_path,
    )

    monkeypatch.setattr(
        "osm_polygon_web_search.relevance_dataset.classify_rows",
        lambda *args, **kwargs: pytest.fail("whole source rows were materialized"),
    )

    counts = transform_parquet(
        input_path,
        classified_path,
        relevant_path,
        FakeClassifier(
            {
                "A forest covers the slope.": "yes",
                "The place was mentioned in 1840.": "no",
            }
        ),
    )

    assert counts == (2, 1)
    assert pq.read_table(classified_path).to_pylist() == [
        {
            "id": 1,
            "sentence": "A forest covers the slope.",
            "relevance_label": "yes",
            "relevance_model": RELEVANCE_MODEL_ID,
        },
        {
            "id": 4,
            "sentence": "The place was mentioned in 1840.",
            "relevance_label": "no",
            "relevance_model": RELEVANCE_MODEL_ID,
        },
    ]


def test_transform_parquet_preserves_string_schema_for_empty_selection(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.parquet"
    classified_path = tmp_path / "classified.parquet"
    relevant_path = tmp_path / "relevant.parquet"
    pq.write_table(
        pa.Table.from_pylist([{"id": 1, "sentence": None}]),
        input_path,
    )

    counts = transform_parquet(
        input_path,
        classified_path,
        relevant_path,
        FakeClassifier({}),
    )
    classified = pq.read_table(classified_path)
    relevant = pq.read_table(relevant_path)

    assert counts == (0, 0)
    assert classified.num_rows == 0
    assert classified.column_names == [
        "id",
        "sentence",
        "relevance_label",
        "relevance_model",
    ]
    assert classified.schema.field("relevance_label").type == pa.string()
    assert classified.schema.field("relevance_model").type == pa.string()
    assert relevant.schema == classified.schema


def test_transform_parquet_rejects_a_short_classifier_batch(tmp_path: Path) -> None:
    input_path = tmp_path / "input.parquet"
    classified_path = tmp_path / "classified.parquet"
    relevant_path = tmp_path / "relevant.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"id": 1, "sentence": "A forest covers the slope."},
                {"id": 2, "sentence": "A road crosses the valley."},
            ]
        ),
        input_path,
    )

    with pytest.raises(
        ValueError,
        match="^classifier must return one label per sentence$",
    ):
        transform_parquet(
            input_path,
            classified_path,
            relevant_path,
            ShortClassifier(),
        )
