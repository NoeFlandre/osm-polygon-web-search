from __future__ import annotations

import gzip
import io
import json
import re
import shlex
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TypedDict

from .data_root import ensure_data_path
from .llm_relevance import RELEVANCE_MODEL_ID, RelevanceLabel

PAYLOAD_SCHEMA_VERSION = 1
DEFAULT_WALLTIME = "0:30"
_OAR_STATES = frozenset(
    {
        "Waiting",
        "Launching",
        "Running",
        "Suspended",
        "Finishing",
        "Terminated",
        "Error",
        "Killed",
        "Cancelled",
    }
)
_OAR_TERMINAL_STATES = frozenset({"Terminated", "Error", "Killed", "Cancelled"})


class SentencePayloadEntry(TypedDict):
    row_index: int
    sentence: str


class SentencePayload(TypedDict):
    schema_version: int
    model_id: str
    entries: list[SentencePayloadEntry]


class LabelPayloadEntry(TypedDict):
    row_index: int
    label: RelevanceLabel


class LabelPayload(TypedDict):
    schema_version: int
    model_id: str
    complete: bool
    entries: list[LabelPayloadEntry]


def _gzip_json(payload: Mapping[str, object]) -> bytes:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
        compressed.write(encoded)
    return output.getvalue()


def _read_json(data: bytes) -> object:
    try:
        return json.loads(gzip.decompress(data))
    except (EOFError, OSError):
        try:
            return json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("payload must be valid gzip JSON") from error


def _payload_dict(data: bytes) -> dict[str, object]:
    payload = _read_json(data)
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def _validate_payload_header(payload: Mapping[str, object]) -> None:
    if payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
        raise ValueError("unsupported payload schema")
    if payload.get("model_id") != RELEVANCE_MODEL_ID:
        raise ValueError("unexpected payload model")


def _payload_entries(payload: Mapping[str, object], error_message: str) -> list[object]:
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(error_message)
    return entries


def _parse_row_index(entry: Mapping[str, object], previous: int | None) -> int:
    row_index = entry.get("row_index")
    if type(row_index) is not int or row_index < 0:
        raise ValueError("payload row index must be a non-negative integer")
    if previous is not None and row_index <= previous:
        raise ValueError("payload row indices must be increasing")
    return row_index


def build_sentence_payload(values: Iterable[tuple[int, object]]) -> bytes:
    entries: list[SentencePayloadEntry] = []
    for row_index, value in values:
        if not isinstance(value, str):
            continue
        if not value.strip():
            continue
        entries.append({"row_index": row_index, "sentence": value})
    payload: SentencePayload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "model_id": RELEVANCE_MODEL_ID,
        "entries": entries,
    }
    return _gzip_json(payload)


def parse_sentence_payload(data: bytes) -> SentencePayload:
    payload = _payload_dict(data)
    _validate_payload_header(payload)
    raw_entries = _payload_entries(payload, "payload entries must be a list")
    entries: list[SentencePayloadEntry] = []
    previous: int | None = None
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("payload entries must be objects")
        entry = raw_entry
        row_index = _parse_row_index(entry, previous)
        sentence = entry.get("sentence")
        if not isinstance(sentence, str) or not sentence.strip():
            raise ValueError("payload sentences must be nonblank strings")
        entries.append({"row_index": row_index, "sentence": sentence})
        previous = row_index
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "model_id": RELEVANCE_MODEL_ID,
        "entries": entries,
    }


def build_label_payload(
    entries: Iterable[tuple[int, RelevanceLabel]],
    *,
    complete: bool,
) -> bytes:
    payload: LabelPayload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "model_id": RELEVANCE_MODEL_ID,
        "complete": complete,
        "entries": [
            {"row_index": row_index, "label": label} for row_index, label in entries
        ],
    }
    return _gzip_json(payload)


def parse_label_payload(data: bytes) -> LabelPayload:
    payload = _payload_dict(data)
    _validate_payload_header(payload)
    complete = payload.get("complete")
    if type(complete) is not bool:
        raise ValueError("label payload complete flag must be boolean")
    raw_entries = _payload_entries(
        payload,
        "label payload entries must be a list",
    )
    entries: list[LabelPayloadEntry] = []
    previous: int | None = None
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("label payload entries must be objects")
        entry = raw_entry
        row_index = _parse_row_index(entry, previous)
        label = entry.get("label")
        if not isinstance(label, str) or label not in {"yes", "no"}:
            raise ValueError("label payload entries must contain yes or no")
        entries.append({"row_index": row_index, "label": label})
        previous = row_index
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "model_id": RELEVANCE_MODEL_ID,
        "complete": complete,
        "entries": entries,
    }


