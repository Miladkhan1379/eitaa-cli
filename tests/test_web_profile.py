from __future__ import annotations

from eitaa_cli.config import EitaaSettings
from eitaa_cli.transport.profile import WebClientProfile

_FORBIDDEN_MARKERS = ("eitaa-cli", "python", "httpx")


def test_default_request_profile_contains_no_runtime_branding() -> None:
    headers = WebClientProfile().headers()
    serialized = "\n".join(f"{key}: {value}" for key, value in headers.items()).casefold()

    assert headers["origin"] == "https://web.eitaa.com"
    assert headers["sec-fetch-mode"] == "cors"
    assert all(marker not in serialized for marker in _FORBIDDEN_MARKERS)


def test_signup_metadata_matches_the_web_profile_without_runtime_branding() -> None:
    profile = WebClientProfile()
    app_info = profile.app_info(build_version=2496, app_version="4.6.12 K")
    serialized = repr(app_info).casefold()

    assert app_info == {
        "_": "eitaaAppInfo",
        "build_version": 2496,
        "device_model": profile.user_agent,
        "system_version": "Linux x86_64",
        "app_version": "4.6.12 K",
        "lang_code": "en",
        "sign": "",
    }
    assert all(marker not in serialized for marker in _FORBIDDEN_MARKERS)


def test_http2_is_enabled_by_default() -> None:
    assert EitaaSettings().http2 is True
