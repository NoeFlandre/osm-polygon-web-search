from collections.abc import Iterable
from typing import Protocol

SAT_MODEL_ID = "segment-any-text/sat-3l-sm"
SAT_MODEL_NAME = "sat-3l-sm"


class SentenceModel(Protocol):
    def split(self, text: str, /) -> Iterable[str]: ...


def load_sat_model() -> SentenceModel:
    """Load the approved SAT-3L-SM sentence segmentation model."""
    from wtpsplit import SaT

    return SaT(SAT_MODEL_NAME, ort_providers=["CPUExecutionProvider"])


def split_sentences(text: str, model: SentenceModel) -> list[str]:
    """Return non-empty, whitespace-trimmed model segments in source order."""
    return [segment.strip() for segment in model.split(text) if segment.strip()]
