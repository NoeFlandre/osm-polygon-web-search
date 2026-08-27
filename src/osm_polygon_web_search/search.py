import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SearchProviderError(RuntimeError):
    """Raised when a search provider cannot return usable results."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    rank: int
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    def search(self, query: str, *, count: int = 5) -> list[SearchResult]: ...


class BraveSearchProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        opener: Callable[..., Any] = urlopen,
        base_url: str = "https://api.search.brave.com/res/v1/web/search",
        timeout: float = 20.0,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY", "")
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
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
        )
        for attempt in range(self.max_retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    status = int(getattr(response, "status", 200))
                    headers = getattr(response, "headers", {})
                    payload = response.read()
            except HTTPError as error:
                if error.code in {429, 503} and attempt < self.max_retries:
                    self.sleep(
                        _retry_delay(error.headers, attempt, self.backoff_seconds)
                    )
                    continue
                raise SearchProviderError(
                    f"Brave search request failed: {error}"
                ) from error
            except (URLError, OSError) as error:
                raise SearchProviderError(
                    f"Brave search request failed: {error}"
                ) from error

            if status in {429, 503} and attempt < self.max_retries:
                self.sleep(_retry_delay(headers, attempt, self.backoff_seconds))
                continue
            if status < 200 or status >= 300:
                raise SearchProviderError(f"Brave search returned HTTP {status}")
            break
        else:  # pragma: no cover
            raise SearchProviderError("Brave search retries exhausted")

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


def _retry_delay(headers: Any, attempt: int, backoff_seconds: float) -> float:
    retry_after = headers.get("Retry-After") if headers is not None else None
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    return backoff_seconds * (2**attempt)
