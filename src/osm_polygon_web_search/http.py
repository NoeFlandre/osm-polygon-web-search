import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
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


def request_bytes(
    request: Request,
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 20.0,
    max_retries: int = 2,
    backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    read_limit: int | None = None,
) -> HTTPResponse:
    max_retries = max(0, max_retries)
    attempt = 0
    while True:
        response = _request_once(
            request,
            opener=opener,
            timeout=timeout,
            read_limit=read_limit,
        )
        if wait_before_retry(
            response.status,
            response.headers,
            attempt=attempt,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            sleep=sleep,
        ):
            attempt += 1
            continue
        return response


def _request_once(
    request: Request,
    *,
    opener: Callable[..., Any],
    timeout: float,
    read_limit: int | None,
) -> HTTPResponse:
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            headers = cast(HeaderValues, getattr(response, "headers", {}))
            payload = _read_payload(response, read_limit)
    except HTTPError as error:
        error_headers: HeaderValues = (
            cast(HeaderValues, error.headers) if error.headers is not None else {}
        )
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


def _read_payload(response: Any, read_limit: int | None) -> bytes:
    return response.read(read_limit) if read_limit is not None else response.read()
