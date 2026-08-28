from pathlib import Path

import pytest

import osm_polygon_web_search.relevance_dataset as command


def test_main_validates_paths_loads_model_and_reports_counts(
    monkeypatch, capsys
) -> None:
    validated = {
        Path("input.parquet"): Path("/data/input.parquet"),
        Path("classified.parquet"): Path("/data/classified.parquet"),
        Path("relevant.parquet"): Path("/data/relevant.parquet"),
    }
    calls = []
    model = object()

    monkeypatch.setattr(command, "ensure_data_path", validated.__getitem__)
    monkeypatch.setattr(command, "load_lfm_classifier", lambda: model)
    monkeypatch.setattr(
        command,
        "transform_parquet",
        lambda input_path, classified_path, relevant_path, classifier: (
            calls.append((input_path, classified_path, relevant_path, classifier))
            or (8, 3)
        ),
    )

    command.main(
        [
            "--input",
            "input.parquet",
            "--classified-output",
            "classified.parquet",
            "--relevant-output",
            "relevant.parquet",
        ]
    )

    assert calls == [
        (
            Path("/data/input.parquet"),
            Path("/data/classified.parquet"),
            Path("/data/relevant.parquet"),
            model,
        )
    ]
    assert capsys.readouterr().out == "classified=8 relevant=3\n"


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "--classified-output",
            "classified.parquet",
            "--relevant-output",
            "relevant.parquet",
        ],
        ["--input", "input.parquet", "--relevant-output", "relevant.parquet"],
        ["--input", "input.parquet", "--classified-output", "classified.parquet"],
    ],
)
def test_main_requires_all_paths(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        command.main(arguments)


def test_main_help_describes_local_classification(capsys) -> None:
    with pytest.raises(SystemExit):
        command.main(["--help"])

    assert (
        "Classify SAT sentence rows with the local LFM relevance model"
        in capsys.readouterr().out.splitlines()
    )
