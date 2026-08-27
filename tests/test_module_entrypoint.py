import subprocess
import sys

import pytest

from osm_polygon_web_search.__main__ import main


def test_module_entrypoint_prints_the_data_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "osm_polygon_web_search"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == "/Volumes/Seagate M3/projects/osm-polygon-web-search\n"
    assert result.stderr == ""


def test_main_function_prints_the_data_root(capsys) -> None:
    main()

    assert capsys.readouterr().out.splitlines() == [
        "/Volumes/Seagate M3/projects/osm-polygon-web-search"
    ]


def test_main_runs_the_plan_command(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_poc(*args, **kwargs):
        calls.append((args, kwargs))
        return "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc/run.json"

    monkeypatch.setattr("osm_polygon_web_search.__main__.run_poc", fake_run_poc)
    pbf_path = (
        "/Volumes/Seagate M3/projects/osm-polygon-web-search/"
        "liechtenstein-latest.osm.pbf"
    )

    main(
        [
            "--pbf",
            pbf_path,
            "--plan-only",
            "--keyword",
            "geology",
        ]
    )

    assert calls[0][1]["search"] is False
    assert calls[0][1]["keywords"] == ["geology"]
    assert "runs/poc/run.json" in capsys.readouterr().out


def test_main_runs_all_variant_mode(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_poc(*args, **kwargs):
        calls.append((args, kwargs))
        return "/Volumes/Seagate M3/projects/osm-polygon-web-search/runs/poc/run.json"

    monkeypatch.setattr("osm_polygon_web_search.__main__.run_poc", fake_run_poc)

    main(["--all-variants", "--plan-only"])

    assert calls[0][1]["all_variants"] is True
    assert calls[0][1]["search"] is False
    assert "runs/poc/run.json" in capsys.readouterr().out


def test_main_rejects_conflicting_execution_modes() -> None:
    with pytest.raises(SystemExit):
        main(["--plan-only", "--search"])
