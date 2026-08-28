import sys
from contextlib import nullcontext
from types import SimpleNamespace

from osm_polygon_web_search.llm_relevance import build_relevance_prompt
from osm_polygon_web_search.relevance_model import (
    LfmRelevanceClassifier,
    load_lfm_classifier,
)


class FakeInputIds:
    shape = (1, 3, 5)


class FakeBatch(dict):
    def __init__(self) -> None:
        super().__init__(input_ids=FakeInputIds())
        self.device = None

    def to(self, device: str) -> "FakeBatch":
        self.device = device
        return self


class FakeTokenizer:
    def __init__(self) -> None:
        self.chat_calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []
        self.decode_calls: list[tuple[object, dict[str, object]]] = []
        self.batch = None

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        **kwargs: object,
    ) -> FakeBatch:
        self.chat_calls.append((messages, kwargs))
        self.batch = FakeBatch()
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
        return [[1, 2, 3, 4, 5, 6]]


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
                {
                    "role": "user",
                    "content": build_relevance_prompt("A sentence about vegetation."),
                }
            ],
            {
                "add_generation_prompt": True,
                "tokenize": True,
                "return_dict": True,
                "return_tensors": "pt",
            },
        )
    ]
    assert model.generate_calls[0]["input_ids"] is tokenizer.batch["input_ids"]
    assert model.generate_calls[0]["do_sample"] is False
    assert model.generate_calls[0]["max_new_tokens"] == 128
    assert tokenizer.decode_calls == [([6], {"skip_special_tokens": True})]


def test_load_lfm_classifier_uses_the_approved_local_model(monkeypatch) -> None:
    tokenizer = object()
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
        bfloat16="bfloat16", inference_mode=lambda: nullcontext()
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
    assert classifier._model is model
    assert classifier._torch is torch_module
    assert tokenizer_calls == ["LiquidAI/LFM2.5-2.6B"]
    assert model_calls == [
        {
            "model_id": "LiquidAI/LFM2.5-2.6B",
            "device_map": "auto",
            "dtype": "bfloat16",
        }
    ]
