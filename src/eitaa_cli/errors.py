from __future__ import annotations


class EitaaError(RuntimeError):
    """Base error for the Eitaa client."""


class EitaaTransportError(EitaaError):
    """Raised when every configured HTTPS endpoint fails."""


class TLCodecError(EitaaError):
    """Raised for invalid TL input or malformed TL responses."""


class EitaaRPCError(EitaaError):
    """An API-level error object returned by Eitaa."""

    def __init__(self, code: int, text: str, method: str | None = None) -> None:
        self.code = code
        self.text = text
        self.method = method
        prefix = f"{method}: " if method else ""
        super().__init__(f"{prefix}{text} (code {code})")


class AuthenticationRequired(EitaaError):
    """Raised when a command needs an active saved token."""


class PeerResolutionError(EitaaError):
    """Raised when a user/chat/channel reference cannot be resolved."""
