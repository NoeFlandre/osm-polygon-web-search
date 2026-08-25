from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_root_license_is_apache_2() -> None:
    text = (ROOT / "LICENSE").read_text()
    assert "Apache License, Version 2.0" in text


def test_citation_declares_apache_license_and_repository() -> None:
    text = (ROOT / "CITATION.cff").read_text()
    assert "license: Apache-2.0" in text
    assert "osm-polygon-web-search" in text


def test_dataset_card_is_metadata_only_and_apache_licensed() -> None:
    text = (ROOT / "dataset" / "README.md").read_text()
    assert "license: apache-2.0" in text
    assert "No data files are published" in text


def test_mkdocs_config_has_explicit_navigation_and_internal_exclusion() -> None:
    text = (ROOT / "mkdocs.yml").read_text()
    assert "theme:" in text
    assert "nav:" in text
    assert "superpowers/" in text


def test_public_docs_state_the_seagate_only_policy() -> None:
    text = (ROOT / "docs" / "data-layout.md").read_text()
    assert "/Volumes/Seagate M3/projects/osm-polygon-web-search" in text
    assert "never uploaded" in text
