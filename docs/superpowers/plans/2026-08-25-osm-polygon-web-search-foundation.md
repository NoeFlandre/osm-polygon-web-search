# OSM Polygon Web Search Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish a minimal, Apache-2.0-licensed Python repository and metadata-only Hugging Face dataset named `osm-polygon-web-search`, while keeping all data on the Seagate volume.

**Architecture:** A three-file package exposes one side-effect-free `data_root() -> Path` boundary and a module entry point used for a Docker smoke command. Repository infrastructure provides uv locking, Ruff, ty, pytest/coverage, pre-commit, mutmut, strict MkDocs, Docker, and GitHub Actions; the Hugging Face surface contains only a dataset card and license.

**Tech Stack:** Python 3.11+, uv, pytest, pytest-cov, Ruff, ty, mutmut, pre-commit, MkDocs Material, Docker, GitHub Actions, GitHub CLI, Hugging Face CLI, Apache-2.0.

---

## File map

The implementation creates these focused units:

- `pyproject.toml`: package metadata and tool configuration.
- `uv.lock`: generated, committed environment lockfile.
- `src/osm_polygon_web_search/data_root.py`: canonical Seagate path and pure accessor.
- `src/osm_polygon_web_search/__init__.py`: public exports and version.
- `src/osm_polygon_web_search/__main__.py`: one-line executable smoke command.
- `tests/test_data_root.py`: exact path and side-effect contract.
- `tests/test_module_entrypoint.py`: module output contract.
- `tests/test_repository_contracts.py`: legal, docs, workflow, and dataset-card contracts.
- `README.md`: code repository landing page.
- `docs/`: public MkDocs pages.
- `dataset/README.md`: Hugging Face dataset card, with no data files.
- `LICENSE`: Apache License 2.0 text.
- `CITATION.cff`: citation metadata.
- `mkdocs.yml`: strict documentation navigation and Pages metadata.
- `Dockerfile`, `.dockerignore`: reproducible image and bounded build context.
- `.github/workflows/ci.yml`: quality and Docker workflow.
- `.github/workflows/docs.yml`: strict Pages build/deployment workflow.
- `.gitignore`, `.pre-commit-config.yaml`, `justfile`: local hygiene and repeatable commands.

The existing approved specification at `docs/superpowers/specs/2026-08-25-osm-polygon-web-search-foundation-design.md` remains internal and is excluded from the published MkDocs site.

### Task 1: Add project metadata and local quality commands

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.dockerignore`
- Create: `.pre-commit-config.yaml`
- Create: `justfile`
- Generate: `uv.lock`

- [ ] **Step 1: Add package metadata without production modules**

Create `pyproject.toml` with this structure:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "osm-polygon-web-search"
version = "0.1.0"
description = "A Seagate-only foundation for OSM polygon web-search data work."
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }
authors = [{ name = "Noe Flandre" }]
dependencies = []

[project.scripts]
osm-polygon-web-search = "osm_polygon_web_search.__main__:main"

[dependency-groups]
dev = [
  "mkdocs-material>=9.6.0",
  "mutmut>=3.3.0",
  "pre-commit>=4.1.0",
  "pytest>=8.3.0",
  "pytest-cov>=6.0.0",
  "ruff>=0.15.0",
  "ty>=0.0.1",
]

[tool.uv]
default-groups = ["dev"]

[tool.hatch.build.targets.wheel]
packages = ["src/osm_polygon_web_search"]

[tool.pytest.ini_options]
addopts = ["--strict-config", "--strict-markers"]
testpaths = ["tests"]

[tool.coverage.run]
branch = true
source = ["osm_polygon_web_search"]

[tool.coverage.report]
fail_under = 100
show_missing = true

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["B", "C4", "E", "F", "I", "SIM", "UP"]

[tool.ruff.format]
quote-style = "double"

[tool.ty.environment]
python-version = "3.11"

[tool.mutmut]
paths_to_mutate = ["src/osm_polygon_web_search/"]
pytest_add_cli_args = ["-q"]
```

- [ ] **Step 2: Add ignore rules that cannot reach the Seagate data root**

Use `.gitignore` for `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.ty/`, `.coverage`, `htmlcov/`, `site/`, `.mutmut-cache/`, `mutants/`, `dist/`, `*.egg-info/`, and `.DS_Store`. Do not add the Seagate path as a repository-relative pattern because it is outside the checkout and must never be accessed by repository tooling.

Use `.dockerignore` for `.git/`, `.venv/`, caches, coverage output, mutation output, `site/`, `dist/`, and `tests/`. The build context must contain source and legal metadata only.

- [ ] **Step 3: Add local hooks and a single quality command surface**

