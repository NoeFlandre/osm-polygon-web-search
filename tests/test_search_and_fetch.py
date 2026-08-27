import json
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from osm_polygon_web_search.fetch import PageFetcher, PageFetchError, _retry_delay
from osm_polygon_web_search.search import (
    BraveSearchProvider,
    SearchProviderError,
    SearchResult,
)
from osm_polygon_web_search.search import (
    _retry_delay as search_retry_delay,
)


def response_headers(retry_after: str | None = None) -> Message:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return headers


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.headers: dict[str, str] = {}

    def read(self, limit: int = -1) -> bytes:
        return self.payload if limit < 0 else self.payload[:limit]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_brave_provider_maps_web_results() -> None:
    response = FakeResponse(
        json.dumps(
            {
                "web": {
                    "results": [
                        {
                            "title": "Alp X",
                            "url": "https://example.test/alp-x",
                            "description": "A limestone landscape.",
                        },
                        {"title": "", "url": "https://example.test/no-title"},
                        {"title": "No URL", "url": ""},
                    ]
                }
            }
        ).encode()
    )

    provider = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: response,
    )

    assert provider.search('"Alp X" "Liechtenstein" geology') == [
        SearchResult(
            rank=1,
            title="Alp X",
            url="https://example.test/alp-x",
            snippet="A limestone landscape.",
        )
    ]


def test_brave_provider_fails_without_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)

    with pytest.raises(SearchProviderError, match="BRAVE_SEARCH_API_KEY"):
        BraveSearchProvider(api_key="")


def test_brave_provider_reads_the_api_key_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "environment-secret")
    provider = BraveSearchProvider(
        opener=lambda request, timeout: FakeResponse(b'{"web": {"results": []}}')
    )

    assert provider.search("test") == []


def test_brave_provider_retries_rate_limited_searches() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(
                request.full_url,
                503,
                "temporarily unavailable",
                response_headers("0"),
                None,
            )
        return FakeResponse(json.dumps({"web": {"results": []}}).encode())

    provider = BraveSearchProvider(
        api_key="secret",
        opener=opener,
        max_retries=1,
        sleep=sleeps.append,
    )

    assert provider.search("test") == []
    assert attempts == 2
    assert sleeps == [0.0]


def test_page_fetcher_extracts_text_with_trafilatura() -> None:
    html = b"<html><body><article><p>Alp X has limestone.</p></article></body></html>"
    fetcher = PageFetcher(opener=lambda request, timeout: FakeResponse(html))

    page = fetcher.fetch("https://example.test/alp-x")

    assert page.status == 200
    assert page.text is not None
    assert "limestone" in page.text


def test_page_fetcher_retries_rate_limited_pages_with_retry_after() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(
                request.full_url,
                429,
                "too many requests",
                response_headers("0"),
                None,
            )
        return FakeResponse(b"<html><body><p>Alp X has limestone.</p></body></html>")

    fetcher = PageFetcher(
        opener=opener,
        max_retries=1,
        sleep=sleeps.append,
    )

    page = fetcher.fetch("https://example.test/alp-x")

    assert page.status == 200
    assert attempts == 2
    assert sleeps == [0.0]


def test_page_fetcher_retries_a_rate_limited_response_status() -> None:
    responses = iter(
        [
            FakeResponse(b"", status=503),
            FakeResponse(b"<html><body><p>Alp X has limestone.</p></body></html>"),
        ]
    )
    sleeps: list[float] = []
    fetcher = PageFetcher(
        opener=lambda request, timeout: next(responses),
        max_retries=1,
        backoff_seconds=0,
        sleep=sleeps.append,
    )

    page = fetcher.fetch("https://example.test/alp-x")

    assert page.status == 200
    assert sleeps == [0.0]


def test_page_fetcher_applies_a_configured_delay() -> None:
    sleeps: list[float] = []
    fetcher = PageFetcher(
        opener=lambda request, timeout: FakeResponse(b"<p>Alp X has limestone.</p>"),
        min_delay_seconds=0.25,
        sleep=sleeps.append,
    )

    fetcher.fetch("https://example.test/alp-x")

    assert sleeps == [0.25]


def test_page_fetcher_rejects_nonretryable_http_errors() -> None:
    def opener(request, timeout):
        raise HTTPError(request.full_url, 404, "not found", response_headers(), None)

    with pytest.raises(PageFetchError, match="page request failed"):
        PageFetcher(opener=opener).fetch("https://example.test/missing")


def test_page_fetcher_rejects_transport_errors() -> None:
    def opener(request, timeout):
        raise URLError("offline")

    with pytest.raises(PageFetchError, match="page request failed"):
        PageFetcher(opener=opener).fetch("https://example.test/offline")


def test_page_fetcher_rejects_non_success_response_status() -> None:
    with pytest.raises(PageFetchError, match="HTTP 500"):
        PageFetcher(
            opener=lambda request, timeout: FakeResponse(b"", status=500)
        ).fetch("https://example.test/error")


def test_page_fetcher_rejects_oversized_pages() -> None:
    with pytest.raises(PageFetchError, match="exceeded"):
        PageFetcher(
            opener=lambda request, timeout: FakeResponse(b"12345"),
            max_bytes=4,
        ).fetch("https://example.test/large")


def test_retry_delay_falls_back_to_exponential_backoff() -> None:
    assert _retry_delay(None, 1, 2.0) == 4.0
    assert _retry_delay({"Retry-After": "later"}, 1, 2.0) == 4.0


def test_brave_provider_rejects_bad_json_and_http_errors() -> None:
    invalid = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: FakeResponse(b"not-json"),
    )
    with pytest.raises(SearchProviderError, match="invalid JSON"):
        invalid.search("test")

    def http_error(request, timeout):
        raise HTTPError(request.full_url, 404, "not found", response_headers(), None)

    with pytest.raises(SearchProviderError, match="request failed"):
        BraveSearchProvider(api_key="secret", opener=http_error).search("test")


def test_brave_provider_rejects_transport_and_response_errors() -> None:
    def offline(request, timeout):
        raise URLError("offline")

    with pytest.raises(SearchProviderError, match="request failed"):
        BraveSearchProvider(api_key="secret", opener=offline).search("test")

    with pytest.raises(SearchProviderError, match="HTTP 500"):
        BraveSearchProvider(
            api_key="secret",
            opener=lambda request, timeout: FakeResponse(b"{}", status=500),
        ).search("test")


def test_brave_provider_retries_a_rate_limited_response_status() -> None:
    responses = iter(
        [
            FakeResponse(b"{}", status=429),
            FakeResponse(b'{"web": {"results": []}}'),
        ]
    )
    sleeps: list[float] = []
    provider = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: next(responses),
        max_retries=1,
        backoff_seconds=0,
        sleep=sleeps.append,
    )

    assert provider.search("test") == []
    assert sleeps == [0.0]


def test_brave_retry_delay_falls_back_for_invalid_retry_after() -> None:
    assert search_retry_delay({"Retry-After": "later"}, 1, 2.0) == 4.0
