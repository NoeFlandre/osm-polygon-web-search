import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request

from .http import (
    DEFAULT_HTTP_OPENER,
    HTTPOpener,
    HTTPRequestError,
    is_success_status,
    request_bytes,
)


class SearchProviderError(RuntimeError):
    """Raised when a search provider cannot return usable results."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    rank: int
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    def search(
        self, query: str, *, count: int = 5
    ) -> list[SearchResult]:  # pragma: no mutate block
        ...


_ACCEPT_HEADER = "Accept"
_JSON_ACCEPT = "application/json"
_SUBSCRIPTION_TOKEN_HEADER = "X-Subscription-Token"


class BraveSearchProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        opener: HTTPOpener = DEFAULT_HTTP_OPENER,
        base_url: str = "https://api.search.brave.com/res/v1/web/search",
        timeout: float = 20.0,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY") or ""
        if not self.api_key:
            raise SearchProviderError(
                "BRAVE_SEARCH_API_KEY is required for live Brave searches"
            )
        self.opener = opener
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.sleep = sleep

    def search(self, query: str, *, count: int = 5) -> list[SearchResult]:
        params = urlencode({"q": query, "count": max(1, min(count, 20))})
        request = Request(
            f"{self.base_url}?{params}",
            headers={
                _ACCEPT_HEADER: _JSON_ACCEPT,
                _SUBSCRIPTION_TOKEN_HEADER: self.api_key,
            },
        )
        try:
            response = request_bytes(
                request,
                opener=self.opener,
                timeout=self.timeout,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                sleep=self.sleep,
            )
        except HTTPRequestError as error:
            cause = error.__cause__ or error
            raise SearchProviderError(
                f"Brave search request failed: {cause}"
            ) from error

        if response.error is not None:
            raise SearchProviderError(
                f"Brave search request failed: {response.error}"
            ) from response.error
        if not is_success_status(response.status):
            raise SearchProviderError(f"Brave search returned HTTP {response.status}")

        return _parse_results(response.payload)


def _parse_results(payload: bytes) -> list[SearchResult]:
    try:
        data = json.loads(payload)
    except (TypeError, ValueError) as error:
        raise SearchProviderError("Brave search returned invalid JSON") from error

    raw_results = data.get("web", {}).get("results", [])
    results: list[SearchResult] = []
    for rank, raw in enumerate(raw_results, start=1):
        title = str(raw.get("title", "")).strip()
        url = str(raw.get("url", "")).strip()
        if title and url:
            results.append(
                SearchResult(
                    rank=rank,
                    title=title,
                    url=url,
                    snippet=str(raw.get("description", "")).strip(),
                )
            )
    return results
