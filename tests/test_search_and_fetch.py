import json
import threading
import time
from email.message import Message
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import osm_polygon_web_search.fetch as fetch_module
import osm_polygon_web_search.search as search_module
from osm_polygon_web_search.fetch import (
    FetchedPage,
    PageFetcher,
    PageFetchError,
    fetch_pages,
)
from osm_polygon_web_search.http import HTTPRequestError, HTTPResponse
from osm_polygon_web_search.retry import retry_delay
from osm_polygon_web_search.search import (
    BraveSearchProvider,
    SearchProviderError,
    SearchResult,
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
        sleep=lambda _delay: None,
    )

    assert provider.search('"Alp X" "Liechtenstein" geology') == [
        SearchResult(
            rank=1,
            title="Alp X",
            url="https://example.test/alp-x",
            snippet="A limestone landscape.",
        )
    ]


def test_brave_provider_defaults_and_normalizes_retry_settings() -> None:
    provider = BraveSearchProvider(api_key="secret")

    assert provider.base_url == "https://api.search.brave.com/res/v1/web/search"
    assert provider.timeout == 20.0
    assert provider.max_retries == 2
    assert provider.backoff_seconds == 1.0
    assert provider.sleep is time.sleep

    normalized = BraveSearchProvider(
        api_key="secret",
        max_retries=-1,
        backoff_seconds=-1.0,
    )

    assert normalized.max_retries == 0
    assert normalized.backoff_seconds == 0.0


def test_brave_provider_forwards_request_configuration(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def opener(request, timeout):
        return None

    def sleeper(delay):
        return None

    def fake_request_bytes(request, **kwargs):
        captured["request"] = request
        captured["kwargs"] = kwargs
        return HTTPResponse(200, {}, b'{"web": {"results": []}}', None)

    monkeypatch.setattr(search_module, "request_bytes", fake_request_bytes)
    provider = BraveSearchProvider(
        api_key="secret",
        opener=opener,
        base_url="https://example.test/search",
        timeout=3.5,
        max_retries=4,
        backoff_seconds=2.0,
        sleep=sleeper,
    )

    assert provider.search("Alp X") == []

    request = cast(Request, captured["request"])
    assert request.full_url == "https://example.test/search?q=Alp+X&count=5"
    assert {key.lower(): value for key, value in request.header_items()} == {
        "accept": "application/json",
        "x-subscription-token": "secret",
    }
    assert captured["kwargs"] == {
        "opener": opener,
        "timeout": 3.5,
        "max_retries": 4,
        "backoff_seconds": 2.0,
        "sleep": sleeper,
    }


@pytest.mark.parametrize("count, expected", [(0, 1), (25, 20)])
def test_brave_provider_clamps_result_count(
    monkeypatch, count: int, expected: int
) -> None:
    urls: list[str] = []

    def fake_request_bytes(request, **kwargs):
        urls.append(request.full_url)
        return HTTPResponse(200, {}, b'{"web": {"results": []}}', None)

    monkeypatch.setattr(search_module, "request_bytes", fake_request_bytes)

    BraveSearchProvider(api_key="secret").search("test", count=count)

    assert urls == [
        f"https://api.search.brave.com/res/v1/web/search?q=test&count={expected}"
    ]


def test_brave_provider_fails_without_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)

    with pytest.raises(SearchProviderError) as error:
        BraveSearchProvider(api_key="")

    assert str(error.value) == (
        "BRAVE_SEARCH_API_KEY is required for live Brave searches"
    )


def test_brave_provider_reads_the_api_key_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "environment-secret")
    provider = BraveSearchProvider(
        opener=lambda request, timeout: FakeResponse(b'{"web": {"results": []}}'),
        sleep=lambda _delay: None,
    )

    assert provider.api_key == "environment-secret"
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
    fetcher = PageFetcher(
        opener=lambda request, timeout: FakeResponse(html),
        sleep=lambda _delay: None,
    )

    page = fetcher.fetch("https://example.test/alp-x")

    assert page.status == 200
    assert page.text is not None
    assert "limestone" in page.text