def validate_label_payload(
    payload: LabelPayload,
    expected_row_indices: Sequence[int],
    *,
    expected_complete: bool,
) -> list[RelevanceLabel]:
    if payload["complete"] != expected_complete:
        if expected_complete:
            raise ValueError("label payload is not complete")
        raise ValueError("checkpoint payload must be partial")
    actual_row_indices = [entry["row_index"] for entry in payload["entries"]]
    if actual_row_indices != list(expected_row_indices):
        raise ValueError("label row indices do not match sentence rows")
    return [entry["label"] for entry in payload["entries"]]


def _validate_run_id(run_id: str) -> None:
    if re.fullmatch(r"lfm-[0-9a-f]{12}-[0-9a-f]{12}", run_id) is None:
        raise ValueError("invalid remote run identifier")


def build_remote_run_id(payload_digest: str, commit_sha: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", payload_digest) is None:
        raise ValueError("hashes must be hexadecimal")
    if re.fullmatch(r"[0-9a-f]{40,64}", commit_sha) is None:
        raise ValueError("hashes must be hexadecimal")
    return f"lfm-{payload_digest[:12]}-{commit_sha[:12]}"


def _validate_walltime(walltime: str) -> None:
    if re.fullmatch(r"[0-9]+:[0-5][0-9]", walltime) is None:
        raise ValueError("walltime must be H:MM")


def build_job_script(
    *,
    run_id: str,
    repository_path: Path,
    payload_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    walltime: str = DEFAULT_WALLTIME,
) -> str:
    _validate_run_id(run_id)
    _validate_walltime(walltime)
    repository = shlex.quote(str(repository_path))
    source_path = shlex.quote(str(repository_path / "src"))
    worker_path = shlex.quote(
        str(repository_path / "scripts" / "grid5000_relevance_worker.py")
    )
    payload = shlex.quote(str(payload_path))
    checkpoint = shlex.quote(str(checkpoint_path))
    output = shlex.quote(str(output_path))
    return (
        "\n".join(
            [
                "#!/bin/bash -l",
                f"#OAR -l host=1/gpu=1,walltime={walltime}",
                "#OAR -n osm-polygon-web-search-lfm",
                "set -euo pipefail",
                "if [ -f /etc/profile.d/modules.sh ]; then "
                "source /etc/profile.d/modules.sh; fi",
                "module load uv/0.10.12",
                "module load cuda-toolkit/13.0.2",
                f'cache_root="/tmp/$USER/osm-polygon-web-search/{run_id}"',
                "trap 'rm -rf -- \"$cache_root\"' EXIT",
                'export HF_HOME="$cache_root/hf"',
                'export HF_HUB_CACHE="$cache_root/hf-hub"',
                'export TRANSFORMERS_CACHE="$cache_root/transformers"',
                'export TORCH_HOME="$cache_root/torch"',
                'export UV_CACHE_DIR="$cache_root/uv"',
                'export XDG_CACHE_HOME="$cache_root/xdg"',
                "export HF_HUB_DISABLE_TELEMETRY=1",
                "export PYTHONUNBUFFERED=1",
                f"cd {repository}",
                f"PYTHONPATH={source_path} uv run --no-project --script {worker_path} "
                f"--input {payload} --checkpoint {checkpoint} "
                f"--output {output} --device cuda",
            ]
        )
        + "\n"
    )


def build_oarsub_command(
    script_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> str:
    return shlex.join(
        (
            "oarsub",
            "-S",
            str(script_path),
            "-O",
            str(stdout_path),
            "-E",
            str(stderr_path),
        )
    )


def parse_oar_job_id(output: str) -> int:
    for line in output.splitlines():
        match = re.fullmatch(r"\s*OAR_JOB_ID=(\d+)\s*", line)
        if match is not None:
            return int(match.group(1))
    raise ValueError("could not parse OAR job ID")


def parse_oar_state(output: str) -> str:
    nonempty_lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not nonempty_lines:
        raise ValueError("unknown OAR state")
    state = nonempty_lines[-1]
    if state not in _OAR_STATES:
        raise ValueError("unknown OAR state")
    return state


def is_terminal_oar_state(state: str) -> bool:
    return state in _OAR_TERMINAL_STATES


def validate_policy_output(returncode: int, output: str) -> None:
    if returncode != 0:
        raise RuntimeError("usage policy check failed")
    if "No jobs flagged" not in output:
        raise RuntimeError("usage policy check did not confirm clean usage")


def write_sentence_payload(input_path: Path, output_path: Path) -> None:
    import pyarrow.parquet as pq

    source_path = ensure_data_path(input_path)
    destination = ensure_data_path(output_path)
    parquet_file = pq.ParquetFile(source_path)
    if "sentence" not in parquet_file.schema.names:
        raise KeyError("sentence")
    source = pq.read_table(source_path, columns=["sentence"])
    payload = build_sentence_payload(enumerate(source["sentence"].to_pylist()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