Create `.pre-commit-config.yaml` with local system hooks that run the locked project tools without downloading a second environment:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format --check .
        language: system
        pass_filenames: false
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check .
        language: system
        pass_filenames: false
      - id: ty
        name: ty check
        entry: uv run ty check
        language: system
        pass_filenames: false
```

Create `justfile` recipes named `format`, `lint`, `type`, `test`, `docs`, `mutation`, `docker`, and `check`. Each recipe must call the exact `uv run` command documented in the design; `check` runs format, lint, type, test, and docs in that order. Mutation and Docker remain explicit separate recipes so they cannot be mistaken for a completed run when either is interrupted.

- [ ] **Step 4: Resolve and lock the environment**

Run:

```sh
uv lock
uv sync --frozen
```

Expected: `uv.lock` is created and the environment installs without source-package import errors. No command may reference or create anything beneath `/Volumes/Seagate M3/projects/osm-polygon-web-search`.

- [ ] **Step 5: Inspect and commit the configuration-only change**

Run `git diff --check` and `git status --short`, then commit only the files from this task:

```sh
git add pyproject.toml .gitignore .dockerignore .pre-commit-config.yaml justfile uv.lock
git commit -m "build: add uv quality tooling"
```

### Task 2: Drive the data-root boundary with RED tests

**Files:**
- Create: `tests/test_data_root.py`

- [ ] **Step 1: Write the first failing test**

Create `tests/test_data_root.py`:

```python
from pathlib import Path

from osm_polygon_web_search.data_root import data_root


EXPECTED_DATA_ROOT = Path("/Volumes/Seagate M3/projects/osm-polygon-web-search")


def test_data_root_returns_the_canonical_seagate_path() -> None:
    assert data_root() == EXPECTED_DATA_ROOT
```

- [ ] **Step 2: Verify RED**

Run:

```sh
uv run pytest tests/test_data_root.py -q
```

Expected: collection fails because `osm_polygon_web_search.data_root` does not exist. If the test passes, stop and correct the test before writing source code.

- [ ] **Step 3: Commit the RED test**

Run:

```sh
git add tests/test_data_root.py
git commit -m "test: specify seagate data root"
```

### Task 3: Implement the minimal package and entry point

**Files:**
- Create: `src/osm_polygon_web_search/__init__.py`
- Create: `src/osm_polygon_web_search/data_root.py`
- Create: `src/osm_polygon_web_search/__main__.py`
- Create: `tests/test_module_entrypoint.py`
- Modify: `tests/test_data_root.py` only if Ruff requires import ordering

- [ ] **Step 1: Add the smallest implementation for GREEN**

Create `src/osm_polygon_web_search/data_root.py`:

```python
from pathlib import Path

DATA_ROOT = Path("/Volumes/Seagate M3/projects/osm-polygon-web-search")


def data_root() -> Path:
    """Return the only permitted local data root without filesystem access."""
    return DATA_ROOT
```

Create `src/osm_polygon_web_search/__init__.py`:

```python
"""Seagate-only OSM polygon web-search foundation."""

from .data_root import DATA_ROOT, data_root

__version__ = "0.1.0"

__all__ = ["DATA_ROOT", "__version__", "data_root"]
```

- [ ] **Step 2: Verify GREEN**

Run:

```sh
uv run pytest tests/test_data_root.py -q
```

Expected: one passing test and no filesystem changes under the Seagate path.

- [ ] **Step 3: Write the entry-point RED test**

Create `tests/test_module_entrypoint.py`:

```python
import subprocess
import sys


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
```

Run `uv run pytest tests/test_module_entrypoint.py -q`; expected: FAIL because `__main__.py` is absent.

- [ ] **Step 4: Add the minimal entry point for GREEN**

Create `src/osm_polygon_web_search/__main__.py`:

```python
from .data_root import data_root


def main() -> None:
    print(data_root())


if __name__ == "__main__":
    main()
```

Run:

```sh
uv run pytest -q
uv run python -m osm_polygon_web_search
```

Expected: two passing tests and exactly the canonical path on stdout.

- [ ] **Step 5: Commit the package behavior**

Run:

```sh
git add src tests
git commit -m "feat: expose seagate data root"
```

### Task 4: Add legal metadata, README, and strict MkDocs content

**Files:**
- Create: `LICENSE`
- Create: `CITATION.cff`
- Create: `README.md`
- Create: `mkdocs.yml`
- Create: `docs/index.md`
- Create: `docs/getting-started.md`
- Create: `docs/data-layout.md`
- Create: `docs/development.md`
- Create: `docs/citation.md`
- Create: `dataset/README.md`

- [ ] **Step 1: Write repository contract tests before the files**

Create `tests/test_repository_contracts.py` with tests that read only checkout files:

```python
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
```

Run `uv run pytest tests/test_repository_contracts.py -q`; expected: collection or file-not-found failures because the publication files do not yet exist.

- [ ] **Step 2: Add Apache-2.0 and citation metadata**

Add the complete standard Apache License 2.0 text to `LICENSE`. Add `CITATION.cff` with CFF version `1.2.0`, title `OSM Polygon Web Search`, version `0.1.0`, release date `2026-08-25`, author Noe Flandre, repository URL `https://github.com/NoeFlandre/osm-polygon-web-search`, and `license: Apache-2.0`.

