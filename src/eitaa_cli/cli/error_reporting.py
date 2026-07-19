from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console

from eitaa_cli.errors import (
    AuthenticationRequired,
    EitaaError,
    EitaaRPCError,
    EitaaTransportError,
    OtpError,
    OtpFailureReason,
    PeerResolutionError,
)


@dataclass(frozen=True, slots=True)
class ErrorReport:
    """User-facing error content separated from protocol exceptions."""

    title: str
    message: str
    action: str | None = None
    hint: str | None = None
    technical: str | None = None


def humanize_duration(seconds: int) -> str:
    """Format a non-negative duration without losing precision."""

    remaining = max(0, seconds)
    units = (
        ("day", 86_400),
        ("hour", 3_600),
        ("minute", 60),
        ("second", 1),
    )
    parts: list[str] = []
    for name, size in units:
        value, remaining = divmod(remaining, size)
        if value:
            suffix = "" if value == 1 else "s"
            parts.append(f"{value} {name}{suffix}")
        if len(parts) == 2:
            break
    return " ".join(parts) or "0 seconds"


def build_error_report(error: Exception) -> ErrorReport:
    """Translate domain and standard exceptions into actionable CLI guidance."""

    if isinstance(error, OtpError):
        return _otp_error_report(error)
    if isinstance(error, EitaaRPCError):
        return _rpc_error_report(error)
    if isinstance(error, EitaaTransportError):
        action = _retry_action(error.retry_after_seconds)
        return ErrorReport(
            title="Could not reach Eitaa",
            message="All configured Eitaa endpoints failed or returned an unusable response.",
            action=action
            or "Check your internet connection, DNS, firewall, and system clock, then retry.",
            hint="Repeated OTP requests are not useful while the network is unavailable.",
            technical=str(error),
        )
    if isinstance(error, AuthenticationRequired):
        return ErrorReport(
            title="Authentication required",
            message=str(error),
            action="Run `eitaa auth login PHONE_NUMBER`, then repeat the command.",
        )
    if isinstance(error, PeerResolutionError):
        return ErrorReport(
            title="Could not resolve the peer",
            message=str(error),
            action="Copy a typed peer reference from `eitaa chats list` and try again.",
        )
    if isinstance(error, FileNotFoundError):
        return ErrorReport(
            title="File not found",
            message=str(error),
            action="Check the path and confirm the file is readable.",
        )
    if isinstance(error, (ValueError, KeyError)):
        return ErrorReport(
            title="Invalid input",
            message=str(error),
            action="Correct the command arguments and try again.",
        )
    if isinstance(error, EitaaError):
        return ErrorReport(
            title="Eitaa request failed",
            message=str(error),
            action=_retry_action(error.retry_after_seconds),
        )
    return ErrorReport(title="Unexpected error", message=str(error))


def render_error(console: Console, error: Exception) -> None:
    """Render one consistent error block for all CLI commands."""

    report = build_error_report(error)
    console.print(f"[bold red]{report.title}[/bold red]")
    console.print(report.message)
    if report.action:
        console.print(f"[bold yellow]Next step:[/bold yellow] {report.action}")
    if report.hint:
        console.print(f"[cyan]Hint:[/cyan] {report.hint}")
    if report.technical:
        console.print(f"[dim]Technical details: {report.technical}[/dim]")


