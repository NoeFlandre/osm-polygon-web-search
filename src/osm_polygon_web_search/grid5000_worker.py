from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeAlias

from .grid5000 import (
    LabelPayload,
    build_label_payload,
    parse_label_payload,
    parse_sentence_payload,
    validate_label_payload,
)
from .llm_relevance import RelevanceClassifier, RelevanceLabel
from .relevance_model import load_lfm_classifier

DEFAULT_BATCH_SIZE = 16
PayloadWriter: TypeAlias = Callable[[Path, bytes], None]


def _write_payload(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_bytes(payload)
    temporary_path.replace(path)


def _checkpoint_state(
    checkpoint_path: Path,
    expected_row_indices: Sequence[int],
) -> tuple[list[RelevanceLabel], bool]:
    if not checkpoint_path.exists():
        return [], False
    checkpoint: LabelPayload = parse_label_payload(checkpoint_path.read_bytes())
    expected_indices = (
        expected_row_indices
        if checkpoint["complete"]
        else expected_row_indices[: len(checkpoint["entries"])]
    )
    labels = validate_label_payload(
        checkpoint,
        expected_indices,
        expected_complete=checkpoint["complete"],
    )
    return labels, checkpoint["complete"]


def _validate_batch_labels(
    labels: Sequence[RelevanceLabel], expected_count: int
) -> None:
    if len(labels) != expected_count:
        raise ValueError("classifier must return one label per sentence")
    if any(
        not isinstance(label, str) or label not in {"yes", "no"} for label in labels
    ):
        raise ValueError("classifier returned an invalid relevance label")


def _label_entries(
    row_indices: Sequence[int],
    labels: Sequence[RelevanceLabel],
) -> list[tuple[int, RelevanceLabel]]:
    return list(zip(row_indices, labels, strict=True))


def _classify_pending(
    sentences: Sequence[str],
    row_indices: Sequence[int],
    labels: list[RelevanceLabel],
    checkpoint_path: Path,
    batch_size: int,
    classifier: RelevanceClassifier | None,
    write_payload: PayloadWriter,
) -> None:
    for start in range(len(labels), len(sentences), batch_size):
        batch = sentences[start : start + batch_size]
        if classifier is None:
            raise RuntimeError("classifier is required for unfinished work")
        batch_labels = classifier.classify_many(batch)
        _validate_batch_labels(batch_labels, len(batch))
        labels.extend(batch_labels)
        write_payload(
            checkpoint_path,
            build_label_payload(
                _label_entries(row_indices[: len(labels)], labels),
                complete=False,
            ),
        )


def run_worker(
    input_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    *,
    device: str = "cuda",
    batch_size: int = DEFAULT_BATCH_SIZE,
    classifier: RelevanceClassifier | None = None,
    write_payload: PayloadWriter = _write_payload,
) -> int:
    """Classify a sentence payload and atomically persist resumable labels."""
    if batch_size < 1:
        raise ValueError("batch size must be positive")
    sentence_payload = parse_sentence_payload(input_path.read_bytes())
    sentence_entries = sentence_payload["entries"]
    row_indices = [entry["row_index"] for entry in sentence_entries]
    sentences = [entry["sentence"] for entry in sentence_entries]
    labels, checkpoint_complete = _checkpoint_state(checkpoint_path, row_indices)
    if not checkpoint_complete:
        if classifier is None and len(labels) < len(sentences):
            classifier = load_lfm_classifier(device)
        _classify_pending(
            sentences,
            row_indices,
            labels,
            checkpoint_path,
            batch_size,
            classifier,
            write_payload,
        )
    completed_payload = build_label_payload(
        _label_entries(row_indices, labels),
        complete=True,
    )
    if not checkpoint_complete:
        write_payload(checkpoint_path, completed_payload)
    write_payload(output_path, completed_payload)
    return len(labels)
