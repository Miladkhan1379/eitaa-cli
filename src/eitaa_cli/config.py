from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from eitaa_cli.api_types import TransportKind
from eitaa_cli.transport.profile import WebClientProfile

CLIENT_ENDPOINTS = (
    "https://hasan.eitaa.ir/eitaa/",
    "https://hosna.eitaa.com/eitaa/",
    "https://armita.eitaa.com/eitaa/",
    "https://majid.eitaa.com/eitaa/",
    "https://alireza.eitaa.com/eitaa/",
    "https://mostafa.eitaa.com/eitaa/",
    "https://sajad.eitaa.ir/eitaa/",
    "https://bagher.eitaa.ir/eitaa/",
    "https://sadegh.eitaa.ir/eitaa/",
    "https://kazem.eitaa.ir/eitaa/",
)
DOWNLOAD_ENDPOINTS = (
    "https://mohsen.eitaa.com/eitaa/",
    "https://ghasem.eitaa.com/eitaa/",
    "https://hadi.eitaa.com/eitaa/",
    "https://hossein.eitaa.com/eitaa/",
    "https://vahid.eitaa.com/eitaa/",
)
UPLOAD_ENDPOINTS = (
    "https://alzheimer.eitaa.com/eitaa/",
    "https://fateme.eitaa.com/eitaa/",
    "https://ali.eitaa.com/eitaa/",
    "https://meysam.eitaa.com/eitaa/",
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(slots=True)
class EitaaSettings:
    """Runtime settings matching Eitaa Web build 4.6.12, API layer 135."""

    api_id: int = field(default_factory=lambda: _env_int("EITAA_API_ID", 2496))
    api_hash: str = field(
        default_factory=lambda: os.getenv("EITAA_API_HASH", "8da85b0d5bfe62527e5b244c209159c3")
    )
    layer: int = field(default_factory=lambda: _env_int("EITAA_LAYER", 135))
    flags: int = 32
    app_version: str = "4.6.12 K"
    build_version: int = 2496
    timeout: float = field(default_factory=lambda: float(os.getenv("EITAA_TIMEOUT", "45")))
    profile: str | None = field(default_factory=lambda: os.getenv("EITAA_PROFILE") or None)
    session_file: Path = field(
        default_factory=lambda: Path(
            os.getenv("EITAA_SESSION_FILE", "~/.config/eitaa-cli/sessions.json")
        ).expanduser()
    )
    endpoint: str | None = field(default_factory=lambda: os.getenv("EITAA_ENDPOINT") or None)
    http2: bool = field(default_factory=lambda: _env_bool("EITAA_HTTP2", True))
    web_profile: WebClientProfile = field(default_factory=WebClientProfile)

    def __post_init__(self) -> None:
        if self.api_id <= 0:
            raise ValueError("api_id must be positive")
        if not self.api_hash.strip():
            raise ValueError("api_hash cannot be empty")
        if self.layer <= 0:
            raise ValueError("layer must be positive")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    def endpoints(self, kind: TransportKind) -> tuple[str, ...]:
        if self.endpoint:
            return (self.endpoint,)
        if kind == "download":
            return DOWNLOAD_ENDPOINTS
        if kind == "upload":
            return UPLOAD_ENDPOINTS
        return CLIENT_ENDPOINTS
