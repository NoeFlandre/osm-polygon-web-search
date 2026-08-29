from collections.abc import Iterable, Sequence
from typing import Any, Protocol

SAT_MODEL_ID = "segment-any-text/sat-3l-sm"
SAT_MODEL_NAME = "sat-3l-sm"
SAT_BATCH_SIZE = 32
SAT_OUTER_BATCH_SIZE = 1000


class SentenceModel(Protocol):
    def split(self, text: str, /) -> Iterable[str]: ...


class SatSentenceModel:
    """Small compatibility adapter around the loaded wtpsplit model."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def split(self, text: str, /) -> Iterable[str]:
        return self._model.split(text)

    def split_many(self, texts: Sequence[str], /) -> Iterable[Iterable[str]]:
        return self._model.split(
            list(texts),
            batch_size=SAT_BATCH_SIZE,
            outer_batch_size=SAT_OUTER_BATCH_SIZE,
        )


def load_sat_model() -> SatSentenceModel:
    """Load the approved SAT-3L-SM sentence segmentation model."""
    from wtpsplit import SaT

    return SatSentenceModel(SaT(SAT_MODEL_NAME, ort_providers=["CPUExecutionProvider"]))


def _clean_segments(segments: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for segment in segments:
        stripped = segment.strip()
        if stripped:
            cleaned.append(stripped)
    return cleaned


def split_sentences(text: str, model: SentenceModel) -> list[str]:
    """Return non-empty, whitespace-trimmed model segments in source order."""
    return _clean_segments(model.split(text))
