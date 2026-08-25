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


def test_public_docs_describe_the_approved_pbf_search_poc() -> None:
    combined = "\n".join(
        (ROOT / relative).read_text()
        for relative in (
            "README.md",
            "docs/index.md",
            "docs/getting-started.md",
            "docs/data-layout.md",
            "dataset/README.md",
        )
    )
    for required in (
        "PBF-first",
        "Liechtenstein",
        "Trafilatura",
        "BRAVE_SEARCH_API_KEY",
        "raw web content is not published",
    ):
        assert required in combined


def test_dockerfile_runs_the_module_smoke_command() -> None:
    text = (ROOT / "Dockerfile").read_text()
    assert "uv sync --frozen --no-dev" in text
    assert (
        'CMD ["uv", "run", "--no-dev", "python", "-m", "osm_polygon_web_search"]'
    ) in text


def test_ci_workflow_runs_the_complete_quality_surface() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for command in (
        "ruff format --check .",
        "ruff check .",
        "ty check",
        "pytest",
        "mkdocs build --strict",
        "mutmut run",
        "docker build",
    ):
        assert command in text


def test_docs_workflow_builds_and_deploys_pages() -> None:
    text = (ROOT / ".github" / "workflows" / "docs.yml").read_text()
    assert "pages: write" in text
    assert "id-token: write" in text
    assert "mkdocs build --strict" in text
    assert "upload-pages-artifact" in text
    assert "deploy-pages" in text
