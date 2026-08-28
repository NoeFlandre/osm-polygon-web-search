import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.request import Request, urlopen

from .http import HTTPRequestError, request_bytes
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

        try:
            response = request_bytes(
                request,
                opener=self.opener,
                timeout=self.timeout,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                sleep=self.sleep,
                read_limit=self.max_bytes + 1,
            )
        except HTTPRequestError as error:
            cause = error.__cause__ or error
            raise PageFetchError(f"page request failed for {url}: {cause}") from error

        if response.error is not None:
            raise PageFetchError(
                f"page request failed for {url}: {response.error}"
            ) from response.error
        status = response.status
        payload = response.payload
        if status < 200 or status >= 300:
            raise PageFetchError(f"page request returned HTTP {status} for {url}")

        if len(payload) > self.max_bytes:
            raise PageFetchError(f"page exceeded {self.max_bytes} bytes: {url}")

        html = payload.decode("utf-8", errors="replace")
        return FetchedPage(url=url, status=status, html=html, text=extract_text(html))
