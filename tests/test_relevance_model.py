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

YES_TOKEN_ID = 101
NO_TOKEN_ID = 202


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
        self.batch = None

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        return {"yes": [YES_TOKEN_ID], "no": [NO_TOKEN_ID]}[text]

    def apply_chat_template(
        self,
        messages: list[list[dict[str, str]]],
        **kwargs: object,
    ) -> FakeBatch:
        self.chat_calls.append((messages, kwargs))
        self.batch = FakeBatch(len(messages))
        return self.batch


class FakeScores:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeLogits:
    def __init__(self, scores: list[tuple[float, float]]) -> None:
        self.scores = scores

    def __getitem__(self, indices: tuple[object, object, int]) -> FakeScores:
        _, position, token_id = indices
        assert position == -1
        score_index = 0 if token_id == YES_TOKEN_ID else 1
        return FakeScores([scores[score_index] for scores in self.scores])


class UnevenLogits:
    def __getitem__(self, indices: tuple[object, object, int]) -> FakeScores:
        _, position, token_id = indices
        assert position == -1
        return FakeScores([2.0] if token_id == YES_TOKEN_ID else [])


class FakeModel:
    device = "cpu"

    def __init__(self, scores: list[tuple[float, float]] | None = None) -> None:
        self.scores = scores
        self.forward_calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> SimpleNamespace:
        self.forward_calls.append(kwargs)
        batch_size = cast(FakeInputIds, kwargs["input_ids"]).shape[0]
        scores = self.scores or [(2.0, 1.0)] * batch_size
        return SimpleNamespace(logits=FakeLogits(scores[:batch_size]))


class UnevenModel:
    device = "cpu"

    def __call__(self, **kwargs: object) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(logits=UnevenLogits())


class FakeTorch:
    def inference_mode(self):
        return nullcontext()


def test_classifier_applies_chat_template_and_scores_final_logits() -> None:
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
    assert model.forward_calls[0]["input_ids"] is tokenizer.batch["input_ids"]
    assert model.forward_calls[0]["logits_to_keep"] == 1
    assert model.forward_calls[0]["use_cache"] is False


def test_classifier_classifies_a_batch_in_one_forward_pass() -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel([(2.0, 1.0), (1.0, 2.0)])
    classifier = LfmRelevanceClassifier(tokenizer, model, FakeTorch())

    sentences = ["A sentence about vegetation.", "A road crosses the valley."]

    assert classifier.classify_many(sentences) == ["yes", "no"]
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
    assert len(model.forward_calls) == 1


def test_classifier_resolves_equal_scores_to_no() -> None:
    classifier = LfmRelevanceClassifier(
        FakeTokenizer(), FakeModel([(1.0, 1.0)]), FakeTorch()
    )

    assert classifier.classify("An ambiguous sentence.") == "no"


def test_classifier_rejects_a_model_batch_with_too_few_scores() -> None:
    classifier = LfmRelevanceClassifier(
        FakeTokenizer(), FakeModel([(2.0, 1.0)]), FakeTorch()
    )

    with pytest.raises(ValueError) as error:
        classifier.classify_many(["First sentence.", "Second sentence."])
    assert str(error.value) == "model output batch does not match input batch"


def test_classifier_rejects_inconsistent_score_batches() -> None:
    classifier = LfmRelevanceClassifier(FakeTokenizer(), UnevenModel(), FakeTorch())

    with pytest.raises(ValueError) as error:
        classifier.classify("A sentence.")
    assert str(error.value) == "model returned inconsistent score batches"


def test_classifier_rejects_a_multitoken_answer_label() -> None:
    class MultiTokenTokenizer(FakeTokenizer):
        def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
            if text == "yes":
                return [YES_TOKEN_ID, 303]
            return super().encode(text, add_special_tokens=add_special_tokens)

    with pytest.raises(ValueError, match="exactly one token"):
        LfmRelevanceClassifier(MultiTokenTokenizer(), FakeModel(), FakeTorch())


@pytest.mark.parametrize(
    ("mps_available", "explicit_device", "expected_device"),
    [(False, None, "cpu"), (True, None, "mps"), (False, "cuda", "cuda")],
)
def test_load_lfm_classifier_uses_one_in_memory_device(
    monkeypatch,
    mps_available: bool,
    explicit_device: str | None,
    expected_device: str,
) -> None:
    def encode(text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        return {"yes": [YES_TOKEN_ID], "no": [NO_TOKEN_ID]}[text]

    tokenizer = SimpleNamespace(padding_side="right", encode=encode)
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

    classifier = (
        load_lfm_classifier(explicit_device)
        if explicit_device is not None
        else load_lfm_classifier()
    )

    assert isinstance(classifier, LfmRelevanceClassifier)
    assert classifier._tokenizer is tokenizer
    assert tokenizer.padding_side == "left"
    assert classifier._yes_token_id == YES_TOKEN_ID
    assert classifier._no_token_id == NO_TOKEN_ID
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
