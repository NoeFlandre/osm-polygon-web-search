from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import TypeAlias

from osm_polygon_web_search.data_root import ensure_data_path
from osm_polygon_web_search.grid5000 import (
    DEFAULT_WALLTIME,
    build_job_script,
    build_oarsub_command,
    build_remote_run_id,
    is_terminal_oar_state,
    parse_label_payload,
    parse_oar_job_id,
    parse_oar_state,
    parse_sentence_payload,
    validate_label_payload,
    validate_policy_output,
    write_sentence_payload,
)
from osm_polygon_web_search.llm_relevance import RELEVANCE_MODEL_ID
from osm_polygon_web_search.relevance_dataset import transform_labeled_parquet

DEFAULT_REMOTE_BASE = Path("/home/nflandre/osm-polygon-web-search-grid5000")
CommandRunner: TypeAlias = Callable[[list[str]], CompletedProcess[str]]
SleepFunction: TypeAlias = Callable[[float], None]


@dataclass(frozen=True)
class RunnerConfig:
    input_path: Path
    classified_output_path: Path
    relevant_output_path: Path
    run_dir: Path
    commit_sha: str
    site: str = "nantes"
    remote_base: Path = DEFAULT_REMOTE_BASE
    walltime: str = DEFAULT_WALLTIME
    poll_seconds: int = 15


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    job_id: int
    classified_count: int
    relevant_count: int
    payload_sha256: str
    manifest_path: Path


def run_command(argv: list[str]) -> CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def build_remote_paths(remote_base: Path, run_id: str) -> dict[str, Path]:
    root = remote_base / run_id
    return {
        "root": root,
        "repo": root / "repo",
        "input": root / "input.json.gz",
        "checkpoint": root / "checkpoint.json.gz",
        "output": root / "output.json.gz",
        "job": root / "job.sh",
        "stdout": root / "oar.stdout",
        "stderr": root / "oar.stderr",
    }


def _ssh(site: str, command: str) -> list[str]:
    return ["ssh", site, command]


def _scp_upload(site: str, local_path: Path, remote_path: Path) -> list[str]:
    return ["scp", "-O", str(local_path), f"{site}:{remote_path}"]


def _scp_download(site: str, remote_path: Path, local_path: Path) -> list[str]:
    return ["scp", "-O", f"{site}:{remote_path}", str(local_path)]


def _require_success(result: CompletedProcess[str], action: str) -> None:
    if result.returncode == 0:
        return
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    raise RuntimeError(f"{action} failed{suffix}")


def _remote_root_command(root: Path) -> str:
    quoted_root = shlex.quote(str(root))
    return f"test ! -e {quoted_root} && mkdir -p {quoted_root}"


def _clone_command(repository: Path) -> str:
    return shlex.join(
        (
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            "main",
            "https://github.com/NoeFlandre/osm-polygon-web-search.git",
            str(repository),
        )
    )


