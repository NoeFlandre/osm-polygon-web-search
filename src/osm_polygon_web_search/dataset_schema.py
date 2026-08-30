"""Typed contracts for persisted dataset rows and generated metadata."""

from collections.abc import Mapping
from typing import TypeAlias, TypedDict

from .llm_relevance import RelevanceLabel

DatasetRow: TypeAlias = Mapping[str, object]
DatasetRecord: TypeAlias = dict[str, object]


class SentenceMetadata(TypedDict):
    sentence: str
    sentence_index: int
    sentence_count: int
    sentence_model: str


class RelevanceMetadata(TypedDict):
    relevance_label: RelevanceLabel
    relevance_model: str
