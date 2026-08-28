from collections.abc import Sequence
from typing import Any

from .llm_relevance import (
    RELEVANCE_MODEL_ID,
    RelevanceLabel,
    build_relevance_prompt,
    parse_relevance_output,
)

MAX_NEW_TOKENS = 1


class LfmRelevanceClassifier:
    """Classify sentences with one already-loaded local LFM model."""

    def __init__(self, tokenizer: Any, model: Any, torch_module: Any) -> None:
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch_module

    def classify(self, sentence: str, /) -> RelevanceLabel:
        return self.classify_many([sentence])[0]

    def classify_many(self, sentences: Sequence[str], /) -> list[RelevanceLabel]:
        messages = [
            [
                {"role": "user", "content": build_relevance_prompt(sentence)},
                {"role": "assistant", "content": "</think>"},
            ]
            for sentence in sentences
        ]
        inputs = self._tokenizer.apply_chat_template(
            messages,
            continue_final_message=True,
            tokenize=True,
            padding=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self._model.device)
        with self._torch.inference_mode():
            outputs = self._model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=MAX_NEW_TOKENS,
            )
        prompt_length = inputs["input_ids"].shape[1]
        return [
            parse_relevance_output(
                self._tokenizer.decode(
                    generated_tokens[prompt_length:],
                    skip_special_tokens=True,
                )
            )
            for generated_tokens in outputs
        ]


def load_lfm_classifier() -> LfmRelevanceClassifier:
    """Load the approved local model and tokenizer once."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer: Any = AutoTokenizer.from_pretrained(RELEVANCE_MODEL_ID)
    tokenizer.padding_side = "left"
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        RELEVANCE_MODEL_ID,
        device_map={"": device},
        dtype=torch.bfloat16,
    )
    return LfmRelevanceClassifier(tokenizer, model, torch)