def _otp_error_report(error: OtpError) -> ErrorReport:
    operation = {
        "request": "request a new OTP",
        "resend": "resend the OTP",
        "sign-in": "verify the OTP",
        "sign-up": "complete signup",
    }[error.operation.value]
    technical = _rpc_technical(error.rpc_error)

    if error.reason is OtpFailureReason.RATE_LIMITED:
        return ErrorReport(
            title="OTP request temporarily blocked",
            message=f"Eitaa did not allow the CLI to {operation} because the request was rate-limited.",
            action=_retry_action(error.retry_after_seconds)
            or "Try again later; Eitaa did not provide an exact cooldown duration.",
            hint="Do not repeatedly request codes before the cooldown ends; that can extend the limit.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.INVALID_PHONE_NUMBER:
        return ErrorReport(
            title="Invalid phone number",
            message="Eitaa rejected the phone number used for the OTP request.",
            action="Use the full international number, for example `+989121234567`.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.BANNED_PHONE_NUMBER:
        return ErrorReport(
            title="Phone number is not allowed",
            message="Eitaa reported that this phone number is banned or blocked from authentication.",
            action="Confirm the number in the official Eitaa client or contact Eitaa support.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.INVALID_CODE:
        return ErrorReport(
            title="Invalid OTP code",
            message="The code does not match the active OTP challenge.",
            action="Enter the newest code received for the current `phone_code_hash`.",
            hint="Do not reuse a code from an earlier `send-code` or `resend-code` request.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.EXPIRED_CODE:
        return ErrorReport(
            title="OTP code expired",
            message="The submitted OTP is no longer valid.",
            action="Request a new code with `eitaa auth send-code PHONE_NUMBER`.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.INVALID_CHALLENGE:
        return ErrorReport(
            title="OTP challenge is invalid",
            message="The `phone_code_hash` is missing, expired, or belongs to a different OTP request.",
            action="Run `eitaa auth send-code PHONE_NUMBER` and use the newly returned hash.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.PASSWORD_REQUIRED:
        return ErrorReport(
            title="Account password required",
            message="Eitaa accepted the OTP step but requires the account's additional password/SRP verification.",
            action="Complete login in an official Eitaa client until password login is exposed as a high-level CLI command.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.RESTART_REQUIRED:
        return ErrorReport(
            title="Authentication must be restarted",
            message="Eitaa invalidated the current authentication flow.",
            action="Start again with `eitaa auth send-code PHONE_NUMBER`.",
            technical=technical,
        )
    if error.reason is OtpFailureReason.DELIVERY_UNAVAILABLE:
        return ErrorReport(
            title="OTP delivery unavailable",
            message="Eitaa could not create or deliver an OTP using the currently available method.",
            action=_retry_action(error.retry_after_seconds)
            or "Wait before trying again, or use the next delivery method advertised by Eitaa.",
            technical=technical,
        )
    return ErrorReport(
        title="OTP operation failed",
        message=f"Eitaa could not {operation}.",
        action=_retry_action(error.retry_after_seconds)
        or "Review the technical RPC error, then retry only when appropriate.",
        technical=technical,
    )


def _rpc_error_report(error: EitaaRPCError) -> ErrorReport:
    technical = _rpc_technical(error)
    if error.retry_after_seconds is not None:
        return ErrorReport(
            title="Request temporarily rate-limited",
            message="Eitaa asked the client to wait before repeating this operation.",
            action=_retry_action(error.retry_after_seconds),
            hint="Avoid automatic rapid retries.",
            technical=technical,
        )
    if "ADMIN_REQUIRED" in error.normalized_text or error.code == 403:
        return ErrorReport(
            title="Permission denied",
            message="The account does not have the permission required for this operation.",
            action="Confirm membership, ownership, or administrator privileges and try again.",
            technical=technical,
        )
    if error.code >= 500:
        return ErrorReport(
            title="Eitaa server error",
            message="Eitaa could not complete the request because of a temporary server-side failure.",
            action="Retry later. Avoid repeating non-idempotent operations until you know whether they succeeded.",
            technical=technical,
        )
    return ErrorReport(
        title="Eitaa rejected the request",
        message="The server returned an RPC-level error.",
        action="Review the command arguments and account permissions.",
        technical=technical,
    )


def _retry_action(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    return f"Try again in {humanize_duration(seconds)} ({seconds} seconds)."


def _rpc_technical(error: EitaaRPCError) -> str:
    method = f" method={error.method}" if error.method else ""
    return f"RPC {error.text} (code {error.code}){method}"
