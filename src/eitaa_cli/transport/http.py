from __future__ import annotations

import random
from collections.abc import Iterable

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
                "user-agent": "eitaa-cli/0.1 (Python; Eitaa Web compatible)",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def post(self, payload: bytes, *, kind: str = "client") -> bytes:
        errors: list[str] = []
        endpoints = list(self.settings.endpoints(kind))
        random.shuffle(endpoints)
        for endpoint in endpoints:
            try:
                response = await self._client.post(endpoint, content=payload)
                if response.status_code != 200:
                    errors.append(f"{endpoint}: HTTP {response.status_code}")
                    continue
                if not response.content:
                    errors.append(f"{endpoint}: empty response")
                    continue
                return response.content
            except httpx.HTTPError as exc:
                errors.append(f"{endpoint}: {exc.__class__.__name__}: {exc}")
        detail = "; ".join(errors) or "no endpoints configured"
        raise EitaaTransportError(f"all Eitaa {kind} endpoints failed: {detail}")

    @staticmethod
    def redact_endpoints(endpoints: Iterable[str]) -> list[str]:
        return [endpoint.split("/eitaa", 1)[0] for endpoint in endpoints]
