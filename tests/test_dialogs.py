from __future__ import annotations

from typing import Any

import pytest

from eitaa_cli.services.dialogs import DialogsService, entity_kind, filter_dialog_result


def sample_dialogs() -> dict[str, Any]:
    return {
        "_": "messages.dialogs",
        "dialogs": [
            {"_": "dialog", "peer": {"_": "peerUser", "user_id": 1}, "top_message": 11, "unread_count": 2},
            {"_": "dialog", "peer": {"_": "peerChat", "chat_id": 2}, "top_message": 12, "unread_count": 0},
            {"_": "dialog", "peer": {"_": "peerChannel", "channel_id": 3}, "top_message": 13, "unread_count": 4},
            {"_": "dialog", "peer": {"_": "peerChannel", "channel_id": 4}, "top_message": 14, "unread_count": 0},
        ],
        "messages": [
            {"_": "message", "id": 11, "message": "private"},
            {"_": "message", "id": 12, "message": "group"},
            {"_": "message", "id": 13, "message": "supergroup"},
            {"_": "message", "id": 14, "message": "channel"},
        ],
        "users": [{"_": "user", "id": 1, "first_name": "Ali", "access_hash": 101}],
        "chats": [
            {"_": "chat", "id": 2, "title": "Project Room"},
            {"_": "channel", "id": 3, "title": "Engineering", "megagroup": True, "access_hash": 103},
            {"_": "channel", "id": 4, "title": "News", "broadcast": True, "access_hash": 104},
        ],
    }


def test_entity_kind_distinguishes_supergroups_from_channels() -> None:
    assert entity_kind({"_": "user"}) == "private"
    assert entity_kind({"_": "chat"}) == "group"
    assert entity_kind({"_": "channel", "megagroup": True}) == "supergroup"
    assert entity_kind({"_": "channel", "broadcast": True}) == "channel"


def test_filter_dialogs_selects_groups_and_prunes_related_collections() -> None:
    result = filter_dialog_result(sample_dialogs(), kinds={"group", "supergroup"})
    assert [item["top_message"] for item in result["dialogs"]] == [12, 13]
    assert [item["id"] for item in result["messages"]] == [12, 13]
    assert result["users"] == []
    assert [item["id"] for item in result["chats"]] == [2, 3]


def test_filter_dialogs_supports_query_and_unread_only() -> None:
    result = filter_dialog_result(
        sample_dialogs(),
        kinds={"private", "group", "supergroup", "channel"},
        query="engineering",
        unread_only=True,
    )
    assert len(result["dialogs"]) == 1
    assert result["chats"][0]["id"] == 3


class FakePeers:
    async def resolve(self, reference: str) -> dict[str, Any]:
        assert reference == "channel:3:103"
        return {"_": "inputPeerChannel", "channel_id": 3, "access_hash": 103}


class FakeClient:
    def __init__(self) -> None:
        self.peers = FakePeers()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, params))
        return {"_": "messages.chatFull"}


@pytest.mark.asyncio
async def test_dialog_info_uses_full_channel_for_supergroups_and_channels() -> None:
    client = FakeClient()
    result = await DialogsService(client).info("channel:3:103")  # type: ignore[arg-type]
    assert result["_"] == "messages.chatFull"
    assert client.calls == [
        (
            "channels.getFullChannel",
            {"channel": {"_": "inputChannel", "channel_id": 3, "access_hash": 103}},
        )
    ]
