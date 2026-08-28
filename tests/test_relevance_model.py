import sys
from contextlib import nullcontext
from types import SimpleNamespace
from typing import cast

import pytest

from osm_polygon_web_search.llm_relevance import build_relevance_prompt
from osm_polygon_web_search.relevance_model import (
    LfmRelevanceClassifier,
    load_lfm_classifier,
)


class FakeInputIds:
    def __init__(self, batch_size: int) -> None:
        self.shape = (batch_size, 5)


class FakeBatch(dict):
    def __init__(self, batch_size: int) -> None:
        super().__init__(input_ids=FakeInputIds(batch_size))
        self.device = None

    def to(self, device: str) -> "FakeBatch":
        self.device = device
        return self


class FakeTokenizer:
    def __init__(self) -> None:
        self.chat_calls: list[tuple[list[list[dict[str, str]]], dict[str, object]]] = []
        self.decode_calls: list[tuple[object, dict[str, object]]] = []
        self.batch = None

    def apply_chat_template(
        self,
        messages: list[list[dict[str, str]]],
        **kwargs: object,
    ) -> FakeBatch:
        self.chat_calls.append((messages, kwargs))
        self.batch = FakeBatch(len(messages))
        return self.batch

    def decode(self, tokens: object, **kwargs: object) -> str:
        self.decode_calls.append((tokens, kwargs))
        return "yes"


class FakeModel:
    device = "cpu"

    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> list[list[int]]:
        self.generate_calls.append(kwargs)
        batch_size = cast(FakeInputIds, kwargs["input_ids"]).shape[0]
        return [[1, 2, 3, 4, 5, 6] for _ in range(batch_size)]


class FakeTorch:
    def inference_mode(self):
        return nullcontext()


def test_classifier_applies_chat_template_and_decodes_only_new_tokens() -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel()
    classifier = LfmRelevanceClassifier(tokenizer, model, FakeTorch())

    assert classifier.classify("A sentence about vegetation.") == "yes"
    assert tokenizer.batch is not None
    assert tokenizer.batch.device == "cpu"
    assert tokenizer.chat_calls == [
        (
            [
                [
                    {
                        "role": "user",
                        "content": build_relevance_prompt(
                            "A sentence about vegetation."
                        ),
                    },
                    {"role": "assistant", "content": "</think>"},
                ]
            ],
            {
                "continue_final_message": True,
                "tokenize": True,
                "padding": True,
                "return_dict": True,
                "return_tensors": "pt",
            },
        )
    ]
    assert model.generate_calls[0]["input_ids"] is tokenizer.batch["input_ids"]
    assert model.generate_calls[0]["do_sample"] is False
    assert model.generate_calls[0]["max_new_tokens"] == 1
    assert tokenizer.decode_calls == [([6], {"skip_special_tokens": True})]


def test_classifier_classifies_a_batch_in_one_generation() -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel()
    classifier = LfmRelevanceClassifier(tokenizer, model, FakeTorch())

    sentences = ["A sentence about vegetation.", "A road crosses the valley."]

    assert classifier.classify_many(sentences) == ["yes", "yes"]
    assert tokenizer.chat_calls[0][0] == [
        [
            {
                "role": "user",
                "content": build_relevance_prompt(sentences[0]),
            },
            {"role": "assistant", "content": "</think>"},
        ],
        [
            {
                "role": "user",
                "content": build_relevance_prompt(sentences[1]),
            },
            {"role": "assistant", "content": "</think>"},
        ],
    ]
    assert len(model.generate_calls) == 1


@pytest.mark.parametrize(
    ("mps_available", "expected_device"),
    [(False, "cpu"), (True, "mps")],
)
def test_load_lfm_classifier_uses_one_in_memory_device(
    monkeypatch,
    mps_available: bool,
    expected_device: str,
) -> None:
    tokenizer = SimpleNamespace(padding_side="right")
    model = object()
    tokenizer_calls: list[str] = []
    model_calls: list[dict[str, object]] = []

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(model_id: str) -> object:
            tokenizer_calls.append(model_id)
            return tokenizer

    class FakeAutoModel:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> object:
            model_calls.append({"model_id": model_id, **kwargs})
            return model

    torch_module = SimpleNamespace(
        bfloat16="bfloat16",
        inference_mode=lambda: nullcontext(),
        backends=SimpleNamespace(
            mps=SimpleNamespace(is_available=lambda: mps_available)
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoModelForCausalLM=FakeAutoModel,
            AutoTokenizer=FakeAutoTokenizer,
        ),
    )

    classifier = load_lfm_classifier()

    assert isinstance(classifier, LfmRelevanceClassifier)
    assert classifier._tokenizer is tokenizer
    assert tokenizer.padding_side == "left"
    assert classifier._model is model
    assert classifier._torch is torch_module
    assert tokenizer_calls == ["LiquidAI/LFM2.5-2.6B"]
    assert model_calls == [
        {
            "model_id": "LiquidAI/LFM2.5-2.6B",
            "device_map": {"": expected_device},
            "dtype": "bfloat16",
        }
    ]
