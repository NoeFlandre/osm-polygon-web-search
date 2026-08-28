from email.message import Message

from osm_polygon_web_search.retry import retry_delay, wait_before_retry


def headers(value: str | None = None) -> Message:
    result = Message()
    if value is not None:
        result["Retry-After"] = value
    return result


def test_retry_delay_prefers_valid_retry_after() -> None:
    assert retry_delay(headers("3"), 1, 2.0) == 3.0
    assert retry_delay({"Retry-After": "3"}, 1, 2.0) == 3.0


def test_retry_delay_uses_backoff_for_missing_or_invalid_header() -> None:
    assert retry_delay(None, 1, 2.0) == 4.0
    assert retry_delay(headers("later"), 1, 2.0) == 4.0


def test_wait_before_retry_only_sleeps_for_retryable_attempts() -> None:
    sleeps: list[float] = []
    assert wait_before_retry(
        503,
        headers("0"),
        attempt=0,
        max_retries=1,
        backoff_seconds=2.0,
        sleep=sleeps.append,
    )
    assert not wait_before_retry(
        500,
        headers("0"),
        attempt=0,
        max_retries=1,
        backoff_seconds=2.0,
        sleep=sleeps.append,
    )
    assert not wait_before_retry(
        503,
        headers("0"),
        attempt=1,
        max_retries=1,
        backoff_seconds=2.0,
        sleep=sleeps.append,
    )
    assert sleeps == [0.0]
