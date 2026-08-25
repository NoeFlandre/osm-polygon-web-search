from collections.abc import Iterable


def _clean_phrase(value: str) -> str:
    return " ".join(value.replace('"', " ").split())


def _render_keyword(value: str) -> str:
    cleaned = _clean_phrase(value)
    return f'"{cleaned}"' if " " in cleaned else cleaned


def build_query(name: str, country: str, keywords: Iterable[str]) -> str:
    """Build a deterministic exact-place web query."""
    cleaned_keywords = [
        _render_keyword(keyword) for keyword in keywords if keyword.strip()
    ]
    if not cleaned_keywords:
        raise ValueError("at least one search keyword is required")
    return (
        f'"{_clean_phrase(name)}" "{_clean_phrase(country)}" '
        f"({' OR '.join(cleaned_keywords)})"
    )
