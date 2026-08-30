from pathlib import Path

DATA_ROOT = Path("/Volumes/Seagate M3/projects/osm-polygon-web-search")


def data_root() -> Path:
    """Return the only permitted local data root without filesystem access."""
    return DATA_ROOT


def ensure_data_path(path: Path) -> Path:
    """Return a path only when it is inside the configured data root."""
    root = data_root().resolve()
    candidate = path.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"path must stay under the configured data root: {path}"
        ) from error
    return candidate
