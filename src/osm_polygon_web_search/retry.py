import time
from collections.abc import Callable, Mapping
from email.message import Message
from typing import TypeAlias

_RETRYABLE_STATUS_CODES = frozenset({429, 503})

HeaderValues: TypeAlias = Mapping[str, str] | Message


def retry_delay(
    headers: HeaderValues | None,
    attempt: int,
    backoff_seconds: float,
) -> float:
    retry_after = headers.get("Retry-After") if headers is not None else None
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    return backoff_seconds * (2**attempt)


def wait_before_retry(
    status: int,
    headers: HeaderValues | None,
    *,
    attempt: int,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    if status not in _RETRYABLE_STATUS_CODES or attempt >= max_retries:
        return False
    sleep(retry_delay(headers, attempt, backoff_seconds))
    return True
