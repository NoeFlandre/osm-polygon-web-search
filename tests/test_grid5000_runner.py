from pathlib import Path
from subprocess import CompletedProcess

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from osm_polygon_web_search.grid5000 import build_label_payload, parse_sentence_payload
from scripts.run_grid5000_relevance import (
    RunnerConfig,
    build_remote_paths,
    poll_oar_job,
    run_pipeline,
)


class FakeRemote:
    def __init__(self, commit_sha: str) -> None:
        self.commit_sha = commit_sha
        self.commands: list[list[str]] = []
        self.statuses = iter(["Running\n", "Terminated\n"])

    def __call__(self, argv: list[str]) -> CompletedProcess[str]:
        self.commands.append(argv)
        if argv[0] == "ssh":
            return self._ssh_result(argv)
        if argv[0] == "scp":
            return self._scp_result(argv)
        return CompletedProcess(argv, 0, "", "")

    def _ssh_result(self, argv: list[str]) -> CompletedProcess[str]:
        command = argv[2]
        if command == "usagepolicycheck -t":
            return CompletedProcess(argv, 0, "No jobs flagged\n", "")
        if command.startswith("git -C"):
            return CompletedProcess(argv, 0, self.commit_sha + "\n", "")
        if command.startswith("oarsub"):
            return CompletedProcess(argv, 0, "OAR_JOB_ID=4321\n", "")
        if command.startswith("oarstat"):
            return CompletedProcess(argv, 0, next(self.statuses), "")
        return CompletedProcess(argv, 0, "", "")

    def _scp_result(self, argv: list[str]) -> CompletedProcess[str]:
        if argv[2].startswith("nantes:"):
            destination = Path(argv[3])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.name in {"checkpoint.json.gz", "output.json.gz"}:
                destination.write_bytes(
                    build_label_payload([(0, "yes"), (1, "no")], complete=True)
                )
            else:
                destination.write_text("log\n", encoding="utf-8")
        return CompletedProcess(argv, 0, "", "")


def test_build_remote_paths_keeps_one_run_under_the_remote_base() -> None:
    paths = build_remote_paths(
        Path("/home/nflandre/grid5000"),
        "lfm-aaaaaaaaaaaa-bbbbbbbbbbbb",
    )

    assert paths == {
        "root": Path("/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb"),
        "repo": Path("/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/repo"),
        "input": Path(
            "/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/input.json.gz"
        ),
        "checkpoint": Path(
            "/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/checkpoint.json.gz"
        ),
        "output": Path(
            "/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/output.json.gz"
        ),
        "job": Path("/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/job.sh"),
        "stdout": Path(
            "/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/oar.stdout"
        ),
        "stderr": Path(
            "/home/nflandre/grid5000/lfm-aaaaaaaaaaaa-bbbbbbbbbbbb/oar.stderr"
        ),
    }


def test_poll_oar_job_waits_for_termination(
    monkeypatch,
) -> None:
    states = iter(["Running\n", "Terminated\n"])
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def fake_run(argv: list[str]) -> CompletedProcess[str]:
        calls.append(argv)
        return CompletedProcess(argv, 0, next(states), "")

    monkeypatch.setattr("scripts.run_grid5000_relevance.time.sleep", sleeps.append)

    state = poll_oar_job("nantes", 4321, 3, fake_run)

    assert state == "Terminated"
    assert calls == [
        ["ssh", "nantes", "oarstat -s -j 4321"],
        ["ssh", "nantes", "oarstat -s -j 4321"],
    ]
    assert sleeps == [3]


def test_poll_oar_job_fails_on_terminal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.run_grid5000_relevance.time.sleep",
        lambda _seconds: pytest.fail("terminal OAR states must not be polled again"),
    )

    def fake_run(argv: list[str]) -> CompletedProcess[str]:
        return CompletedProcess(argv, 0, "Error\n", "")

    with pytest.raises(RuntimeError, match="^OAR job ended in Error$"):
        poll_oar_job("nantes", 4321, 3, fake_run)


def test_run_pipeline_completes_the_frontend_transport_contract(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "sentences.parquet"
    classified_path = tmp_path / "classified.parquet"
    relevant_path = tmp_path / "relevant.parquet"
    run_dir = tmp_path / "run"
    pq.write_table(
        pa.table(
            {
                "id": pa.array([1, 2]),
                "sentence": pa.array(
                    ["A forest covers the slope.", "A road crosses it."]
                ),
            }
        ),
        input_path,
    )
    monkeypatch.setattr(
        "scripts.run_grid5000_relevance.ensure_data_path", lambda path: path
    )
    monkeypatch.setattr(
        "osm_polygon_web_search.grid5000.ensure_data_path", lambda path: path
    )
    commit_sha = "b" * 40
    remote = FakeRemote(commit_sha)

    summary = run_pipeline(
        RunnerConfig(
            input_path=input_path,
            classified_output_path=classified_path,
            relevant_output_path=relevant_path,
            run_dir=run_dir,
            commit_sha=commit_sha,
        ),
        command_runner=remote,
        sleep=lambda _seconds: None,
    )

    assert summary.job_id == 4321
    assert pq.read_table(relevant_path).to_pylist()[0]["id"] == 1
    assert parse_sentence_payload((run_dir / "input.json.gz").read_bytes())["entries"]
    assert any(
        command[0] == "ssh" and command[2].startswith("rm -rf --")
        for command in remote.commands
    )
