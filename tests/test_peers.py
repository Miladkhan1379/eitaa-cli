from __future__ import annotations

from typing import Any

import pytest

from eitaa_cli.services.peers import PeerResolver


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, params))
        if method == "contacts.resolveUsername":
            return {
                "_": "contacts.resolvedPeer",
                "peer": {"_": "peerChannel", "channel_id": 42},
                "chats": [
                    {
                        "_": "channel",
                        "id": 42,
                        "access_hash": 99,
                        "title": "Example",
                    }
                ],
                "users": [],
            }
        raise AssertionError(method)


@pytest.mark.asyncio
async def test_username_url_resolves_to_input_channel() -> None:
    resolver = PeerResolver(FakeClient())  # type: ignore[arg-type]
    result = await resolver.resolve("https://eitaa.com/example")
    assert result == {"_": "inputPeerChannel", "channel_id": 42, "access_hash": 99}