def test_page_fetcher_defaults_and_normalizes_configuration() -> None:
    fetcher = PageFetcher(opener=lambda request, timeout: FakeResponse(b""))

    assert fetcher.timeout == 20.0
    assert fetcher.max_bytes == 2_000_000
    assert fetcher.user_agent == (
        "osm-polygon-web-search/0.1 "
        "(+https://github.com/NoeFlandre/osm-polygon-web-search)"
    )
    assert fetcher.max_retries == 2
    assert fetcher.backoff_seconds == 1.0
    assert fetcher.min_delay_seconds == 0.0
    assert fetcher.sleep is time.sleep

    normalized = PageFetcher(
        opener=lambda request, timeout: FakeResponse(b""),
        max_retries=-1,
        backoff_seconds=-1.0,
        min_delay_seconds=-1.0,
    )

    assert normalized.max_retries == 0
    assert normalized.backoff_seconds == 0.0
    assert normalized.min_delay_seconds == 0.0


def test_page_fetcher_forwards_request_configuration(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def opener(request, timeout):
        return None

    def sleeper(delay):
        return None

    def fake_request_bytes(request, **kwargs):
        captured["request"] = request
        captured["kwargs"] = kwargs
        return HTTPResponse(200, {}, b"\xff", None)

    monkeypatch.setattr(fetch_module, "request_bytes", fake_request_bytes)
    monkeypatch.setattr(fetch_module, "extract_text", lambda html: "extracted")
    fetcher = PageFetcher(
        opener=opener,
        timeout=3.5,
        max_bytes=4,
        user_agent="test-agent",
        max_retries=4,
        backoff_seconds=2.0,
        sleep=sleeper,
    )

    page = fetcher.fetch("https://example.test/page")

    request = cast(Request, captured["request"])
    assert {key.lower(): value for key, value in request.header_items()} == {
        "accept": "text/html,application/xhtml+xml",
        "user-agent": "test-agent",
    }
    assert captured["kwargs"] == {
        "opener": opener,
        "timeout": 3.5,
        "max_retries": 4,
        "backoff_seconds": 2.0,
        "sleep": sleeper,
        "read_limit": 5,
    }
    assert page == FetchedPage(
        url="https://example.test/page",
        status=200,
        html="�",
        text="extracted",
    )


def test_page_fetcher_includes_the_url_in_response_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_module,
        "request_bytes",
        lambda request, **kwargs: HTTPResponse(500, {}, b"", None),
    )

    with pytest.raises(PageFetchError, match="HTTP 500.*example.test/page"):
        PageFetcher().fetch("https://example.test/page")


def test_page_fetcher_preserves_the_transport_error_cause(monkeypatch) -> None:
    def fake_request_bytes(request, **kwargs):
        try:
            raise ValueError("inner cause")
        except ValueError as cause:
            raise HTTPRequestError("outer error") from cause

    monkeypatch.setattr(fetch_module, "request_bytes", fake_request_bytes)

    with pytest.raises(PageFetchError, match="inner cause"):
        PageFetcher().fetch("https://example.test/page")


def test_page_fetcher_rejects_http_300_response() -> None:
    with pytest.raises(PageFetchError, match="HTTP 300"):
        PageFetcher(
            opener=lambda request, timeout: FakeResponse(b"", status=300),
            sleep=lambda _delay: None,
        ).fetch("https://example.test/redirect")


def test_page_fetcher_accepts_a_payload_at_the_byte_limit() -> None:
    page = PageFetcher(
        opener=lambda request, timeout: FakeResponse(b"1234"),
        max_bytes=4,
        sleep=lambda _delay: None,
    ).fetch("https://example.test/exact")

    assert page.html == "1234"


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
        PageFetcher(opener=opener, sleep=lambda _delay: None).fetch(
            "https://example.test/missing"
        )


def test_page_fetcher_rejects_transport_errors() -> None:
    def opener(request, timeout):
        raise URLError("offline")

    with pytest.raises(PageFetchError, match="page request failed"):
        PageFetcher(opener=opener, sleep=lambda _delay: None).fetch(
            "https://example.test/offline"
        )


def test_page_fetcher_rejects_non_success_response_status() -> None:
    with pytest.raises(PageFetchError, match="HTTP 500"):
        PageFetcher(
            opener=lambda request, timeout: FakeResponse(b"", status=500),
            sleep=lambda _delay: None,
        ).fetch("https://example.test/error")