def _commit_command(repository: Path) -> str:
    return shlex.join(("git", "-C", str(repository), "rev-parse", "HEAD"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_policy_check(
    site: str,
    command_runner: CommandRunner,
) -> None:
    result = command_runner(_ssh(site, "usagepolicycheck -t"))
    validate_policy_output(result.returncode, result.stdout + result.stderr)


def poll_oar_job(
    site: str,
    job_id: int,
    poll_seconds: int,
    command_runner: CommandRunner,
    sleep: SleepFunction | None = None,
) -> str:
    if poll_seconds < 1:
        raise ValueError("poll interval must be positive")
    pause = sleep if sleep is not None else time.sleep
    status_command = f"oarstat -s -j {job_id}"
    while True:
        result = command_runner(_ssh(site, status_command))
        _require_success(result, "OAR status query")
        state = parse_oar_state(result.stdout)
        if is_terminal_oar_state(state):
            if state != "Terminated":
                raise RuntimeError(f"OAR job ended in {state}")
            return state
        pause(poll_seconds)


def _write_manifest(path: Path, summary: dict[str, object]) -> None:
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _download_logs(
    site: str,
    paths: dict[str, Path],
    run_dir: Path,
    command_runner: CommandRunner,
) -> None:
    for name in ("stdout", "stderr"):
        result = command_runner(
            _scp_download(site, paths[name], run_dir / f"oar.{name}")
        )
        _require_success(result, f"download {name}")


def _materialize_labels(
    input_path: Path,
    payload_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    classified_output_path: Path,
    relevant_output_path: Path,
) -> tuple[int, int]:
    sentence_payload = parse_sentence_payload(payload_path.read_bytes())
    row_indices = [entry["row_index"] for entry in sentence_payload["entries"]]
    output_payload = parse_label_payload(output_path.read_bytes())
    labels = validate_label_payload(
        output_payload,
        row_indices,
        expected_complete=True,
    )
    checkpoint_payload = parse_label_payload(checkpoint_path.read_bytes())
    validate_label_payload(
        checkpoint_payload,
        row_indices,
        expected_complete=True,
    )
    return transform_labeled_parquet(
        input_path,
        classified_output_path,
        relevant_output_path,
        row_indices,
        labels,
    )


def _prepare_local_run(
    config: RunnerConfig,
) -> tuple[Path, Path, str, str, dict[str, Path]]:
    input_path = ensure_data_path(config.input_path)
    run_dir = ensure_data_path(config.run_dir)
    if run_dir.exists():
        raise FileExistsError(f"local run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    payload_path = run_dir / "input.json.gz"
    write_sentence_payload(input_path, payload_path)
    payload_digest = _sha256(payload_path)
    run_id = build_remote_run_id(payload_digest, config.commit_sha)
    remote_paths = build_remote_paths(config.remote_base, run_id)
    job_path = run_dir / "job.sh"
    job_path.write_text(
        build_job_script(
            run_id=run_id,
            repository_path=remote_paths["repo"],
            payload_path=remote_paths["input"],
            checkpoint_path=remote_paths["checkpoint"],
            output_path=remote_paths["output"],
            walltime=config.walltime,
        ),
        encoding="utf-8",
    )
    return input_path, payload_path, payload_digest, run_id, remote_paths


def _stage_remote_run(
    config: RunnerConfig,
    remote_paths: dict[str, Path],
    payload_path: Path,
    job_path: Path,
    command_runner: CommandRunner,
) -> None:

    _run_policy_check(config.site, command_runner)
    _require_success(
        command_runner(_ssh(config.site, _remote_root_command(remote_paths["root"]))),
        "initialize remote run directory",
    )
    _require_success(
        command_runner(_ssh(config.site, _clone_command(remote_paths["repo"]))),
        "clone pushed repository",
    )
    commit_result = command_runner(
        _ssh(config.site, _commit_command(remote_paths["repo"]))
    )
    _require_success(commit_result, "inspect remote repository commit")
    if commit_result.stdout.strip() != config.commit_sha:
        raise RuntimeError("remote repository commit does not match local commit")
    for local_path, remote_name in (
        (payload_path, "input"),
        (job_path, "job"),
    ):
        _require_success(
            command_runner(
                _scp_upload(config.site, local_path, remote_paths[remote_name])
            ),
            f"upload {remote_name}",
        )


def _submit_remote_job(
    config: RunnerConfig,
    remote_paths: dict[str, Path],
    run_dir: Path,
    command_runner: CommandRunner,
) -> int:
    submission = command_runner(
        _ssh(
            config.site,
            build_oarsub_command(
                remote_paths["job"],
                remote_paths["stdout"],
                remote_paths["stderr"],
            ),
        )
    )
    _require_success(submission, "submit OAR job")
    job_id = parse_oar_job_id(submission.stdout)
    (run_dir / "job.id").write_text(f"{job_id}\n", encoding="utf-8")
    return job_id


def _wait_for_remote_job(
    config: RunnerConfig,
    remote_paths: dict[str, Path],
    run_dir: Path,
    job_id: int,
    command_runner: CommandRunner,
    sleep: SleepFunction | None,
) -> None:
    try:
        poll_oar_job(
            config.site,
            job_id,
            config.poll_seconds,
            command_runner,
            sleep,
        )
    except RuntimeError:
        _download_logs(config.site, remote_paths, run_dir, command_runner)
        raise
    _run_policy_check(config.site, command_runner)
    _download_logs(config.site, remote_paths, run_dir, command_runner)


def _retrieve_remote_outputs(
    config: RunnerConfig,
    remote_paths: dict[str, Path],
    run_dir: Path,
    command_runner: CommandRunner,
) -> tuple[Path, Path]:
    checkpoint_path = run_dir / "checkpoint.json.gz"
    output_path = run_dir / "output.json.gz"
    for remote_name, local_path in (
        ("checkpoint", checkpoint_path),
        ("output", output_path),
    ):
        _require_success(
            command_runner(
                _scp_download(config.site, remote_paths[remote_name], local_path)
            ),
            f"download {remote_name}",
        )
    return checkpoint_path, output_path


def _clean_remote_run(
    config: RunnerConfig,
    remote_paths: dict[str, Path],
    command_runner: CommandRunner,
) -> None:
    _require_success(
        command_runner(
            _ssh(
                config.site,
                f"rm -rf -- {shlex.quote(str(remote_paths['root']))}",
            )
        ),
        "clean remote run directory",
    )


def run_pipeline(
    config: RunnerConfig,
    command_runner: CommandRunner = run_command,
    sleep: SleepFunction | None = None,
) -> RunSummary:
    input_path, payload_path, payload_digest, run_id, remote_paths = _prepare_local_run(
        config
    )
    classified_output_path = ensure_data_path(config.classified_output_path)
    relevant_output_path = ensure_data_path(config.relevant_output_path)
    run_dir = payload_path.parent
    job_path = run_dir / "job.sh"
    _stage_remote_run(
        config,
        remote_paths,
        payload_path,
        job_path,
        command_runner,
    )
    job_id = _submit_remote_job(config, remote_paths, run_dir, command_runner)
    _wait_for_remote_job(
        config,
        remote_paths,
        run_dir,
        job_id,
        command_runner,
        sleep,
    )
    checkpoint_path, output_path = _retrieve_remote_outputs(
        config,
        remote_paths,
        run_dir,
        command_runner,
    )
    classified_count, relevant_count = _materialize_labels(
        input_path,
        payload_path,
        checkpoint_path,
        output_path,
        classified_output_path,
        relevant_output_path,
    )
    _clean_remote_run(config, remote_paths, command_runner)
    manifest_path = run_dir / "manifest.json"
    _write_manifest(
        manifest_path,
        {
            "classified_count": classified_count,
            "commit_sha": config.commit_sha,
            "job_id": job_id,
            "model_id": RELEVANCE_MODEL_ID,
            "payload_sha256": payload_digest,
            "relevant_count": relevant_count,
            "run_id": run_id,
            "site": config.site,
            "walltime": config.walltime,
        },
    )
    return RunSummary(
        run_id,
        job_id,
        classified_count,
        relevant_count,
        payload_digest,
        manifest_path,
    )


def _current_commit(command_runner: CommandRunner) -> str:
    result = command_runner(["git", "rev-parse", "HEAD"])
    _require_success(result, "inspect local repository commit")
    commit = result.stdout.strip()
    if not commit:
        raise RuntimeError("local repository commit is empty")
    return commit


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run one bounded Grid'5000 GPU relevance classification job"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--classified-output", type=Path, required=True)
    parser.add_argument("--relevant-output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--site", default="nantes")
    parser.add_argument("--remote-base", type=Path, default=DEFAULT_REMOTE_BASE)
    parser.add_argument("--commit")
    parser.add_argument("--walltime", default=DEFAULT_WALLTIME)
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args(argv)
    input_path = ensure_data_path(args.input)
    command_runner = run_command
    commit_sha = args.commit or _current_commit(command_runner)
    run_dir = args.run_dir or input_path.parent / f"grid5000-{commit_sha[:12]}"
    summary = run_pipeline(
        RunnerConfig(
            input_path=input_path,
            classified_output_path=args.classified_output,
            relevant_output_path=args.relevant_output,
            run_dir=run_dir,
            commit_sha=commit_sha,
            site=args.site,
            remote_base=args.remote_base,
            walltime=args.walltime,
            poll_seconds=args.poll_seconds,
        )
    )
    print(
        f"run_id={summary.run_id} job_id={summary.job_id} "
        f"classified={summary.classified_count} relevant={summary.relevant_count} "
        f"manifest={summary.manifest_path}"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
