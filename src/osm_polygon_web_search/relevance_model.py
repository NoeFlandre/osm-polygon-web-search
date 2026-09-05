from collections.abc import Sequence
from typing import Any

from .llm_relevance import (
    RELEVANCE_MODEL_ID,
    RelevanceLabel,
    build_relevance_prompt,
)

LOGITS_TO_KEEP = 1


def _resolve_single_token_id(tokenizer: Any, label: RelevanceLabel, /) -> int:
    token_ids = tokenizer.encode(label, add_special_tokens=False)
    if len(token_ids) != 1:
        raise ValueError(f"{label!r} must encode as exactly one token")
    return token_ids[0]


class LfmRelevanceClassifier:
    """Classify sentences with one already-loaded local LFM model."""

    def __init__(self, tokenizer: Any, model: Any, torch_module: Any) -> None:
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch_module
        self._yes_token_id = _resolve_single_token_id(tokenizer, "yes")
        self._no_token_id = _resolve_single_token_id(tokenizer, "no")

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
            outputs = self._model(
                **inputs,
                logits_to_keep=LOGITS_TO_KEEP,
                use_cache=False,
            )
        yes_scores = outputs.logits[:, -1, self._yes_token_id].tolist()
        no_scores = outputs.logits[:, -1, self._no_token_id].tolist()
        if len(yes_scores) != len(no_scores):
            raise ValueError("model returned inconsistent score batches")
        expected_batch_size = inputs["input_ids"].shape[0]
        if len(yes_scores) != expected_batch_size:
            raise ValueError("model output batch does not match input batch")
        return [
            "yes" if yes_scores[index] > no_scores[index] else "no"
            for index in range(len(yes_scores))
        ]


def load_lfm_classifier(device: str | None = None) -> LfmRelevanceClassifier:
    """Load the approved local model and tokenizer once."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer: Any = AutoTokenizer.from_pretrained(RELEVANCE_MODEL_ID)
    tokenizer.padding_side = "left"
    target_device = (
        device
        if device is not None
        else ("mps" if torch.backends.mps.is_available() else "cpu")
    )
    model = AutoModelForCausalLM.from_pretrained(
        RELEVANCE_MODEL_ID,
        device_map={"": target_device},
        dtype=torch.bfloat16,
    )
    return LfmRelevanceClassifier(tokenizer, model, torch)
