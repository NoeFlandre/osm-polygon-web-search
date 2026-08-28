from pathlib import Path

import pytest

import osm_polygon_web_search.sentence_dataset as command


def test_main_transforms_the_validated_input_and_output(monkeypatch, capsys) -> None:
    validated = {
        Path("input.parquet"): Path("/data/input.parquet"),
        Path("output.parquet"): Path("/data/output.parquet"),
    }
    calls = []
    model = object()

    monkeypatch.setattr(command, "ensure_data_path", validated.__getitem__)
    monkeypatch.setattr(command, "load_sat_model", lambda: model)
    monkeypatch.setattr(
        command,
        "transform_parquet",
        lambda input_path, output_path, segmenter: (
            calls.append((input_path, output_path, segmenter)) or 7
        ),
    )

    command.main(["--input", "input.parquet", "--output", "output.parquet"])

    assert calls == [(Path("/data/input.parquet"), Path("/data/output.parquet"), model)]
    assert capsys.readouterr().out == "7 sentence rows written\n"


@pytest.mark.parametrize(
    "arguments", [["--output", "output.parquet"], ["--input", "input.parquet"]]
)
def test_main_requires_both_paths(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        command.main(arguments)


def test_main_help_describes_the_transformation(capsys) -> None:
    with pytest.raises(SystemExit):
        command.main(["--help"])

    assert (
        "Split a Viewer parquet table into SAT sentence rows"
        in capsys.readouterr().out.splitlines()
    )
