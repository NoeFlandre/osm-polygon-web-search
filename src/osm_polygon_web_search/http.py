import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, Self, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .retry import HeaderValues, wait_before_retry


class HTTPRequestError(RuntimeError):
    """Raised when an HTTP request cannot be completed."""


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status: int
    headers: HeaderValues
    payload: bytes
    error: HTTPError | None


class HTTPResponseLike(Protocol):
    @property
    def status(self) -> int: ...

    @property
    def headers(self) -> HeaderValues: ...

    def read(self, limit: int = -1) -> bytes: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: object) -> None: ...


class HTTPOpener(Protocol):
    def __call__(self, request: Request, *, timeout: float) -> HTTPResponseLike: ...


DEFAULT_HTTP_OPENER: HTTPOpener = cast(HTTPOpener, urlopen)


def is_success_status(status: int) -> bool:
    return 200 <= status < 300


def request_bytes(
    request: Request,
    *,
    opener: HTTPOpener = DEFAULT_HTTP_OPENER,
    timeout: float = 20.0,
    max_retries: int = 2,
    backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    read_limit: int | None = None,
) -> HTTPResponse:
    max_retries = max(0, max_retries)
    response = _request_once(
        request,
        opener=opener,
        timeout=timeout,
        read_limit=read_limit,
    )
    for attempt in range(max_retries):
        if not wait_before_retry(
            response.status,
            response.headers,
            attempt=attempt,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            sleep=sleep,
        ):
            return response
        response = _request_once(
            request,
            opener=opener,
            timeout=timeout,
            read_limit=read_limit,
        )
    return response


def _request_once(
    request: Request,
    *,
    opener: HTTPOpener,
    timeout: float,
    read_limit: int | None,
) -> HTTPResponse:
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            headers = getattr(response, "headers", {})
            payload = (
                response.read(read_limit) if read_limit is not None else response.read()
            )
    except HTTPError as error:
        error_headers: HeaderValues = error.headers if error.headers is not None else {}
        return HTTPResponse(
            status=error.code,
            headers=error_headers,
            payload=b"",
            error=error,
        )
    except (URLError, OSError) as error:
        raise HTTPRequestError(
            f"request failed for {request.full_url}: {error}"
        ) from error
    return HTTPResponse(
        status=status,
        headers=headers,
        payload=payload,
        error=None,
    )
