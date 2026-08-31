from __future__ import annotations

from typing import Any

import pytest

from eitaa_cli.services.extras import ExtrasService


class FakePeers:
    async def resolve(self, reference: Any) -> dict[str, Any]:
        if reference == "channel":
            return {"_": "inputPeerChannel", "channel_id": 10, "access_hash": 20}
        return {"_": "inputPeerUser", "user_id": 1, "access_hash": 2}


class FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def history(self, peer: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        offset = int(kwargs.get("offset_id", 0))
        if offset == 0:
            ids = [5, 4]
        elif offset == 4:
            ids = [3, 2]
        elif offset == 2:
            ids = [1]
        else:
            ids = []
        return {
            "_": "messages.messages",
            "messages": [
                {"_": "message", "id": item, "date": item, "message": str(item)}
                for item in ids
            ],
            "users": [],
            "chats": [],
        }


class FakeMedia:
    pass


class FakeClient:
    def __init__(self) -> None:
        self.peers = FakePeers()
        self.messages = FakeMessages()
        self.media = FakeMedia()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, method: str, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        payload = dict(params or {})
        self.calls.append((method, payload))
        return {"_": "updates"}


@pytest.mark.asyncio
async def test_schedule_text_uses_server_schedule_date() -> None:
    client = FakeClient()
    await ExtrasService(client).schedule_text("user", "hello", schedule_date=123456789)
    method, params = client.calls[-1]
    assert method == "messages.sendMessage"
    assert params["schedule_date"] == 123456789
    assert params["message"] == "hello"


@pytest.mark.asyncio
async def test_mark_read_uses_channel_method_for_channels() -> None:
    client = FakeClient()
    await ExtrasService(client).mark_read("channel", max_id=77)
    method, params = client.calls[-1]
    assert method == "channels.readHistory"
    assert params["max_id"] == 77
    assert params["channel"]["channel_id"] == 10


@pytest.mark.asyncio
async def test_iter_history_paginates_until_limit() -> None:
    client = FakeClient()
    messages = [
        item
        async for item in ExtrasService(client).iter_history(
            "user", limit=5, page_size=2
        )
    ]
    assert [item["id"] for item in messages] == [5, 4, 3, 2, 1]
    assert [call["offset_id"] for call in client.messages.calls] == [0, 4, 2]
