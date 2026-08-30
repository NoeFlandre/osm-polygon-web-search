import time
from collections.abc import Callable, MutableMapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any, Protocol
from urllib.request import Request, urlopen

from .http import HTTPRequestError, HTTPResponse, request_bytes
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


PAGE_FETCH_WORKERS = 4
_ACCEPT_HEADER = "Accept"
_HTML_ACCEPT = "text/html,application/xhtml+xml"
_USER_AGENT_HEADER = "User-Agent"


def _fetch_or_skip(fetcher: PageProvider, url: str) -> FetchedPage | None:
    try:
        return fetcher.fetch(url)
    except PageFetchError:
        return None


def _fetch_missing(
    fetcher: PageProvider,
    urls: Sequence[str],
    max_workers: int,
) -> list[FetchedPage | None]:
    if len(urls) < 2 or max_workers == 1:
        return [_fetch_or_skip(fetcher, url) for url in urls]

    worker_count = min(max_workers, len(urls))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(partial(_fetch_or_skip, fetcher), urls))


def fetch_pages(
    fetcher: PageProvider,
    urls: Sequence[str],
    *,
    cache: MutableMapping[str, FetchedPage] | None = None,
    max_workers: int = PAGE_FETCH_WORKERS,
) -> dict[str, FetchedPage]:
    """Fetch unique URLs concurrently and return successful pages in URL order."""
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    pages = {} if cache is None else cache
    unique_urls = list(dict.fromkeys(urls))
    missing_urls = [url for url in unique_urls if url not in pages]
    fetched = _fetch_missing(fetcher, missing_urls, max_workers)
    for url, page in zip(missing_urls, fetched, strict=True):
        if page is not None:
            pages[url] = page
    return {url: pages[url] for url in unique_urls if url in pages}


def _page_payload(response: HTTPResponse, url: str, max_bytes: int) -> bytes:
    if response.error is not None:
        raise PageFetchError(
            f"page request failed for {url}: {response.error}"
        ) from response.error
    if response.status < 200 or response.status >= 300:
        raise PageFetchError(f"page request returned HTTP {response.status} for {url}")
    if len(response.payload) > max_bytes:
        raise PageFetchError(f"page exceeded {max_bytes} bytes: {url}")
    return response.payload


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
                _ACCEPT_HEADER: _HTML_ACCEPT,
                _USER_AGENT_HEADER: self.user_agent,
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

        payload = _page_payload(response, url, self.max_bytes)
        html = payload.decode(errors="replace")
        return FetchedPage(
            url=url,
            status=response.status,
            html=html,
            text=extract_text(html),
        )
