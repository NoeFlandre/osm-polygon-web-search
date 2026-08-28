from typing import Any

from .llm_relevance import (
    RELEVANCE_MODEL_ID,
    RelevanceLabel,
    build_relevance_prompt,
    parse_relevance_output,
)

MAX_NEW_TOKENS = 128


class LfmRelevanceClassifier:
    """Classify sentences with one already-loaded local LFM model."""

    def __init__(self, tokenizer: Any, model: Any, torch_module: Any) -> None:
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch_module

    def classify(self, sentence: str, /) -> RelevanceLabel:
        messages = [{"role": "user", "content": build_relevance_prompt(sentence)}]
        inputs = self._tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
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
        prompt_length = inputs["input_ids"].shape[-1]
        generated_tokens = outputs[0][prompt_length:]
        decoded = self._tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
        )
        return parse_relevance_output(decoded)


def load_lfm_classifier() -> LfmRelevanceClassifier:
    """Load the approved local model and tokenizer once."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(RELEVANCE_MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        RELEVANCE_MODEL_ID,
        device_map="auto",
        dtype=torch.bfloat16,
    )
    return LfmRelevanceClassifier(tokenizer, model, torch)
