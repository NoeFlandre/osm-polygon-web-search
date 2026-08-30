from pathlib import Path


def _country_stem(path: Path) -> str:
    return path.name.removesuffix(".osm.pbf").removesuffix("-latest")


def country_from_pbf(path: Path) -> str:
    """Derive the country label from a ``<country>-latest.osm.pbf`` name."""
    name = _country_stem(path)
    country = " ".join(name.replace("-", " ").split()).title()
    if not country:
        raise ValueError(f"cannot derive a country from PBF path: {path}")
    return country
