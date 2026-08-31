import gzip
import json
import shlex
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import osm_polygon_web_search.grid5000 as grid5000
from osm_polygon_web_search.grid5000 import (
    build_job_script,
    build_label_payload,
    build_oarsub_command,
    build_remote_run_id,
    build_sentence_payload,
    is_terminal_oar_state,
    parse_label_payload,
    parse_oar_job_id,
    parse_oar_state,
    parse_sentence_payload,
    validate_label_payload,
    validate_policy_output,
    write_sentence_payload,
)


def _encoded_json(value: object) -> bytes:
    return gzip.compress(json.dumps(value).encode(), mtime=0)


def test_build_sentence_payload_keeps_valid_entries_and_metadata() -> None:
    payload = build_sentence_payload(
        [
            (4, "First sentence."),
            (5, None),
            (6, "  "),
            (7, "Last sentence."),
        ]
    )

    assert parse_sentence_payload(payload) == {
        "schema_version": 1,
        "model_id": "LiquidAI/LFM2.5-2.6B",
        "entries": [
            {"row_index": 4, "sentence": "First sentence."},
            {"row_index": 7, "sentence": "Last sentence."},
        ],
    }


def test_build_sentence_payload_is_deterministic() -> None:
    entries = [(1, "A sentence."), (2, "Une phrase.")]

    assert build_sentence_payload(entries) == build_sentence_payload(entries)


def test_build_sentence_payload_uses_compact_utf8_json() -> None:
    payload = build_sentence_payload([(1, "Une forêt."), (2, "A lake.")])

    encoded = gzip.decompress(payload)
    assert (
        encoded
        == (
            '{"schema_version":1,"model_id":"LiquidAI/LFM2.5-2.6B",'
            '"entries":[{"row_index":1,"sentence":"Une forêt."},'
            '{"row_index":2,"sentence":"A lake."}]}'
        ).encode()
    )


def test_build_sentence_payload_pins_json_encoding_options(monkeypatch) -> None:
    calls = []
    original_dumps = grid5000.json.dumps

    def observe_dumps(value, **kwargs):
        calls.append(kwargs)
        return original_dumps(value, **kwargs)

    monkeypatch.setattr(grid5000.json, "dumps", observe_dumps)

    build_sentence_payload([(1, "Une forêt.")])

    assert calls == [{"ensure_ascii": False, "separators": (",", ":")}]


def test_build_sentence_payload_gzip_header_is_reproducible() -> None:
    payload = build_sentence_payload([(1, "A sentence.")])

    assert payload[4:8] == b"\x00\x00\x00\x00"


def test_parse_sentence_payload_rejects_invalid_label_input() -> None:
    with pytest.raises(ValueError, match="^payload must be a JSON object$"):
        parse_sentence_payload(b"[]")