def test_page_fetcher_rejects_oversized_pages() -> None:
    with pytest.raises(PageFetchError, match="exceeded"):
        PageFetcher(
            opener=lambda request, timeout: FakeResponse(b"12345"),
            max_bytes=4,
            sleep=lambda _delay: None,
        ).fetch("https://example.test/large")


def test_fetch_pages_deduplicates_urls_and_reuses_successful_cache() -> None:
    calls: list[str] = []

    class Fetcher:
        min_delay_seconds = 0.0

        def fetch(self, url: str) -> FetchedPage:
            calls.append(url)
            return FetchedPage(url, 200, "", f"text for {url}")

    cache: dict[str, FetchedPage] = {}
    fetcher = Fetcher()

    assert list(
        fetch_pages(
            fetcher,
            [
                "https://example.test/one",
                "https://example.test/two",
                "https://example.test/one",
            ],
            cache=cache,
        )
    ) == ["https://example.test/one", "https://example.test/two"]
    fetch_pages(fetcher, ["https://example.test/two"], cache=cache)

    assert calls == [
        "https://example.test/one",
        "https://example.test/two",
    ]


def test_fetch_pages_allows_one_worker() -> None:
    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            return FetchedPage(url, 200, "", url)

    assert list(
        fetch_pages(Fetcher(), ["https://example.test/one"], max_workers=1)
    ) == ["https://example.test/one"]


def test_fetch_pages_rejects_an_unexpected_fetch_result_count(monkeypatch) -> None:
    monkeypatch.setattr(fetch_module, "_fetch_missing", lambda *args: [])

    with pytest.raises(ValueError):
        fetch_pages(
            cast(fetch_module.PageProvider, object()),
            ["https://example.test/one"],
        )


def test_fetch_pages_concurrently_fetches_two_urls_with_two_workers() -> None:
    active = 0
    peak = 0
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=1.0)

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait()
            with lock:
                active -= 1
            return FetchedPage(url, 200, "", url)

    urls = [
        "https://example.test/one",
        "https://example.test/two",
    ]

    pages = fetch_pages(Fetcher(), urls, max_workers=2)

    assert list(pages) == urls
    assert peak == 2


def test_fetch_pages_respects_the_worker_limit_for_three_urls() -> None:
    active = 0
    peak = 0
    lock = threading.Lock()
    two_workers_started = threading.Event()
    release = threading.Event()
    pages: dict[str, FetchedPage] = {}

    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                if active >= 2:
                    two_workers_started.set()
            release.wait(timeout=1.0)
            with lock:
                active -= 1
            return FetchedPage(url, 200, "", url)

    urls = [f"https://example.test/{name}" for name in ("one", "two", "three")]

    worker = threading.Thread(
        target=lambda: pages.update(fetch_pages(Fetcher(), urls, max_workers=2))
    )
    worker.start()
    assert two_workers_started.wait(timeout=1.0)
    time.sleep(0.05)
    assert peak == 2
    release.set()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert list(pages) == urls


def test_fetch_pages_keeps_provider_order_with_bounded_concurrency() -> None:
    active = 0
    peak = 0
    lock = threading.Lock()
    barrier = threading.Barrier(4, timeout=1.0)

    class Fetcher:
        min_delay_seconds = 0.0

        def fetch(self, url: str) -> FetchedPage:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait()
            time.sleep(0.02 if url.endswith("one") else 0.01)
            with lock:
                active -= 1
            return FetchedPage(url, 200, "", url)

    urls = [f"https://example.test/{name}" for name in ("one", "two", "three", "four")]

    pages = fetch_pages(Fetcher(), urls)

    assert list(pages) == urls
    assert peak == 4


def test_fetch_pages_does_not_cache_failed_urls() -> None:
    attempts = 0

    class Fetcher:
        min_delay_seconds = 0.0

        def fetch(self, url: str) -> FetchedPage:
            nonlocal attempts
            attempts += 1
            raise PageFetchError(f"cannot fetch {url}")

    cache: dict[str, FetchedPage] = {}
    fetcher = Fetcher()

    assert fetch_pages(fetcher, ["https://example.test/fail"], cache=cache) == {}
    assert fetch_pages(fetcher, ["https://example.test/fail"], cache=cache) == {}

    assert attempts == 2
    assert cache == {}