- [ ] **Step 3: Add the code README and dataset card**

`README.md` must describe the current metadata-only scope, the exact Seagate data policy, uv setup, smoke command, quality commands, documentation link, and citation/license links. It must not suggest that data is available remotely.

`dataset/README.md` must begin with YAML front matter containing:

```yaml
---
license: apache-2.0
pretty_name: OSM Polygon Web Search
tags:
  - openstreetmap
  - geospatial
---
```

The card must state exactly that no data files are published, all local and derived data stays on the Seagate volume, and future data publication is outside this approved scope. Do not place any data file in `dataset/`.

- [ ] **Step 4: Add the MkDocs site**

Configure `mkdocs.yml` with Material, `site_name: OSM Polygon Web Search`, `site_url: https://noeflandre.github.io/osm-polygon-web-search/`, repository links for `NoeFlandre/osm-polygon-web-search`, explicit navigation for the five public pages, and `exclude_docs: superpowers/**`.

The pages must provide copyable commands that match `pyproject.toml` and explain the Seagate-only boundary, metadata-only HF repository, local quality gate, Apache-2.0 license, and citation.

- [ ] **Step 5: Verify the contract tests and strict local site**

Run:

```sh
uv run pytest tests/test_repository_contracts.py -q
uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
```

Expected: contract tests pass; MkDocs exits 0 and writes `/tmp/osm-polygon-web-search-site/index.html` without warnings. Inspect the generated site for the landing page and all explicit navigation pages.

- [ ] **Step 6: Commit documentation and legal metadata**

Run:

```sh
git add LICENSE CITATION.cff README.md mkdocs.yml docs dataset tests/test_repository_contracts.py
git commit -m "docs: add project and dataset publication metadata"
```

### Task 5: Add Docker and GitHub Actions workflows

**Files:**
- Create: `Dockerfile`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/docs.yml`
- Modify: `tests/test_repository_contracts.py`

- [ ] **Step 1: Extend RED contract tests for Docker and workflows**

Add these tests before creating the workflow files:

```python
def test_dockerfile_runs_the_module_smoke_command() -> None:
    text = (ROOT / "Dockerfile").read_text()
    assert "uv sync --frozen --no-dev" in text
    assert 'CMD ["uv", "run", "--no-dev", "python", "-m", "osm_polygon_web_search"]' in text


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
```

Run the focused tests and observe the expected failures for the absent files.

- [ ] **Step 2: Add the minimal Docker image**

Create a `python:3.12-slim` image with `/app` as the work directory. Copy `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, and `src/`; install uv; run `uv sync --frozen --no-dev`; set `CMD ["uv", "run", "--no-dev", "python", "-m", "osm_polygon_web_search"]`. Do not copy tests, caches, the Seagate path, or any generated data.

- [ ] **Step 3: Add the CI workflow**

Create `.github/workflows/ci.yml` for pushes to `main` and pull requests. Use read-only contents permission, checkout, uv setup, `uv sync --frozen`, then run the exact format, lint, type, test/coverage, strict MkDocs, mutation, and Docker commands. Keep mutation and Docker as explicit steps whose failures stop the job.

- [ ] **Step 4: Add the Pages workflow**

Create `.github/workflows/docs.yml` for pushes to `main` and manual dispatch. Build the site with `uv run mkdocs build --strict --site-dir site`, upload only `site`, and deploy via GitHub Pages. Use `contents: read`, `pages: write`, and `id-token: write` only where required, and expose the deployment URL through the Pages environment.

- [ ] **Step 5: Verify workflow contracts and local Docker**

Run:

```sh
uv run pytest tests/test_repository_contracts.py -q
docker build -t osm-polygon-web-search:local .
docker run --rm osm-polygon-web-search:local
```

Expected: all contract tests pass; the image builds; the container prints the exact Seagate path and does not access it.

- [ ] **Step 6: Commit the container and workflow changes**

Run:

```sh
git add Dockerfile .dockerignore .github tests/test_repository_contracts.py
git commit -m "ci: add docker and documentation workflows"
```

### Task 6: Run the complete local quality gate and review the diff

**Files:**
- Modify only files needed to correct verified failures.
- Generated/ignored: `/tmp/osm-polygon-web-search-site`, mutation cache, coverage output.

- [ ] **Step 1: Run the RED→GREEN and repository tests freshly**

