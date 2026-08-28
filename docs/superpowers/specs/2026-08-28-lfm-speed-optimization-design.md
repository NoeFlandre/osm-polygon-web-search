# LFM Sentence Classification Speed Optimization

## Goal

Reduce local sentence-classification time while preserving the existing
classification contract, output schema, row order, strict yes/no meaning, and
Seagate-only data boundary.

## Invariants

- Use `LiquidAI/LFM2.5-2.6B` locally.
- Build the same user prompt once for each sentence.
- Keep the assistant `</think>` prefill and left-padding required by LFM2.
- Produce exactly one `yes` or `no` label for every non-empty sentence.
- Preserve the input row order and all existing output columns.
- Write the complete local table and the yes-only Hugging Face table only after
  every sentence has a valid label.
- Do not add a web-search provider, fallback, retry, or new dataset feature.

## Options considered

1. Keep `generate(max_new_tokens=1)` and increase the batch size. This is the
   smallest change, but it retains generation overhead and cannot prevent an
   invalid non-label token.
2. Use one batched forward pass to score only the next-token logits for the
   existing `yes` and `no` tokens. This removes generation and decoding
   overhead, guarantees a valid binary output, and uses LFM2's
   `logits_to_keep=1` capability. This is the selected design.
3. Cache shared prompt prefixes or manually manage KV caches. This could save
   additional work but adds stateful complexity and memory pressure that is
   not justified for the 708-row proof of concept.

## Selected design

The classifier will resolve the tokenizer's single-token IDs for `yes` and
`no` once at load time. For each bounded batch it will apply the current chat
template, move the padded inputs to the model device, and call the loaded
model once with `logits_to_keep=1` under `torch.inference_mode()`. It will
compare the final-position logits for the two label tokens and map the larger
score to the corresponding label. Ties resolve deterministically to `no`,
matching the negative default used by the binary contract.

The dataset transformer will use a measured bounded batch size. The initial
candidate is 16; a real smoke test must demonstrate that it fits the 8 GB
unified-memory machine before it replaces the current size of 8. If it does
not fit or does not improve throughput, the batch size remains 8 and the
logit-only path is retained.

## Failure handling

The loader will fail if either answer is not represented by exactly one token
in the approved tokenizer. The classifier will fail if the model output lacks
the expected final logits or if the number of returned scores does not match
the batch. It will not silently parse, retry, coerce, or publish invalid data.

## Verification

TDD will cover token-ID resolution, final-logit scoring, left-padding,
`logits_to_keep=1`, batch boundaries, row order, and output preservation. The
full repository gates must pass: Ruff, `ty`, pytest with 100% line and branch
coverage, strict MkDocs, pre-commit, and mutation testing with zero survivors.
A real local comparison will verify that valid smoke labels remain unchanged
and that the previously invalid-output condition now yields a deterministic
binary label. Only then will the 708-row local table be generated, validated,
and uploaded to the existing HF dataset.