def test_fetch_pages_requires_a_positive_worker_count() -> None:
    class Fetcher:
        def fetch(self, url: str) -> FetchedPage:
            raise AssertionError(f"fetch should not run for {url}")

    with pytest.raises(ValueError) as error:
        fetch_pages(Fetcher(), [], max_workers=0)

    assert str(error.value) == "max_workers must be at least 1"


def test_retry_delay_falls_back_to_exponential_backoff() -> None:
    assert retry_delay(None, 1, 2.0) == 4.0
    assert retry_delay({"Retry-After": "later"}, 1, 2.0) == 4.0


def test_brave_provider_rejects_bad_json_and_http_errors() -> None:
    invalid = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: FakeResponse(b"not-json"),
        sleep=lambda _delay: None,
    )
    with pytest.raises(SearchProviderError, match="invalid JSON"):
        invalid.search("test")

    def http_error(request, timeout):
        raise HTTPError(request.full_url, 404, "not found", response_headers(), None)

    with pytest.raises(SearchProviderError, match="request failed"):
        BraveSearchProvider(
            api_key="secret",
            opener=http_error,
            sleep=lambda _delay: None,
        ).search("test")


def test_brave_provider_reports_the_transport_error_cause(monkeypatch) -> None:
    def fake_request_bytes(request, **kwargs):
        try:
            raise ValueError("inner cause")
        except ValueError as cause:
            raise HTTPRequestError("outer error") from cause

    monkeypatch.setattr(search_module, "request_bytes", fake_request_bytes)

    with pytest.raises(SearchProviderError, match="inner cause"):
        BraveSearchProvider(api_key="secret").search("test")


def test_brave_provider_rejects_transport_and_response_errors() -> None:
    def offline(request, timeout):
        raise URLError("offline")

    with pytest.raises(SearchProviderError, match="request failed"):
        BraveSearchProvider(
            api_key="secret",
            opener=offline,
            sleep=lambda _delay: None,
        ).search("test")

    with pytest.raises(SearchProviderError, match="HTTP 500"):
        BraveSearchProvider(
            api_key="secret",
            opener=lambda request, timeout: FakeResponse(b"{}", status=500),
            sleep=lambda _delay: None,
        ).search("test")


def test_brave_provider_rejects_http_300_response() -> None:
    with pytest.raises(SearchProviderError, match="HTTP 300"):
        BraveSearchProvider(
            api_key="secret",
            opener=lambda request, timeout: FakeResponse(b"{}", status=300),
            sleep=lambda _delay: None,
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
    assert retry_delay({"Retry-After": "later"}, 1, 2.0) == 4.0


def test_brave_provider_handles_missing_result_fields() -> None:
    response = FakeResponse(
        json.dumps(
            {
                "web": {
                    "results": [
                        {"url": "https://example.test/no-title"},
                        {"title": "No URL"},
                        {"title": "Kept", "url": "https://example.test/kept"},
                    ]
                }
            }
        ).encode()
    )

    results = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: response,
        sleep=lambda _delay: None,
    ).search("test")

    assert results == [
        SearchResult(
            rank=3,
            title="Kept",
            url="https://example.test/kept",
            snippet="",
        )
    ]


def test_brave_provider_handles_missing_web_results() -> None:
    provider = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: FakeResponse(b'{"web": {}}'),
        sleep=lambda _delay: None,
    )

    assert provider.search("test") == []


def test_brave_provider_handles_a_missing_web_object() -> None:
    provider = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: FakeResponse(b"{}"),
        sleep=lambda _delay: None,
    )

    assert provider.search("test") == []


def test_brave_provider_reports_invalid_json_exactly() -> None:
    provider = BraveSearchProvider(
        api_key="secret",
        opener=lambda request, timeout: FakeResponse(b"not-json"),
        sleep=lambda _delay: None,
    )

    with pytest.raises(SearchProviderError) as error:
        provider.search("test")

    assert str(error.value) == "Brave search returned invalid JSON"
