from __future__ import annotations

import re
from enum import StrEnum

_WAIT_PATTERNS = (
    re.compile(
        r"(?:FLOOD(?:_PREMIUM)?_WAIT|SLOWMODE_WAIT|TAKEOUT_INIT_DELAY|"
        r"2FA_CONFIRM_WAIT|RETRY_AFTER|WAIT)_(?P<seconds>\d+)(?:\D|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:retry\s+after|try\s+again\s+in|wait)\D{0,24}"
        r"(?P<seconds>\d+)\s*(?:seconds?|secs?|s)\b",
        re.IGNORECASE,
    ),
)


class EitaaError(RuntimeError):
    """Base error for the Eitaa client."""

    retry_after_seconds: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a stable machine-readable representation of the error."""

        return {
            "type": self.__class__.__name__,
            "message": str(self),
            "retry_after_seconds": self.retry_after_seconds,
        }


class EitaaTransportError(EitaaError):
    """Raised when every configured HTTPS endpoint fails."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class TLCodecError(EitaaError):
    """Raised for invalid TL input or malformed TL responses."""


class EitaaRPCError(EitaaError):
    """An API-level error object returned by Eitaa."""

    def __init__(self, code: int, text: str, method: str | None = None) -> None:
        self.code = code
        self.text = text
        self.method = method
        self.retry_after_seconds = parse_retry_after_seconds(text)
        prefix = f"{method}: " if method else ""
        super().__init__(f"{prefix}{text} (code {code})")

    @property
    def normalized_text(self) -> str:
        """Return an uppercase identifier suitable for classification."""

        return re.sub(r"[^A-Z0-9]+", "_", self.text.upper()).strip("_")

    @property
    def retryable(self) -> bool:
        """Return whether retrying later is generally safe."""

        return bool(
            self.retry_after_seconds is not None
            or self.code in {420, 429, 500, 502, 503, 504}
            or self.normalized_text.startswith(
                ("FLOOD_", "RETRY_", "TEMPORARILY_", "TIMEOUT", "SERVER_")
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **super().to_dict(),
            "code": self.code,
            "rpc_text": self.text,
            "method": self.method,
            "retryable": self.retryable,
        }


class OtpOperation(StrEnum):
    """Authentication operation that failed."""

    REQUEST = "request"
    RESEND = "resend"
    SIGN_IN = "sign-in"
    SIGN_UP = "sign-up"


class OtpFailureReason(StrEnum):
    """Stable OTP failure categories independent of Eitaa's raw RPC strings."""

    RATE_LIMITED = "rate-limited"
    INVALID_PHONE_NUMBER = "invalid-phone-number"
    BANNED_PHONE_NUMBER = "banned-phone-number"
    INVALID_CODE = "invalid-code"
    EXPIRED_CODE = "expired-code"
    INVALID_CHALLENGE = "invalid-challenge"
    PASSWORD_REQUIRED = "password-required"
    RESTART_REQUIRED = "restart-required"
    DELIVERY_UNAVAILABLE = "delivery-unavailable"
    UNKNOWN = "unknown"


class OtpError(EitaaError):
    """A typed OTP failure with an actionable, stable reason."""

    def __init__(
        self,
        *,
        operation: OtpOperation,
        reason: OtpFailureReason,
        rpc_error: EitaaRPCError,
    ) -> None:
        self.operation = operation
        self.reason = reason
        self.rpc_error = rpc_error
        self.retry_after_seconds = rpc_error.retry_after_seconds
        super().__init__(str(rpc_error))

    def to_dict(self) -> dict[str, object]:
        return {
            **super().to_dict(),
            "operation": self.operation.value,
            "reason": self.reason.value,
            "rpc": self.rpc_error.to_dict(),
        }


class AuthenticationRequired(EitaaError):
    """Raised when a command needs an active saved token."""


class PeerResolutionError(EitaaError):
    """Raised when a user/chat/channel reference cannot be resolved."""


def parse_retry_after_seconds(text: str) -> int | None:
    """Extract an exact server-provided retry delay without guessing.

    Eitaa is Telegram-derived and commonly returns identifiers such as
    ``FLOOD_WAIT_120``. Some gateways instead return prose such as
    ``try again in 120 seconds``. Unrelated digits, including identifiers like
    ``RETRY_LIMIT404``, are deliberately ignored.
    """

    for pattern in _WAIT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        seconds = int(match.group("seconds"))
        if seconds >= 0:
            return seconds
    return None


def classify_otp_rpc_error(
    error: EitaaRPCError,
    *,
    operation: OtpOperation,
) -> OtpError:
    """Translate raw Eitaa authentication errors into stable OTP categories."""

    text = error.normalized_text
    if error.retry_after_seconds is not None or any(
        marker in text
        for marker in (
            "FLOOD",
            "TOO_MANY",
            "RATE_LIMIT",
            "PHONE_NUMBER_FLOOD",
            "RETRY_LATER",
        )
    ):
        reason = OtpFailureReason.RATE_LIMITED
    elif "PHONE_NUMBER_BANNED" in text:
        reason = OtpFailureReason.BANNED_PHONE_NUMBER
    elif any(marker in text for marker in ("PHONE_NUMBER_INVALID", "PHONE_NUMBER_EMPTY")):
        reason = OtpFailureReason.INVALID_PHONE_NUMBER
    elif any(marker in text for marker in ("PHONE_CODE_EXPIRED", "CODE_EXPIRED")):
        reason = OtpFailureReason.EXPIRED_CODE
    elif any(
        marker in text for marker in ("PHONE_CODE_INVALID", "PHONE_CODE_EMPTY", "CODE_INVALID")
    ):
        reason = OtpFailureReason.INVALID_CODE
    elif any(
        marker in text
        for marker in (
            "PHONE_CODE_HASH_INVALID",
            "PHONE_CODE_HASH_EMPTY",
            "PHONE_CODE_HASH_EXPIRED",
        )
    ):
        reason = OtpFailureReason.INVALID_CHALLENGE
    elif any(marker in text for marker in ("SESSION_PASSWORD_NEEDED", "PASSWORD_HASH_INVALID")):
        reason = OtpFailureReason.PASSWORD_REQUIRED
    elif "AUTH_RESTART" in text:
        reason = OtpFailureReason.RESTART_REQUIRED
    elif any(
        marker in text
        for marker in (
            "SEND_CODE_UNAVAILABLE",
            "SMS_CODE_CREATE_FAILED",
            "PHONE_NUMBER_APP_SIGNUP_FORBIDDEN",
        )
    ):
        reason = OtpFailureReason.DELIVERY_UNAVAILABLE
    else:
        reason = OtpFailureReason.UNKNOWN
    return OtpError(operation=operation, reason=reason, rpc_error=error)
