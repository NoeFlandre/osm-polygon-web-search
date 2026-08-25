import trafilatura


def extract_text(html: str) -> str | None:
    """Extract readable page text with Trafilatura."""
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
    )
    if extracted is None:
        return None
    text = extracted.strip()
    return text or None
