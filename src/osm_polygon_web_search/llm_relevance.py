from typing import Literal, Protocol, TypeAlias

RELEVANCE_MODEL_ID = "LiquidAI/LFM2.5-2.6B"
RELEVANCE_PROMPT_TEMPLATE = (
    "Classify whether the TARGET SENTENCE contains information about the target "
    "place that could help characterize its land use, land cover, or geographic "
    "environment from remote sensing, either directly or through observable "
    "proxies.\n\n"
    "Return exactly one token: yes or no.\n\n"
    "Answer **yes** for information about vegetation, agriculture, forests, "
    "water, soil or surface, terrain, buildings, settlements, infrastructure, "
    "transport networks, mining, managed land, or other human or natural "
    "features with a spatial or remotely detectable signature.\n\n"
    "Answer **no** for information only about history, administration, people, "
    "events, demographics, economy, navigation, or activities with no meaningful "
    "land-use, land-cover, or remotely detectable implication.\n\n"
    "Output only the lowercase token yes or no.\n\n"
    "TARGET SENTENCE: {}"
)

RelevanceLabel: TypeAlias = Literal["yes", "no"]


class RelevanceClassifier(Protocol):
    def classify(self, sentence: str, /) -> RelevanceLabel: ...


def build_relevance_prompt(sentence: str, /) -> str:
    """Insert one target sentence into the approved classification prompt."""
    return RELEVANCE_PROMPT_TEMPLATE.format(sentence)


def parse_relevance_output(output: str, /) -> RelevanceLabel:
    """Return a strict final label, allowing the model's closed think wrapper."""
    final_output = output.strip()
    if "</think>" in final_output:
        final_output = final_output.rsplit("</think>", 1)[1].strip()
    if final_output not in {"yes", "no"}:
        raise ValueError("model output must be exactly one lowercase label: yes or no")
    return final_output
