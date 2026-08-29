import sys
from types import SimpleNamespace

from osm_polygon_web_search.sentences import (
    SAT_MODEL_ID,
    SAT_MODEL_NAME,
    SatSentenceModel,
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


def test_sat_sentence_model_forwards_scalar_text() -> None:
    calls: list[object] = []

    class Model:
        def split(self, text: object) -> list[object]:
            calls.append(text)
            return [text]

    adapter = SatSentenceModel(Model())

    assert list(adapter.split("page text")) == ["page text"]
    assert calls == ["page text"]


def test_sat_sentence_model_forwards_batched_texts_and_settings() -> None:
    calls: list[tuple[object, dict[str, int]]] = []

    class Model:
        def split(self, texts: object, **kwargs: int) -> list[list[object]]:
            calls.append((texts, kwargs))
            return [[text] for text in texts]

    adapter = SatSentenceModel(Model())

    assert [list(group) for group in adapter.split_many(("one", "two"))] == [
        ["one"],
        ["two"],
    ]
    assert calls == [
        (
            ["one", "two"],
            {"batch_size": 32, "outer_batch_size": 1000},
        )
    ]


def test_load_sat_model_uses_the_approved_model_name(monkeypatch) -> None:
    created: list[tuple[str, dict[str, list[str]]]] = []
    split_calls: list[tuple[object, dict[str, int]]] = []

    class FakeSaT:
        def __init__(
            self,
            model_name: str,
            **kwargs: list[str],
        ) -> None:
            created.append((model_name, kwargs))

        def split(self, text_or_texts: object, **kwargs: int) -> list[object]:
            split_calls.append((text_or_texts, kwargs))
            if isinstance(text_or_texts, list):
                return [["first"], ["second"]]
            return ["scalar"]

    monkeypatch.setitem(sys.modules, "wtpsplit", SimpleNamespace(SaT=FakeSaT))

    model = load_sat_model()

    assert created == [(SAT_MODEL_NAME, {"ort_providers": ["CPUExecutionProvider"]})]
    assert list(model.split("page")) == ["scalar"]
    assert [list(group) for group in model.split_many(["first", "second"])] == [
        ["first"],
        ["second"],
    ]
    assert split_calls == [
        ("page", {}),
        (["first", "second"], {"batch_size": 32, "outer_batch_size": 1000}),
    ]
    assert SAT_MODEL_ID == "segment-any-text/sat-3l-sm"
