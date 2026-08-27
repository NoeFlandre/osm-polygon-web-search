from collections.abc import Iterable

QUERY_VARIANTS: tuple[tuple[str, str], ...] = (
    ("v1", "land cover"),
    ("v2", "land use"),
    ("v3", "vegetation"),
    ("v4", "terrain"),
    ("v5", "soil surface"),
    ("v6", "ecosystem"),
    ("v7", "physical geography"),
    ("v8", "buildings infrastructure"),
    ("v9", "landscape environment"),
)


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


def build_variant_queries(
    name: str,
    country: str,
    variants: Iterable[tuple[str, str]] = QUERY_VARIANTS,
) -> list[dict[str, str]]:
    """Build independently identifiable queries for the approved variants."""
    return [
        {
            "id": variant_id,
            "keyword": keyword,
            "query": build_query(name, country, [keyword]),
        }
        for variant_id, keyword in variants
    ]
