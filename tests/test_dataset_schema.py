from collections.abc import Mapping
from typing import get_type_hints

from osm_polygon_web_search.dataset_schema import (
    DatasetRecord,
    DatasetRow,
    RelevanceMetadata,
    SentenceMetadata,
)


def test_dataset_schema_declares_open_rows_and_required_generated_fields() -> None:
    assert DatasetRow == Mapping[str, object]
    assert DatasetRecord == dict[str, object]
    assert set(SentenceMetadata.__required_keys__) == {
        "sentence",
        "sentence_index",
        "sentence_count",
        "sentence_model",
    }
    assert get_type_hints(SentenceMetadata) == {
        "sentence": str,
        "sentence_index": int,
        "sentence_count": int,
        "sentence_model": str,
    }
    assert set(RelevanceMetadata.__required_keys__) == {
        "relevance_label",
        "relevance_model",
    }
