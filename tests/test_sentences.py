import sys
from types import SimpleNamespace

import pytest

from osm_polygon_web_search.sentences import (
    SAT_MODEL_ID,
    SAT_MODEL_NAME,
    SatSentenceModel,
    load_sat_model,
    prepare_for_segmentation,
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


def test_prepare_for_segmentation_removes_structural_fragments() -> None:
    raw_text = "\n".join(
        [
            "Stausee Steg",
            "Erscheinungsbild",
            "[Bearbeiten | Quelltext bearbeiten]",
            "-",
            "100 %",
            "OpenStreetMap ID",
            "way 119489292",
            "Stausee Steg is an artificial lake surrounded by mountains.",
            "The lake has an elevation of 1295 metres.",
        ]
    )

    assert prepare_for_segmentation(raw_text) == (
        "Stausee Steg is an artificial lake surrounded by mountains.\n"
        "The lake has an elevation of 1295 metres."
    )


def test_prepare_for_segmentation_normalizes_heading_dash_variants() -> None:
    raw_text = "By foot or bike –\nA real trail crosses the valley."

    assert prepare_for_segmentation(raw_text) == "A real trail crosses the valley."


def test_prepare_for_segmentation_keeps_short_sentences_and_prose_bullets() -> None:
    assert (
        prepare_for_segmentation("- The reservoir is surrounded by forest.\nFirst.")
        == "The reservoir is surrounded by forest.\nFirst."
    )


def test_prepare_for_segmentation_returns_empty_text_for_only_noise() -> None:
    assert (
        prepare_for_segmentation("Overview\n-\nLatitude\nOpenStreetMap ID\n100 %") == ""
    )


def test_prepare_for_segmentation_removes_attribution_and_metadata_blocks() -> None:
    raw_text = "\n".join(
        [
            "Photo: Example, CC BY-SA 4.0.",
            "Source: NOAA GFS 0.25°.",
            "Weather in Sareiserjoch",
            "Day length 13 h 41 min",
            "Also known as: Sareiser Joch",
            "View on OpenStreetMap",
            "Sareiserjoch is a pass.",
            "Elevation 1992 m (DEM: 1978 m)",
        ]
    )

    assert prepare_for_segmentation(raw_text) == (
        "Sareiserjoch is a pass.\nElevation 1992 m (DEM: 1978 m)"
    )


def test_prepare_for_segmentation_removes_inline_citations() -> None:
    assert (
        prepare_for_segmentation(
            "Stausee Steg is an artificial lake.[3] It is fed by two streams.[4]"
        )
        == "Stausee Steg is an artificial lake. It is fed by two streams."
    )


def test_prepare_for_segmentation_removes_question_headings_and_ctas() -> None:
    raw_text = "\n".join(
        [
            "A brief summary to Stausee Steg",
            "How to get to Stausee Steg?",
            "Discover the Tranquil Beauty of Stausee Steg",
            "Take control to get all the benefits.",
            "Stausee Steg is a serene lake surrounded by mountains.",
        ]
    )

    assert prepare_for_segmentation(raw_text) == (
        "Stausee Steg is a serene lake surrounded by mountains."
    )


def test_prepare_for_segmentation_removes_remaining_template_fragments() -> None:
    raw_text = "\n".join(
        [
            "8FVF3JCC+6Q",
            "3.6 m/s S (169 deg)",
            "↑ Source: an external reference",
            "Sareiserjoch is a Wikidata entity.",
            "A map to help you discover where Stausee Steg and Gänglesee are:",
            "Circuit hike for the whole family",
            "Stausee Steg: The Ultimate Guide for an Epic Visit",
            "Your all‑in‑one travel companion app",
            "Sareiserjoch is a pass.",
            "Elevation 1992 m (DEM: 1978 m)",
        ]
    )

    assert prepare_for_segmentation(raw_text) == (
        "Sareiserjoch is a pass.\nElevation 1992 m (DEM: 1978 m)"
    )


def test_prepare_for_segmentation_removes_question_and_location_metadata() -> None:
    raw_text = "\n".join(
        [
            "How to get here: Fly into Zurich Airport and drive to the lake",
            "Is precipitation expected in the next 24 hours?",
            "It is at 47.09521, 9.62539 (latitude, longitude).",
            "What is the elevation of Sareiserjoch?",
            "Where is Stausee Steg?",
            "When to visit: June – August",
            "Delve into Bregenz, Dornbirn, Feldkirch, and Bludenz.",
            "Sareiserjoch is a pass.",
        ]
    )

    assert prepare_for_segmentation(raw_text) == "Sareiserjoch is a pass."


def test_prepare_for_segmentation_normalizes_non_breaking_spaces() -> None:
    assert prepare_for_segmentation("XX\u00a0XX is a place.") == "XX XX is a place."


@pytest.mark.parametrize("text", ["Short!", "Question?"])
def test_prepare_for_segmentation_keeps_terminal_punctuation(text: str) -> None:
    assert prepare_for_segmentation(text) == text


def test_prepare_for_segmentation_removes_a_twelve_word_heading() -> None:
    heading = "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliet Kilo Lima"

    assert prepare_for_segmentation(heading) == ""


def test_prepare_for_segmentation_keeps_a_thirteen_word_prose_block() -> None:
    prose = (
        "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliet Kilo Lima Mike"
    )

    assert prepare_for_segmentation(prose) == prose


def test_prepare_for_segmentation_keeps_three_word_fragments() -> None:
    assert prepare_for_segmentation("A quiet valley") == "A quiet valley"


def test_prepare_for_segmentation_handles_remaining_structural_boundaries() -> None:
    raw_text = "\n".join(
        [
            "!!!",
            "elevation = 1992 m",
            "elevation=1992.",
            "1 2 3 reference entry detail",
            "[a useful reference entry]",
            "A useful reference entry]",
            "By foot or bike –",
            "A real place is visible from here.",
        ]
    )

    assert prepare_for_segmentation(raw_text) == (
        "A useful reference entry]\nA real place is visible from here."
    )


def test_prepare_for_segmentation_removes_inline_heading_prefixes() -> None:
    raw_text = "\n".join(
        [
            "By Car – The most convenient way to get to the lake.",
            "Fishing – The reservoir is a popular spot.",
            "The reservoir – surrounded by mountains.",
        ]
    )

    assert prepare_for_segmentation(raw_text) == (
        "The most convenient way to get to the lake.\n"
        "The reservoir is a popular spot.\n"
        "The reservoir – surrounded by mountains."
    )


def test_prepare_for_segmentation_removes_activity_heading_fragments() -> None:
    raw_text = "Enjoy a picnic or a BBQ – Relax by the reservoir.\nEnjoy a swim –"

    assert prepare_for_segmentation(raw_text) == "Relax by the reservoir."


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
        def split(self, texts: list[object], **kwargs: int) -> list[list[object]]:
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