def test_parse_sentence_payload_rejects_invalid_gzip_json() -> None:
    with pytest.raises(ValueError, match="^payload must be valid gzip JSON$"):
        parse_sentence_payload(b"not-json")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (
            {
                "schema_version": 2,
                "model_id": "LiquidAI/LFM2.5-2.6B",
                "entries": [],
            },
            "unsupported payload schema",
        ),
        (
            {"schema_version": 1, "model_id": "other", "entries": []},
            "unexpected payload model",
        ),
        (
            {
                "schema_version": 1,
                "model_id": "LiquidAI/LFM2.5-2.6B",
                "entries": {},
            },
            "payload entries must be a list",
        ),
    ],
)
def test_parse_sentence_payload_rejects_invalid_metadata(
    value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        parse_sentence_payload(_encoded_json(value))


def test_parse_sentence_payload_rejects_invalid_entry_order_and_content() -> None:
    base = {
        "schema_version": 1,
        "model_id": "LiquidAI/LFM2.5-2.6B",
    }
    with pytest.raises(
        ValueError, match="^payload row index must be a non-negative integer$"
    ):
        parse_sentence_payload(
            _encoded_json({**base, "entries": [{"row_index": -1, "sentence": "A."}]})
        )
    with pytest.raises(
        ValueError, match="^payload sentences must be nonblank strings$"
    ):
        parse_sentence_payload(
            _encoded_json({**base, "entries": [{"row_index": 0, "sentence": "  "}]})
        )
    with pytest.raises(ValueError, match="^payload row indices must be increasing$"):
        parse_sentence_payload(
            _encoded_json(
                {
                    **base,
                    "entries": [
                        {"row_index": 2, "sentence": "A."},
                        {"row_index": 1, "sentence": "B."},
                    ],
                }
            )
        )
    with pytest.raises(ValueError, match="^payload entries must be objects$"):
        parse_sentence_payload(_encoded_json({**base, "entries": ["not-an-entry"]}))
    with pytest.raises(
        ValueError, match="^payload row index must be a non-negative integer$"
    ):
        parse_sentence_payload(
            _encoded_json({**base, "entries": [{"row_index": "0", "sentence": "A."}]})
        )
    with pytest.raises(ValueError, match="^payload row indices must be increasing$"):
        parse_sentence_payload(
            _encoded_json(
                {
                    **base,
                    "entries": [
                        {"row_index": 1, "sentence": "A."},
                        {"row_index": 1, "sentence": "B."},
                    ],
                }
            )
        )


def test_label_payload_round_trip_and_validation() -> None:
    payload = build_label_payload([(2, "yes"), (5, "no")], complete=True)

    parsed = parse_label_payload(payload)

    assert parsed == {
        "schema_version": 1,
        "model_id": "LiquidAI/LFM2.5-2.6B",
        "complete": True,
        "entries": [
            {"row_index": 2, "label": "yes"},
            {"row_index": 5, "label": "no"},
        ],
    }
    assert validate_label_payload(parsed, [2, 5], expected_complete=True) == [
        "yes",
        "no",
    ]


def test_parse_label_payload_rejects_non_object_entries() -> None:
    with pytest.raises(ValueError, match="^label payload entries must be objects$"):
        parse_label_payload(
            _encoded_json(
                {
                    "schema_version": 1,
                    "model_id": "LiquidAI/LFM2.5-2.6B",
                    "complete": False,
                    "entries": ["not-an-entry"],
                }
            )
        )


def test_parse_label_payload_reports_non_list_entries() -> None:
    with pytest.raises(ValueError, match="^label payload entries must be a list$"):
        parse_label_payload(
            _encoded_json(
                {
                    "schema_version": 1,
                    "model_id": "LiquidAI/LFM2.5-2.6B",
                    "complete": False,
                    "entries": {},
                }
            )
        )


def test_parse_label_payload_rejects_non_increasing_indices() -> None:
    with pytest.raises(ValueError, match="^payload row indices must be increasing$"):
        parse_label_payload(
            _encoded_json(
                {
                    "schema_version": 1,
                    "model_id": "LiquidAI/LFM2.5-2.6B",
                    "complete": False,
                    "entries": [
                        {"row_index": 1, "label": "yes"},
                        {"row_index": 1, "label": "no"},
                    ],
                }
            )
        )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (
            {
                "schema_version": 1,
                "model_id": "LiquidAI/LFM2.5-2.6B",
                "complete": "yes",
                "entries": [],
            },
            "label payload complete flag must be boolean",
        ),
        (
            {
                "schema_version": 1,
                "model_id": "LiquidAI/LFM2.5-2.6B",
                "complete": True,
                "entries": [{"row_index": 0, "label": "maybe"}],
            },
            "label payload entries must contain yes or no",
        ),
    ],
)
def test_parse_label_payload_rejects_invalid_values(
    value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        parse_label_payload(_encoded_json(value))


def test_validate_label_payload_rejects_incomplete_or_misaligned_results() -> None:
    payload = parse_label_payload(build_label_payload([(0, "yes")], complete=False))

    with pytest.raises(ValueError, match="^label payload is not complete$"):
        validate_label_payload(payload, [0], expected_complete=True)
    with pytest.raises(
        ValueError, match="^label row indices do not match sentence rows$"
    ):
        validate_label_payload(payload, [1], expected_complete=False)
    complete_payload = parse_label_payload(
        build_label_payload([(0, "yes")], complete=True)
    )
    with pytest.raises(ValueError, match="^checkpoint payload must be partial$"):
        validate_label_payload(complete_payload, [0], expected_complete=False)


def test_remote_job_script_requests_one_gpu_and_quotes_paths() -> None:
    script = build_job_script(
        run_id="lfm-aaaaaaaaaaaa-bbbbbbbbbbbb",
        repository_path=Path("/home/user/repo with space"),
        payload_path=Path("/home/user/input file.json.gz"),
        checkpoint_path=Path("/home/user/checkpoint.json.gz"),
        output_path=Path("/home/user/output.json.gz"),
        walltime="0:30",
    )

    assert "#OAR -l host=1/gpu=1,walltime=0:30" in script
    assert "module load cuda-toolkit/13.0.2" in script
    assert "uv run --no-project --script" in script
    assert shlex.quote("/home/user/repo with space") in script
    assert 'HF_HUB_CACHE="$cache_root/hf-hub"' in script
    assert 'UV_CACHE_DIR="$cache_root/uv"' in script
    assert 'XDG_CACHE_HOME="$cache_root/xdg"' in script
    assert "trap 'rm -rf -- \"$cache_root\"' EXIT" in script
    with pytest.raises(ValueError, match="^invalid remote run identifier$"):
        build_job_script(
            run_id="unsafe",
            repository_path=Path("/home/user/repo"),
            payload_path=Path("/home/user/input.json.gz"),
            checkpoint_path=Path("/home/user/checkpoint.json.gz"),
            output_path=Path("/home/user/output.json.gz"),
        )
    with pytest.raises(ValueError, match="^walltime must be H:MM$"):
        build_job_script(
            run_id="lfm-aaaaaaaaaaaa-bbbbbbbbbbbb",
            repository_path=Path("/home/user/repo"),
            payload_path=Path("/home/user/input.json.gz"),
            checkpoint_path=Path("/home/user/checkpoint.json.gz"),
            output_path=Path("/home/user/output.json.gz"),
            walltime="30m",
        )


def test_remote_job_script_has_an_exact_reproducible_contract() -> None:
    assert build_job_script(
        run_id="lfm-aaaaaaaaaaaa-bbbbbbbbbbbb",
        repository_path=Path("/home/user/repo with space"),
        payload_path=Path("/home/user/input file.json.gz"),
        checkpoint_path=Path("/home/user/checkpoint.json.gz"),
        output_path=Path("/home/user/output.json.gz"),
    ) == (
        "#!/bin/bash -l\n"
        "#OAR -l host=1/gpu=1,walltime=0:30\n"
        "#OAR -n osm-polygon-web-search-lfm\n"
        "set -euo pipefail\n"
        "if [ -f /etc/profile.d/modules.sh ]; then "
        "source /etc/profile.d/modules.sh; fi\n"
        "module load uv/0.10.12\n"
        "module load cuda-toolkit/13.0.2\n"
        'cache_root="/tmp/$USER/osm-polygon-web-search/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb"\n'
        "trap 'rm -rf -- \"$cache_root\"' EXIT\n"
        'export HF_HOME="$cache_root/hf"\n'
        'export HF_HUB_CACHE="$cache_root/hf-hub"\n'
        'export TRANSFORMERS_CACHE="$cache_root/transformers"\n'
        'export TORCH_HOME="$cache_root/torch"\n'
        'export UV_CACHE_DIR="$cache_root/uv"\n'
        'export XDG_CACHE_HOME="$cache_root/xdg"\n'
        "export HF_HUB_DISABLE_TELEMETRY=1\n"
        "export PYTHONUNBUFFERED=1\n"
        "cd '/home/user/repo with space'\n"
        "PYTHONPATH='/home/user/repo with space/src' uv run --no-project --script "
        "'/home/user/repo with space/scripts/grid5000_relevance_worker.py' "
        "--input '/home/user/input file.json.gz' "
        "--checkpoint /home/user/checkpoint.json.gz "
        "--output /home/user/output.json.gz --device cuda\n"
    )


def test_oarsub_command_pins_remote_log_paths() -> None:
    assert build_oarsub_command(
        Path("/home/user/job script.sh"),
        Path("/home/user/stdout.log"),
        Path("/home/user/stderr.log"),
    ) == shlex.join(
        [
            "oarsub",
            "-S",
            "/home/user/job script.sh",
            "-O",
            "/home/user/stdout.log",
            "-E",
            "/home/user/stderr.log",
        ]
    )


def test_remote_run_id_is_stable_and_rejects_unsafe_inputs() -> None:
    assert build_remote_run_id("a" * 64, "b" * 40) == ("lfm-aaaaaaaaaaaa-bbbbbbbbbbbb")
    with pytest.raises(ValueError, match="^hashes must be hexadecimal$"):
        build_remote_run_id("not-a-hash", "b" * 40)
    with pytest.raises(ValueError, match="^hashes must be hexadecimal$"):
        build_remote_run_id("a" * 64, "not-a-commit")


def test_oar_parsers_and_terminal_states(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.run_grid5000_relevance.time.sleep",
        lambda _seconds: pytest.fail("terminal OAR states must not be polled again"),
    )
    assert parse_oar_job_id("OAR_JOB_ID=4321\n") == 4321
    assert parse_oar_state("\nRunning\n") == "Running"
    assert is_terminal_oar_state("Terminated") is True
    assert is_terminal_oar_state("Running") is False
    assert is_terminal_oar_state("Waiting") is False
    assert is_terminal_oar_state("Cancelled") is True
    with pytest.raises(ValueError, match="^could not parse OAR job ID$"):
        parse_oar_job_id("submission failed")
    with pytest.raises(ValueError, match="^unknown OAR state$"):
        parse_oar_state("Unknown")
    with pytest.raises(ValueError, match="^unknown OAR state$"):
        parse_oar_state("")


def test_policy_output_requires_a_successful_unflagged_check() -> None:
    validate_policy_output(0, "No jobs flagged\n")
    with pytest.raises(RuntimeError, match="^usage policy check failed$"):
        validate_policy_output(1, "No jobs flagged\n")
    with pytest.raises(
        RuntimeError, match="^usage policy check did not confirm clean usage$"
    ):
        validate_policy_output(0, "warning\n")


def test_write_sentence_payload_reads_only_the_sentence_column(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "sentences.parquet"
    payload_path = tmp_path / "remote" / "nested" / "input.json.gz"
    pq.write_table(
        pa.table(
            {
                "id": pa.array([1, 2]),
                "sentence": pa.array(["A forest covers the slope.", "  "]),
            }
        ),
        input_path,
    )
    calls = []
    original_read_table = pq.read_table

    def observe_read_table(path, **kwargs):
        calls.append(kwargs)
        return original_read_table(path, **kwargs)

    monkeypatch.setattr("pyarrow.parquet.read_table", observe_read_table)
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000.ensure_data_path", lambda path: path
    )

    assert not payload_path.parent.exists()
    write_sentence_payload(input_path, payload_path)

    assert payload_path.parent.is_dir()
    assert calls == [{"columns": ["sentence"]}]
    assert parse_sentence_payload(payload_path.read_bytes())["entries"] == [
        {"row_index": 0, "sentence": "A forest covers the slope."}
    ]


def test_write_sentence_payload_requires_a_sentence_column(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "input.parquet"
    output_path = tmp_path / "output.json.gz"
    pq.write_table(pa.table({"id": pa.array([1])}), input_path)
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000.ensure_data_path", lambda path: path
    )

    with pytest.raises(KeyError, match="^'sentence'$"):
        write_sentence_payload(input_path, output_path)
