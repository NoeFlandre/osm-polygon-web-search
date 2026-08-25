import subprocess
import sys

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
