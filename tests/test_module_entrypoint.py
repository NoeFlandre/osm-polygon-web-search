import subprocess
import sys
from pathlib import Path

import pytest

from osm_polygon_web_search.__main__ import main
from osm_polygon_web_search.data_root import data_root
from osm_polygon_web_search.pipeline import DEFAULT_KEYWORDS, DEFAULT_PBF


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


def test_main_forwards_all_cli_options(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_poc(*args, **kwargs):
        calls.append((args, kwargs))
        return "/tmp/run.json"

    monkeypatch.setattr("osm_polygon_web_search.__main__.run_poc", fake_run_poc)

    main(
        [
            "--pbf",
            "/tmp/custom.osm.pbf",
            "--output-dir",
            "/tmp/output",
            "--keyword",
            "land cover",
            "--keyword",
            "terrain",
            "--results",
            "9",
            "--search",
            "--all-variants",
        ]
    )

    assert calls == [
        (
            (Path("/tmp/custom.osm.pbf"),),
            {
                "output_dir": Path("/tmp/output"),
                "keywords": ["land cover", "terrain"],
                "search": True,
                "result_count": 9,
                "all_variants": True,
            },
        )
    ]
    assert capsys.readouterr().out.splitlines() == ["/tmp/run.json"]


def test_main_uses_stable_cli_defaults(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_poc(*args, **kwargs):
        calls.append((args, kwargs))
        return "/tmp/run.json"

    monkeypatch.setattr("osm_polygon_web_search.__main__.run_poc", fake_run_poc)

    main(["--plan-only"])

    assert calls == [
        (
            (DEFAULT_PBF,),
            {
                "output_dir": data_root() / "runs" / "poc",
                "keywords": DEFAULT_KEYWORDS,
                "search": False,
                "result_count": 10,
                "all_variants": False,
            },
        )
    ]
    assert capsys.readouterr().out.splitlines() == ["/tmp/run.json"]


def test_main_help_describes_the_command(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])

    assert error.value.code == 0
    assert "Run the OSM polygon web-search POC\n" in capsys.readouterr().out


def test_main_reports_the_execution_mode_conflict(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--plan-only", "--search"])

    assert (
        "error: --plan-only and --search are mutually exclusive\n"
        in capsys.readouterr().err
    )
