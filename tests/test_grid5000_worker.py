from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from osm_polygon_web_search.grid5000 import (
    build_label_payload,
    build_sentence_payload,
    parse_label_payload,
)
from osm_polygon_web_search.grid5000_worker import (
    _label_entries,
    _write_payload,
    run_worker,
)
from osm_polygon_web_search.llm_relevance import RelevanceLabel


@pytest.fixture(autouse=True)
def _prevent_model_loading_in_unit_tests(monkeypatch) -> None:
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000_worker.load_lfm_classifier",
        lambda device: pytest.fail(f"unexpected model load on {device}"),
    )


class FakeClassifier:
    def __init__(self, labels: dict[str, RelevanceLabel]) -> None:
        self.labels = labels
        self.calls: list[list[str]] = []

    def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
        batch = list(sentences)
        self.calls.append(batch)
        return [self.labels[sentence] for sentence in batch]


def _write_input(path: Path, entries: list[tuple[int, str]]) -> None:
    path.write_bytes(build_sentence_payload(entries))


def test_worker_classifies_in_batches_and_completes_checkpoint(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "nested" / "checkpoint.json.gz"
    output_path = tmp_path / "nested" / "output.json.gz"
    entries = [(4, "A forest."), (8, "A road."), (12, "A lake.")]
    _write_input(input_path, entries)
    classifier = FakeClassifier({"A forest.": "yes", "A road.": "no", "A lake.": "yes"})

    writes: list[tuple[Path, bool]] = []

    def observe_write(path: Path, payload: bytes) -> None:
        writes.append((path, parse_label_payload(payload)["complete"]))
        _write_payload(path, payload)

    result = run_worker(
        input_path,
        checkpoint_path,
        output_path,
        device="cuda",
        batch_size=2,
        classifier=classifier,
        write_payload=observe_write,
    )

    assert result == 3
    assert classifier.calls == [["A forest.", "A road."], ["A lake."]]
    assert writes == [
        (checkpoint_path, False),
        (checkpoint_path, False),
        (checkpoint_path, True),
        (output_path, True),
    ]
    assert parse_label_payload(output_path.read_bytes())["entries"] == [
        {"row_index": 4, "label": "yes"},
        {"row_index": 8, "label": "no"},
        {"row_index": 12, "label": "yes"},
    ]


def test_write_payload_creates_all_missing_parent_directories(tmp_path: Path) -> None:
    output_path = tmp_path / "one" / "two" / "payload.bin"

    assert not output_path.parent.exists()
    _write_payload(output_path, b"payload")

    assert output_path.read_bytes() == b"payload"


def test_worker_resumes_from_a_partial_checkpoint(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(1, "First."), (3, "Second."), (7, "Third.")])
    checkpoint_path.write_bytes(build_label_payload([(1, "yes")], complete=False))
    classifier = FakeClassifier({"Second.": "no", "Third.": "yes"})

    assert (
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            batch_size=2,
            classifier=classifier,
        )
        == 3
    )

    assert classifier.calls == [["Second.", "Third."]]
    assert parse_label_payload(output_path.read_bytes())["complete"] is True


def test_worker_uses_cuda_loader_when_no_classifier_is_supplied(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "A sentence.")])
    classifier = FakeClassifier({"A sentence.": "no"})
    devices: list[str] = []

    def load(device: str):
        devices.append(device)
        return classifier

    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000_worker.load_lfm_classifier", load
    )

    run_worker(input_path, checkpoint_path, output_path)

    assert devices == ["cuda"]
    assert classifier.calls == [["A sentence."]]


def test_worker_rejects_a_checkpoint_that_is_not_a_prefix(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(1, "First."), (3, "Second.")])
    checkpoint_path.write_bytes(build_label_payload([(3, "yes")], complete=False))

    with pytest.raises(
        ValueError, match="^label row indices do not match sentence rows$"
    ):
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            classifier=FakeClassifier({}),
        )


def test_worker_rejects_a_classifier_batch_with_wrong_length(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First."), (1, "Second.")])

    class ShortClassifier:
        def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
            del sentences
            return ["yes"]

    with pytest.raises(
        ValueError, match="^classifier must return one label per sentence$"
    ):
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            classifier=ShortClassifier(),
        )


def test_worker_rejects_invalid_classifier_labels(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First.")])

    class InvalidClassifier:
        def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
            del sentences
            return cast(list[RelevanceLabel], ["maybe"])

    with pytest.raises(
        ValueError, match="^classifier returned an invalid relevance label$"
    ):
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            classifier=InvalidClassifier(),
        )


def test_worker_rejects_a_nonpositive_batch_size(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [])

    with pytest.raises(ValueError, match="^batch size must be positive$"):
        run_worker(input_path, checkpoint_path, output_path, batch_size=0)


def test_worker_accepts_a_batch_size_of_one(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First."), (1, "Second.")])
    classifier = FakeClassifier({"First.": "yes", "Second.": "no"})

    assert (
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            batch_size=1,
            classifier=classifier,
        )
        == 2
    )
    assert classifier.calls == [["First."], ["Second."]]


def test_label_entries_requires_equal_lengths() -> None:
    with pytest.raises(
        ValueError, match=r"^zip\(\) argument 2 is shorter than argument 1$"
    ):
        _label_entries([0, 1], ["yes"])


def test_worker_does_not_load_a_model_when_an_empty_payload_is_pending(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [])
    loaded: list[str] = []
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000_worker.load_lfm_classifier",
        lambda device: loaded.append(device),
    )

    assert run_worker(input_path, checkpoint_path, output_path) == 0
    assert loaded == []


def test_worker_does_not_replace_a_supplied_classifier(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First.")])
    classifier = FakeClassifier({"First.": "yes"})
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000_worker.load_lfm_classifier",
        lambda device: pytest.fail(f"unexpected model load on {device}"),
    )

    assert (
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            classifier=classifier,
        )
        == 1
    )


def test_worker_fails_if_the_loader_returns_no_classifier(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First.")])
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000_worker.load_lfm_classifier",
        lambda device: None,
    )

    with pytest.raises(
        RuntimeError, match="^classifier is required for unfinished work$"
    ):
        run_worker(input_path, checkpoint_path, output_path)


def test_worker_reuses_a_complete_checkpoint_without_loading_model(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First."), (2, "Second.")])
    checkpoint_path.write_bytes(
        build_label_payload([(0, "yes"), (2, "no")], complete=True)
    )

    class NeverClassifier:
        def classify_many(self, sentences: Sequence[str]) -> list[RelevanceLabel]:
            del sentences
            pytest.fail("a complete checkpoint must not classify")

    assert (
        run_worker(
            input_path,
            checkpoint_path,
            output_path,
            classifier=NeverClassifier(),
        )
        == 2
    )
    assert parse_label_payload(output_path.read_bytes())["complete"] is True


def test_worker_reuses_a_complete_checkpoint_without_a_classifier(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.json.gz"
    checkpoint_path = tmp_path / "checkpoint.json.gz"
    output_path = tmp_path / "output.json.gz"
    _write_input(input_path, [(0, "First."), (2, "Second.")])
    checkpoint_path.write_bytes(
        build_label_payload([(0, "yes"), (2, "no")], complete=True)
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000_worker.load_lfm_classifier",
        lambda device: pytest.fail(f"a complete checkpoint must not load on {device}"),
    )

    assert run_worker(input_path, checkpoint_path, output_path) == 2
    assert parse_label_payload(output_path.read_bytes())["complete"] is True
