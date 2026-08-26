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
    prefix = f'"{_clean_phrase(name)}" "{_clean_phrase(country)}"'
    if len(cleaned_keywords) == 1:
        return f"{prefix} {cleaned_keywords[0]}"
    return f"{prefix} ({' OR '.join(cleaned_keywords)})"
