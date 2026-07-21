from __future__ import annotations

import os
from dataclasses import dataclass, field

from eitaa_cli.api_types import BrowserHeaders, EitaaAppInfo

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0"
)


@dataclass(frozen=True, slots=True)
class WebClientProfile:
    """Stable HTTP and app metadata used by the captured Eitaa web client.

    The profile is intentionally static and configurable. It is not rotated and
    does not attempt to reproduce browser TLS or JavaScript fingerprints.
    """

    user_agent: str = field(
        default_factory=lambda: os.getenv("EITAA_WEB_USER_AGENT", _DEFAULT_USER_AGENT)
    )
    accept_language: str = field(
        default_factory=lambda: os.getenv("EITAA_WEB_ACCEPT_LANGUAGE", "en,de-DE;q=0.9,en-US;q=0.8")
    )
    origin: str = field(
        default_factory=lambda: os.getenv("EITAA_WEB_ORIGIN", "https://web.eitaa.com")
    )
    system_version: str = field(
        default_factory=lambda: os.getenv("EITAA_WEB_SYSTEM_VERSION", "Linux x86_64")
    )
    language_code: str = field(default_factory=lambda: os.getenv("EITAA_WEB_LANGUAGE_CODE", "en"))

    def headers(self) -> BrowserHeaders:
        return {
            "accept": "*/*",
            "accept-language": self.accept_language,
            "origin": self.origin,
            "sec-gpc": "1",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": self.user_agent,
        }

    def app_info(self, *, build_version: int, app_version: str) -> EitaaAppInfo:
        return {
            "_": "eitaaAppInfo",
            "build_version": build_version,
            "device_model": self.user_agent,
            "system_version": self.system_version,
            "app_version": app_version,
            "lang_code": self.language_code,
            "sign": "",
        }
