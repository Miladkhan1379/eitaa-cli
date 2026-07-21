from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import cast

import httpx

from eitaa_cli.api_types import TransportKind
from eitaa_cli.config import EitaaSettings
from eitaa_cli.errors import EitaaTransportError


class HttpTransport:
    """Asynchronous binary POST transport with endpoint failover."""

    def __init__(
        self,
        settings: EitaaSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.timeout),
            follow_redirects=False,
            http2=settings.http2,
            headers=cast(Mapping[str, str], settings.web_profile.headers()),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def post(self, payload: bytes, *, kind: TransportKind = "client") -> bytes:
        errors: list[str] = []
        retry_delays: list[int] = []
        endpoints = _shuffled(self.settings.endpoints(kind))

        for endpoint in endpoints:
            try:
                response = await self._client.post(endpoint, content=payload)
            except httpx.TimeoutException as exc:
                errors.append(f"{endpoint}: timeout: {exc}")
                continue
            except httpx.ConnectError as exc:
                errors.append(f"{endpoint}: connection failed: {exc}")
                continue
            except httpx.HTTPError as exc:
                errors.append(f"{endpoint}: {exc.__class__.__name__}: {exc}")
                continue

            if response.status_code != httpx.codes.OK:
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

        detail = "; ".join(errors) or "no endpoints configured"
        raise EitaaTransportError(
            f"all Eitaa {kind} endpoints failed: {detail}",
            retry_after_seconds=max(retry_delays, default=None),
        )

    @staticmethod
    def redact_endpoints(endpoints: Iterable[str]) -> list[str]:
        return [endpoint.split("/eitaa", 1)[0] for endpoint in endpoints]


def _shuffled(endpoints: tuple[str, ...]) -> tuple[str, ...]:
    if len(endpoints) < 2:
        return endpoints
    return tuple(random.SystemRandom().sample(endpoints, len(endpoints)))


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
