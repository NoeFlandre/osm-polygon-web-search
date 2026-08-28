from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from osm_polygon_web_search.llm_relevance import RELEVANCE_MODEL_ID, RelevanceLabel
from osm_polygon_web_search.relevance_dataset import (
    classify_rows,
    relevant_rows,
    transform_parquet,
)


class FakeClassifier:
    def __init__(self, labels: dict[str, RelevanceLabel]) -> None:
        self.labels = labels
        self.calls: list[str] = []

    def classify(self, sentence: str) -> RelevanceLabel:
        self.calls.append(sentence)
        return self.labels[sentence]


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
    assert classifier.calls == [
        "A forest covers the slope.",
        "The place was mentioned in 1840.",
    ]


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
