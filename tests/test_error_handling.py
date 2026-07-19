from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from eitaa_cli.cli.error_reporting import build_error_report, humanize_duration
from eitaa_cli.errors import (
    EitaaRPCError,
    OtpError,
    OtpFailureReason,
    OtpOperation,
    classify_otp_rpc_error,
    parse_retry_after_seconds,
)
from eitaa_cli.services.auth import AuthService


class FailingAuthClient:
    def __init__(self, error: EitaaRPCError) -> None:
        self.error = error
        self.settings = SimpleNamespace(api_id=2496, api_hash="hash")

    async def invoke(
        self,
        method: str,
        params: dict[str, Any],
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        del method, params, token
        raise self.error


def test_retry_delay_parses_rpc_identifier() -> None:
    assert parse_retry_after_seconds("FLOOD_WAIT_137") == 137
    assert parse_retry_after_seconds("FLOOD_PREMIUM_WAIT_42") == 42


def test_retry_delay_parses_server_prose() -> None:
    assert parse_retry_after_seconds("Please try again in 61 seconds") == 61


def test_retry_delay_does_not_guess_from_unrelated_digits() -> None:
    assert parse_retry_after_seconds("RETRY_LIMIT404") is None
    assert parse_retry_after_seconds("PHONE_MIGRATE_2") is None


def test_humanize_duration_keeps_seconds_visible() -> None:
    assert humanize_duration(5) == "5 seconds"
    assert humanize_duration(125) == "2 minutes 5 seconds"
    assert humanize_duration(3_661) == "1 hour 1 minute"


def test_otp_flood_error_has_exact_action() -> None:
    raw = EitaaRPCError(420, "FLOOD_WAIT_125", "auth.sendCode")
    error = classify_otp_rpc_error(raw, operation=OtpOperation.REQUEST)
    report = build_error_report(error)

    assert error.reason is OtpFailureReason.RATE_LIMITED
    assert error.retry_after_seconds == 125
    assert report.title == "OTP request temporarily blocked"
    assert report.action == "Try again in 2 minutes 5 seconds (125 seconds)."
    assert report.technical == "RPC FLOOD_WAIT_125 (code 420) method=auth.sendCode"


def test_invalid_otp_has_specific_guidance() -> None:
    raw = EitaaRPCError(400, "PHONE_CODE_INVALID", "auth.signIn")
    error = classify_otp_rpc_error(raw, operation=OtpOperation.SIGN_IN)
    report = build_error_report(error)

    assert error.reason is OtpFailureReason.INVALID_CODE
    assert report.title == "Invalid OTP code"
    assert "newest code" in (report.action or "")


@pytest.mark.asyncio
async def test_auth_service_translates_raw_rpc_errors() -> None:
    client = FailingAuthClient(EitaaRPCError(420, "FLOOD_WAIT_90", "auth.sendCode"))

    with pytest.raises(OtpError) as captured:
        await AuthService(client).request_code("+989121234567")  # type: ignore[arg-type]

    assert captured.value.operation is OtpOperation.REQUEST
    assert captured.value.reason is OtpFailureReason.RATE_LIMITED
    assert captured.value.retry_after_seconds == 90
