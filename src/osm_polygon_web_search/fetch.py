import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .text import extract_text


class PageFetchError(RuntimeError):
    """Raised when a web page cannot be downloaded safely."""


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status: int
    html: str
    text: str | None


class PageProvider(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...


class PageFetcher:
    def __init__(
        self,
        *,
        opener: Callable[..., Any] = urlopen,
        timeout: float = 20.0,
        max_bytes: int = 2_000_000,
        user_agent: str = "osm-polygon-web-search/0.1 (+https://github.com/NoeFlandre/osm-polygon-web-search)",
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        min_delay_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.opener = opener
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.min_delay_seconds = max(0.0, min_delay_seconds)
        self.sleep = sleep

    def fetch(self, url: str) -> FetchedPage:
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": self.user_agent,
            },
        )
        if self.min_delay_seconds:
            self.sleep(self.min_delay_seconds)

        for attempt in range(self.max_retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    status = int(getattr(response, "status", 200))
                    headers = getattr(response, "headers", {})
                    payload = response.read(self.max_bytes + 1)
            except HTTPError as error:
                if error.code in {429, 503} and attempt < self.max_retries:
                    self.sleep(
                        _retry_delay(error.headers, attempt, self.backoff_seconds)
                    )
                    continue
                raise PageFetchError(
                    f"page request failed for {url}: {error}"
                ) from error
            except (URLError, OSError) as error:
                raise PageFetchError(
                    f"page request failed for {url}: {error}"
                ) from error

            if status in {429, 503} and attempt < self.max_retries:
                self.sleep(_retry_delay(headers, attempt, self.backoff_seconds))
                continue
            if status < 200 or status >= 300:
                raise PageFetchError(f"page request returned HTTP {status} for {url}")
            break
        else:  # pragma: no cover
            raise PageFetchError(f"page request retries exhausted for {url}")

        if len(payload) > self.max_bytes:
            raise PageFetchError(f"page exceeded {self.max_bytes} bytes: {url}")

        html = payload.decode("utf-8", errors="replace")
        return FetchedPage(url=url, status=status, html=html, text=extract_text(html))


def _retry_delay(headers: Any, attempt: int, backoff_seconds: float) -> float:
    retry_after = headers.get("Retry-After") if headers is not None else None
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    return backoff_seconds * (2**attempt)
