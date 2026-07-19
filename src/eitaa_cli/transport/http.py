from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from eitaa_cli.config import EitaaSettings
from eitaa_cli.errors import EitaaTransportError


class HttpTransport:
    """Async binary POST transport with Eitaa Web-compatible endpoint failover."""

    def __init__(self, settings: EitaaSettings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=settings.timeout,
            follow_redirects=False,
            headers={
                "accept": "*/*",
                "content-type": "application/octet-stream",
                "origin": "https://web.eitaa.com",
                "referer": "https://web.eitaa.com/",
                "user-agent": "eitaa-cli/0.4 (Python; Eitaa Web compatible)",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def post(self, payload: bytes, *, kind: str = "client") -> bytes:
        errors: list[str] = []
        retry_delays: list[int] = []
        endpoints = list(self.settings.endpoints(kind))
        random.shuffle(endpoints)
        for endpoint in endpoints:
            try:
                response = await self._client.post(endpoint, content=payload)
                if response.status_code != 200:
                    retry_after = _retry_after_seconds(response.headers.get("retry-after"))
                    if retry_after is not None:
                        retry_delays.append(retry_after)
                        errors.append(
                            f"{endpoint}: HTTP {response.status_code}, retry after {retry_after}s"
                        )
                    else:
                        errors.append(f"{endpoint}: HTTP {response.status_code}")
                    continue
                if not response.content:
                    errors.append(f"{endpoint}: empty response")
                    continue
                return response.content
            except httpx.TimeoutException as exc:
                errors.append(f"{endpoint}: timeout: {exc}")
            except httpx.ConnectError as exc:
                errors.append(f"{endpoint}: connection failed: {exc}")
            except httpx.HTTPError as exc:
                errors.append(f"{endpoint}: {exc.__class__.__name__}: {exc}")
        detail = "; ".join(errors) or "no endpoints configured"
        raise EitaaTransportError(
            f"all Eitaa {kind} endpoints failed: {detail}",
            retry_after_seconds=max(retry_delays, default=None),
        )

    @staticmethod
    def redact_endpoints(endpoints: Iterable[str]) -> list[str]:
        return [endpoint.split("/eitaa", 1)[0] for endpoint in endpoints]


def _retry_after_seconds(value: str | None) -> int | None:
    """Parse an HTTP Retry-After delta or date without guessing."""

    if not value:
        return None
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    try:
        target = parsedate_to_datetime(stripped)
    except (TypeError, ValueError, OverflowError):
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    delay = int((target - datetime.now(UTC)).total_seconds())
    return max(0, delay)
