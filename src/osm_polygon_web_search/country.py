from pathlib import Path


def country_from_pbf(path: Path) -> str:
    """Derive the country label from a ``<country>-latest.osm.pbf`` name."""
    name = path.name
    if name.endswith(".osm.pbf"):
        name = name[: -len(".osm.pbf")]
    if name.endswith("-latest"):
        name = name[: -len("-latest")]
    country = " ".join(name.replace("-", " ").split()).title()
    if not country:
        raise ValueError(f"cannot derive a country from PBF path: {path}")
    return country
