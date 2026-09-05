import re
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

SAT_MODEL_ID = "segment-any-text/sat-3l-sm"
SAT_MODEL_NAME = "sat-3l-sm"
SAT_BATCH_SIZE = 32
SAT_OUTER_BATCH_SIZE = 1000

_BULLET_PREFIX = re.compile(r"^\s*[-*•]\s+")
_BRACKETED_REFERENCE = re.compile(
    r"\s*\[(?:\d+(?:\s+\d+)*|"
    r"[^\]]*\b(?:bearbeiten|edit|quelltext|see also|source)\b[^\]]*)\]",
    re.IGNORECASE,
)
_COORDINATE_SENTENCE = re.compile(
    r"\b\d{1,3}\.\d{2,},\s*\d{1,3}\.\d{2,}\b|"
    r"\(latitude,\s*longitude\)",
    re.IGNORECASE,
)
_FOOTNOTE_PREFIX = re.compile(r"^[↑†‡]")
_INLINE_HEADING_PREFIX = re.compile(r"^(?P<heading>[^.!?]+?)\s+[–—]\s+(?P<body>.+)$")
_DASH_HEADING = re.compile(r"^(?P<heading>[^.!?]+?)\s+[‑–—]\s*$")
_KEY_VALUE_FRAGMENT = re.compile(r"^[^\s=]+\s*=\s*[^\s=]+$")
_NUMBERED_REFERENCE_PREFIX = re.compile(r"^\d+(?:\s+\d+){1,2}\s+")
_NUMERIC_VALUE_FRAGMENT = re.compile(
    r"^\d[\d,.]*\s*(?:c|deg|h|hpa|km²|m/s|mm|p/km²|w/m2|%)(?:\s|$)",
    re.IGNORECASE,
)
_SYMBOL_OR_NUMBER_FRAGMENT = re.compile(r"^[\W\d_]+$", re.UNICODE)
_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿ]+)*")
_METADATA_FRAGMENT = re.compile(
    r"^(?:also known as:|category(?::|\s|$)|clouds|commons:|coordinates?|"
    r"country(?:\s|$)|day length|latitude|local time|longitude|"
    r"open location code|openstreetmap id|other pass nearby|phone prefix|"
    r"photo:|pop\.|precip|pressure|settlement(?:\s|$)|solar|source:|"
    r"statistics|sunrise|sunset|temperature|timezone|type(?::|\s|$)|"
    r"uv-b|view on openstreetmap|weather|wind|wikidata)",
    re.IGNORECASE,
)
_NON_CONTENT_PREFIXES = (
    "a brief summary to ",
    "a map to help ",
    "activate your presence",
    "circuit hike for ",
    "conclusion on visiting ",
    "discover the tranquil beauty of ",
    "discover more about ",
    "do you manage this location",
    "excursion destination ",
    "explore expert travel guides",
    "explore the best of what ",
    "explore places such as ",
    "delve into ",
    "how to get here:",
    "how to get to ",
    "how long should ",
    "hi, i'm eve.",
    "is precipitation expected ",
    "more about ",
    "tell me more about ",
    "take control to get ",
    "this page is based on ",
    "this post contains affiliate links",
    "visit the restaurant ",
    "when ",
    "what ",
    "where ",
    "which ",
    "your all-in-one travel companion app",
)
_HEADING_TEXT = frozenset(
    {
        "basic data",
        "getting there",
        "how to get here:",
        "know before you go",
        "location & surroundings",
        "places in the area",
        "places of interest nearby",
        "the swiss franc",
        "web links",
        "weblinks",
    }
)
_HEADING_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
)
_INLINE_HEADING_STARTS = ("by ", "enjoy ", "fishing", "hiking", "hotel ", "photography")


class SentenceModel(Protocol):
    def split(self, text: str, /) -> Iterable[str]: ...


class SatSentenceModel:
    """Small compatibility adapter around the loaded wtpsplit model."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def split(self, text: str, /) -> Iterable[str]:
        return self._model.split(text)

    def split_many(self, texts: Sequence[str], /) -> Iterable[Iterable[str]]:
        return self._model.split(
            list(texts),
            batch_size=SAT_BATCH_SIZE,
            outer_batch_size=SAT_OUTER_BATCH_SIZE,
        )


def _normalize_block(block: str) -> str:
    normalized = block.strip()
    normalized = _BRACKETED_REFERENCE.sub("", normalized).strip()
    normalized = _BULLET_PREFIX.sub("", normalized)
    return " ".join(normalized.split())


def _has_sentence_ending(block: str) -> bool:
    return block.endswith((".", "!", "?"))


def _is_title_word(word: str) -> bool:
    letters = _WORD.search(word)
    return letters is not None and (
        letters.group(0).casefold() in _HEADING_STOPWORDS
        or letters.group(0)[0].isupper()
    )


def _looks_like_heading(block: str) -> bool:
    if _has_sentence_ending(block):
        return False
    words = block.split()
    return len(words) <= 12 and all(
        _is_title_word(word) for word in words if _WORD.search(word)
    )


def _looks_like_inline_heading(block: str) -> bool:
    return _looks_like_heading(block) or block.casefold().startswith(
        _INLINE_HEADING_STARTS
    )


def _is_short_fragment(block: str) -> bool:
    return len(_WORD.findall(block)) < 3 and not _has_sentence_ending(block)


def _is_structural_noise(block: str) -> bool:
    folded = block.casefold().replace("\u2011", "-")
    return (
        bool(_COORDINATE_SENTENCE.search(block))
        or bool(_FOOTNOTE_PREFIX.match(block))
        or bool(_SYMBOL_OR_NUMBER_FRAGMENT.fullmatch(block))
        or bool(_KEY_VALUE_FRAGMENT.fullmatch(block))
        or bool(_NUMBERED_REFERENCE_PREFIX.match(block))
        or bool(_NUMERIC_VALUE_FRAGMENT.match(block))
        or (block.startswith("[") and block.endswith("]"))
        or folded in _HEADING_TEXT
        or bool(_METADATA_FRAGMENT.match(block))
        or folded.endswith(" is a wikidata entity.")
        or folded.startswith(_NON_CONTENT_PREFIXES)
        or bool(_DASH_HEADING.fullmatch(block))
        or _looks_like_heading(block)
        or _is_short_fragment(block)
    )


def _strip_inline_heading(block: str) -> str:
    if _is_structural_noise(block):
        return block
    match = _INLINE_HEADING_PREFIX.match(block)
    if match is not None and _looks_like_inline_heading(match.group("heading")):
        return match.group("body")
    return block


def prepare_for_segmentation(text: str, /) -> str:
    """Remove structural extraction noise before sentence segmentation."""
    blocks = (
        _strip_inline_heading(_normalize_block(block)) for block in text.splitlines()
    )
    retained = [block for block in blocks if block and not _is_structural_noise(block)]
    return "\n".join(retained)


def load_sat_model() -> SatSentenceModel:
    """Load the approved SAT-3L-SM sentence segmentation model."""
    from wtpsplit import SaT

    return SatSentenceModel(SaT(SAT_MODEL_NAME, ort_providers=["CPUExecutionProvider"]))


def _clean_segments(segments: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for segment in segments:
        stripped = segment.strip()
        if stripped:
            cleaned.append(stripped)
    return cleaned


def split_sentences(text: str, model: SentenceModel) -> list[str]:
    """Return non-empty, whitespace-trimmed model segments in source order."""
    return _clean_segments(model.split(text))
