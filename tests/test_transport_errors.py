from __future__ import annotations

from eitaa_cli.transport.http import _retry_after_seconds


def test_http_retry_after_delta_seconds() -> None:
    assert _retry_after_seconds("120") == 120


def test_http_retry_after_invalid_value() -> None:
    assert _retry_after_seconds("not-a-date") is None
