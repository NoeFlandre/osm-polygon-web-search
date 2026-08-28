import sys
from types import SimpleNamespace

from osm_polygon_web_search.sentences import (
    SAT_MODEL_ID,
    SAT_MODEL_NAME,
    load_sat_model,
    split_sentences,
)


class FakeSegmenter:
    def __init__(self, segments: list[str]) -> None:
        self.segments = segments
        self.inputs: list[str] = []

    def split(self, text: str) -> list[str]:
        self.inputs.append(text)
        return self.segments


def test_split_sentences_trims_and_discards_empty_model_segments() -> None:
    model = FakeSegmenter([" First sentence. ", "", " Second sentence! "])

    assert split_sentences("page text", model) == [
        "First sentence.",
        "Second sentence!",
    ]
    assert model.inputs == ["page text"]


def test_load_sat_model_uses_the_approved_model_name(monkeypatch) -> None:
    created: list[tuple[str, dict[str, list[str]]]] = []

    class FakeSaT:
        def __init__(
            self,
            model_name: str,
            **kwargs: list[str],
        ) -> None:
            created.append((model_name, kwargs))

    monkeypatch.setitem(sys.modules, "wtpsplit", SimpleNamespace(SaT=FakeSaT))

    model = load_sat_model()

    assert isinstance(model, FakeSaT)
    assert created == [(SAT_MODEL_NAME, {"ort_providers": ["CPUExecutionProvider"]})]
    assert SAT_MODEL_ID == "segment-any-text/sat-3l-sm"
