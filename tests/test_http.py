from email.message import Message
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from osm_polygon_web_search.http import (
    HTTPOpener,
    HTTPRequestError,
    is_success_status,
    request_bytes,
)


class Response:
    def __init__(
        self,
        payload: bytes,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.status = status
        self.headers = headers if headers is not None else {}
        self.read_limits: list[int] = []

    def read(self, limit: int = -1) -> bytes:
        self.read_limits.append(limit)
        return self.payload if limit < 0 else self.payload[:limit]

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.mark.parametrize(
    ("status", "expected"),
    [(199, False), (200, True), (299, True), (300, False)],
)
def test_is_success_status_uses_the_http_2xx_range(
    status: int,
    expected: bool,
) -> None:
    assert is_success_status(status) is expected


def test_request_bytes_returns_response_data() -> None:
    result = request_bytes(
        Request("https://example.test"),
        opener=lambda request, timeout: Response(b"ready"),
        timeout=1.0,
        max_retries=0,
        backoff_seconds=0.0,
        sleep=lambda delay: None,
    )
    assert (result.status, result.payload, result.error) == (200, b"ready", None)


def test_request_bytes_forwards_timeout_and_read_limit() -> None:
    first = Response(b"busy", status=503)
    second = Response(b"ready", headers={"X-Trace": "yes"})
    responses = iter([first, second])
    timeouts: list[float] = []

    def opener(request: Request, timeout: float) -> Response:
        timeouts.append(timeout)
        return next(responses)

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        timeout=3.5,
        read_limit=3,
        max_retries=1,
        backoff_seconds=0.0,
        sleep=lambda delay: None,
    )

    assert result.headers == {"X-Trace": "yes"}
    assert result.payload == b"rea"
    assert timeouts == [3.5, 3.5]
    assert first.read_limits == [3]
    assert second.read_limits == [3]


class StatuslessResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "StatuslessResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_request_bytes_uses_default_status_and_headers() -> None:
    result = request_bytes(
        Request("https://example.test"),
        opener=cast(
            HTTPOpener,
            lambda request, timeout: StatuslessResponse(b"ready"),
        ),
        max_retries=0,
        sleep=lambda delay: None,
    )

    assert result.status == 200
    assert result.headers == {}


def test_request_bytes_uses_default_timeout_retry_budget_and_backoff() -> None:
    attempts = 0
    timeouts: list[float] = []
    sleeps: list[float] = []

    def opener(request: Request, timeout: float) -> Response:
        nonlocal attempts
        attempts += 1
        timeouts.append(timeout)
        return Response(b"busy", status=503)

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        sleep=sleeps.append,
    )

    assert result.status == 503
    assert attempts == 3
    assert timeouts == [20.0, 20.0, 20.0]
    assert sleeps == [1.0, 2.0]


def test_request_bytes_clamps_negative_retry_counts() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request: Request, timeout: float) -> Response:
        nonlocal attempts
        attempts += 1
        return Response(b"busy", status=503)

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        max_retries=-1,
        sleep=sleeps.append,
    )

    assert result.status == 503
    assert attempts == 1
    assert sleeps == []


def test_request_bytes_respects_the_retry_budget_even_if_policy_overretries(
    monkeypatch,
) -> None:
    import osm_polygon_web_search.http as http_module

    attempts = 0

    def opener(request: Request, timeout: float) -> Response:
        nonlocal attempts
        attempts += 1
        return Response(b"ready")

    monkeypatch.setattr(
        http_module,
        "wait_before_retry",
        lambda *args, **kwargs: True,
    )

    request_bytes(
        Request("https://example.test"),
        opener=opener,
        max_retries=1,
        sleep=lambda delay: None,
    )

    assert attempts == 2


def test_request_bytes_retries_http_and_response_statuses() -> None:
    attempts = 0
    sleeps: list[float] = []
    request_urls: list[str] = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        request_urls.append(request.full_url)
        if attempts == 1:
            raise HTTPError(request.full_url, 503, "busy", Message(), None)
        if attempts == 2:
            return Response(b"busy", status=503)
        return Response(b"ready")

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        timeout=1.0,
        max_retries=2,
        backoff_seconds=0.0,
        sleep=sleeps.append,
    )
    assert result.payload == b"ready"
    assert (attempts, sleeps) == (3, [0.0, 0.0])
    assert request_urls == ["https://example.test"] * 3


def test_request_bytes_returns_nonretryable_http_error() -> None:
    headers = Message()
    headers["X-Error"] = "yes"

    def opener(request, timeout):
        raise HTTPError(request.full_url, 404, "missing", headers, None)

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        timeout=1.0,
        max_retries=1,
        backoff_seconds=0.0,
        sleep=lambda delay: None,
    )
    assert result.status == 404
    assert result.headers == headers
    assert result.payload == b""
    assert result.error is not None


def test_request_bytes_wraps_transport_errors() -> None:
    def opener(request, timeout):
        raise URLError("offline")

    with pytest.raises(HTTPRequestError, match="request failed"):
        request_bytes(
            Request("https://example.test"),
            opener=opener,
            timeout=1.0,
            max_retries=0,
            backoff_seconds=0.0,
            sleep=lambda delay: None,
        )