Run:

```sh
uv run pytest -q --cov=osm_polygon_web_search --cov-report=term-missing
```

Expected: all tests pass, coverage reports 100% for the small package, and no warnings indicate missing configuration.

- [ ] **Step 2: Run formatting, linting, and typing**

Run:

```sh
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

Expected: each command exits 0. Apply only formatter-approved changes, then rerun all three commands.

- [ ] **Step 3: Run strict documentation validation**

Run:

```sh
rm -rf /tmp/osm-polygon-web-search-site
uv run mkdocs build --strict --site-dir /tmp/osm-polygon-web-search-site
test -s /tmp/osm-polygon-web-search-site/index.html
```

Expected: strict build succeeds and the landing page is non-empty. The generated site must not contain `docs/superpowers`.

- [ ] **Step 4: Run mutation testing to completion**

Run:

```sh
uv run mutmut run --paths-to-mutate src/osm_polygon_web_search/
uv run mutmut results
```

Expected: the run completes for the entire package with zero surviving or unresolved mutants. If the installed mutmut version uses a different configuration entry point, inspect `uv run mutmut run --help`, make the smallest configuration correction, and rerun from a clean mutation state; do not report a partial run as passing.

- [ ] **Step 5: Run pre-commit, Docker, and repository hygiene checks**

Run:

```sh
uv run pre-commit run --all-files
docker build -t osm-polygon-web-search:local .
docker run --rm osm-polygon-web-search:local
git diff --check
git status --short --branch
```

Expected: all feasible commands exit 0; only intentional tracked files are present; no Seagate path or generated artifact is staged.

- [ ] **Step 6: Commit any verified corrections and record the gate**

If corrections were required, commit them with a focused Conventional Commit. Record exact command output and distinguish passed, skipped, blocked, and incomplete checks.

### Task 7: Create and verify the public remotes

**Files:**
- Modify: `.git/config` via Git remote setup only.
- Remote GitHub repository: `NoeFlandre/osm-polygon-web-search`.
- Remote Hugging Face dataset repository: authenticated namespace `/osm-polygon-web-search`.

- [ ] **Step 1: Verify local publication preconditions**

Run:

```sh
git status --short --branch
git log --oneline --decorate -5
git diff --check
gh auth status
hf auth whoami
```

Do not proceed with a remote write if local quality evidence is incomplete. Do not print tokens.

- [ ] **Step 2: Create and push the GitHub repository**

Run the authenticated GitHub CLI command:

```sh
gh repo create NoeFlandre/osm-polygon-web-search --public --description "A Seagate-only foundation for OSM polygon web-search data work." --source . --remote origin --push
```

If the repository already exists, inspect it first and use the existing remote without overwriting unrelated history. Verify with `git ls-remote origin refs/heads/main` and `gh repo view NoeFlandre/osm-polygon-web-search --json nameWithOwner,isPrivate,defaultBranchRef,url`.

- [ ] **Step 3: Create the metadata-only Hugging Face dataset**

Derive the authenticated namespace without exposing the token:

```sh
HF_NAMESPACE="${HF_NAMESPACE:-$(hf auth whoami --format json | python3 -c 'import json, sys; print(json.load(sys.stdin)["name"])')}"
hf repos create "${HF_NAMESPACE}/osm-polygon-web-search" --type dataset --exist-ok
hf upload "${HF_NAMESPACE}/osm-polygon-web-search" dataset/README.md README.md --commit-message "docs: add dataset card"
hf upload "${HF_NAMESPACE}/osm-polygon-web-search" LICENSE LICENSE --commit-message "legal: add apache license"
```

Verify that the dataset repository contains only the card and license through `hf datasets info "${HF_NAMESPACE}/osm-polygon-web-search"` and a metadata listing. Never use a recursive upload of the checkout or Seagate path.

- [ ] **Step 4: Verify GitHub Pages publication**

After the GitHub push, inspect the Actions run and wait for both build and deploy jobs. Verify the configured Pages URL returns the expected title and landing-page text. If repository Pages settings require an external manual change, report the exact setting and do not alter unrelated settings.

- [ ] **Step 5: Verify clean synchronization and data safety**

Run:

```sh
git fetch origin main
git rev-parse HEAD
git rev-parse origin/main
git status --short --branch
git ls-remote origin refs/heads/main
```

Expected: local `HEAD` equals `origin/main`, the worktree is clean, the GitHub repository is public, the HF repository is public and metadata-only, and no local data path was read or modified.

- [ ] **Step 6: Final handoff**

Report the GitHub URL, HF dataset URL, Pages URL and live verification status, commit SHA, exact local gates and outcomes, any external blocker, and explicit confirmation that no Seagate data was accessed or uploaded. Do not claim publication if a workflow, remote ref, or live URL was not verified.
