from pathlib import Path

DATA_ROOT = Path("/Volumes/Seagate M3/projects/osm-polygon-web-search")


def data_root() -> Path:
    """Return the only permitted local data root without filesystem access."""
    return DATA_ROOT
