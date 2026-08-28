import pytest

from osm_polygon_web_search.llm_relevance import (
    RELEVANCE_MODEL_ID,
    build_relevance_prompt,
    parse_relevance_output,
)


def test_build_relevance_prompt_matches_the_approved_prompt() -> None:
    sentence = "The glacier has a broad {shaped} basin."

    assert build_relevance_prompt(sentence) == (
        "Classify whether the TARGET SENTENCE contains information about the "
        "target place that could help characterize its land use, land cover, or "
        "geographic environment from remote sensing, either directly or through "
        "observable proxies.\n\n"
        "Return exactly one token: yes or no.\n\n"
        "Answer **yes** for information about vegetation, agriculture, forests, "
        "water, soil or surface, terrain, buildings, settlements, infrastructure, "
        "transport networks, mining, managed land, or other human or natural "
        "features with a spatial or remotely detectable signature.\n\n"
        "Answer **no** for information only about history, administration, people, "
        "events, demographics, economy, navigation, or activities with no "
        "meaningful land-use, land-cover, or remotely detectable implication.\n\n"
        "Output only the lowercase token yes or no.\n\n"
        "TARGET SENTENCE: The glacier has a broad {shaped} basin."
    )

    assert RELEVANCE_MODEL_ID == "LiquidAI/LFM2.5-2.6B"


def test_parse_relevance_output_accepts_plain_and_reasoning_wrapped_labels() -> None:
    assert parse_relevance_output("yes") == "yes"
    assert parse_relevance_output("<think>surface context</think>\nno") == "no"
    assert (
        parse_relevance_output("<think>first pass</think>discarded</think>\nyes")
        == "yes"
    )
    assert parse_relevance_output("<think>surface context</think>yes") == "yes"


@pytest.mark.parametrize(
    "output",
    ["", "maybe", "yes\nno", "<think>unfinished", "yes </think>"],
)
def test_parse_relevance_output_rejects_non_strict_results(output: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_relevance_output(output)

    assert str(error.value) == (
        "model output must be exactly one lowercase label: yes or no"
    )
