from __future__ import annotations

from typing import Any

import pytest

from eitaa_cli.models.search import (
    ChatSearchFilter,
    GlobalSearchFilter,
    GlobalSearchScope,
    ParticipantFilter,
    SearchCursor,
    TopPeerCategory,
)
from eitaa_cli.services.search import SearchService, next_search_cursor


class FakePeers:
    async def resolve(self, reference: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(reference, dict):
            return reference
        if reference == "room":
            return {"_": "inputPeerChannel", "channel_id": 42, "access_hash": 99}
        if reference == "sender":
            return {"_": "inputPeerUser", "user_id": 7, "access_hash": 8}
        raise AssertionError(reference)

    async def resolve_input_channel(
        self, reference: str | dict[str, Any]
    ) -> dict[str, Any]:
        peer = await self.resolve(reference)
        return {
            "_": "inputChannel",
            "channel_id": peer["channel_id"],
            "access_hash": peer["access_hash"],
        }


class FakeSearchClient:
    def __init__(self) -> None:
        self.peers = FakePeers()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, params))
        return {"_": "messages.messages", "messages": [], "users": [], "chats": []}


@pytest.mark.asyncio
async def test_global_search_uses_recovered_scope_and_media_flags() -> None:
    client = FakeSearchClient()
    await SearchService(client).global_messages(  # type: ignore[arg-type]
        "release",
        scope=GlobalSearchScope.GLOBAL,
        content_filter=GlobalSearchFilter.IMAGE,
        limit=26,
        cursor=SearchCursor(
            offset_date=100,
            offset_peer={"_": "inputPeerChannel", "channel_id": 42, "access_hash": 99},
            offset_id=5,
        ),
    )

    method, params = client.calls[0]
    assert method == "messages.searchGlobalExt"
    assert params == {
        "flags": 262146,
        "q": "release",
        "limit": 26,
        "offset_date": 100,
        "offset_peer": {"_": "inputPeerChannel", "channel_id": 42, "access_hash": 99},
        "offset_id": 5,
    }


@pytest.mark.asyncio
async def test_chat_search_supports_sender_dates_and_missed_call_filter() -> None:
    client = FakeSearchClient()
    await SearchService(client).in_chat_messages(  # type: ignore[arg-type]
        "room",
        "",
        content_filter=ChatSearchFilter.MISSED_CALLS,
        from_reference="sender",
        min_date=10,
        max_date=20,
        limit=30,
    )

    method, params = client.calls[0]
    assert method == "messages.search"
    assert params["filter"] == {"_": "inputMessagesFilterPhoneCalls", "missed": True}
    assert params["from_id"] == {"_": "inputPeerUser", "user_id": 7, "access_hash": 8}
    assert params["min_date"] == 10
    assert params["max_date"] == 20


@pytest.mark.asyncio
async def test_top_peer_categories_set_the_correct_tl_flags() -> None:
    client = FakeSearchClient()
    await SearchService(client).top_peers(  # type: ignore[arg-type]
        [TopPeerCategory.CORRESPONDENTS, TopPeerCategory.GROUPS, TopPeerCategory.CHANNELS],
        limit=40,
    )

    assert client.calls[0] == (
        "contacts.getTopPeers",
        {
            "offset": 0,
            "limit": 40,
            "hash": 0,
            "correspondents": True,
            "groups": True,
            "channels": True,
        },
    )


@pytest.mark.asyncio
async def test_participant_search_builds_the_typed_filter() -> None:
    client = FakeSearchClient()
    await SearchService(client).participants(  # type: ignore[arg-type]
        "room",
        participant_filter=ParticipantFilter.SEARCH,
        query="ali",
        offset=20,
        limit=100,
    )

    assert client.calls[0] == (
        "channels.getParticipants",
        {
            "channel": {"_": "inputChannel", "channel_id": 42, "access_hash": 99},
            "filter": {"_": "channelParticipantsSearch", "q": "ali"},
            "offset": 20,
            "limit": 100,
            "hash": 0,
        },
    )


def test_next_search_cursor_uses_the_last_message_and_entity_access_hash() -> None:
    cursor = next_search_cursor(
        {
            "messages": [
                {
                    "_": "message",
                    "id": 55,
                    "date": 1234,
                    "peer_id": {"_": "peerChannel", "channel_id": 42},
                }
            ],
            "chats": [
                {"_": "channel", "id": 42, "access_hash": 99, "title": "Example"}
            ],
            "users": [],
        }
    )

    assert cursor == SearchCursor(
        offset_date=1234,
        offset_peer={"_": "inputPeerChannel", "channel_id": 42, "access_hash": 99},
        offset_id=55,
    )
