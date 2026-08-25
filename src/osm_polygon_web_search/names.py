import unicodedata


def normalize_name(value: str) -> str:
    """Return the conservative key used for polygon-name uniqueness."""
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.casefold().split())
