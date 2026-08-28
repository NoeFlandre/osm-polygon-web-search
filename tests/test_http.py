from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from osm_polygon_web_search.http import HTTPRequestError, request_bytes


class Response:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.headers: dict[str, str] = {}

    def read(self, limit: int = -1) -> bytes:
        return self.payload if limit < 0 else self.payload[:limit]

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None


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


def test_request_bytes_retries_http_and_response_statuses() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
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


def test_request_bytes_returns_nonretryable_http_error() -> None:
    def opener(request, timeout):
        raise HTTPError(request.full_url, 404, "missing", {}, None)

    result = request_bytes(
        Request("https://example.test"),
        opener=opener,
        timeout=1.0,
        max_retries=1,
        backoff_seconds=0.0,
        sleep=lambda delay: None,
    )
    assert result.status == 404
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
