from __future__ import annotations

from typing import Any

import pytest

from eitaa_cli.services.dialogs import DialogsService


def make_page(
    *,
    dialogs: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    users: list[dict[str, Any]] | None = None,
    chats: list[dict[str, Any]] | None = None,
    count: int = 0,
) -> dict[str, Any]:
    return {
        "_": "messages.dialogsSlice",
        "count": count,
        "dialogs": dialogs,
        "messages": messages,
        "users": users or [],
        "chats": chats or [],
    }


def channel_dialog(
    channel_id: int,
    message_id: int,
) -> dict[str, Any]:
    return {
        "_": "dialog",
        "peer": {
            "_": "peerChannel",
            "channel_id": channel_id,
        },
        "top_message": message_id,
        "unread_count": 0,
    }


def user_dialog(
    user_id: int,
    message_id: int,
) -> dict[str, Any]:
    return {
        "_": "dialog",
        "peer": {
            "_": "peerUser",
            "user_id": user_id,
        },
        "top_message": message_id,
        "unread_count": 0,
    }


def channel_entity(channel_id: int) -> dict[str, Any]:
    return {
        "_": "channel",
        "id": channel_id,
        "title": f"Channel {channel_id}",
        "broadcast": True,
        "access_hash": 100000 + channel_id,
    }


def user_entity(user_id: int) -> dict[str, Any]:
    return {
        "_": "user",
        "id": user_id,
        "first_name": f"User {user_id}",
        "access_hash": 200000 + user_id,
    }


def message(
    *,
    message_id: int,
    peer: dict[str, Any],
    date: int,
) -> dict[str, Any]:
    return {
        "_": "message",
        "id": message_id,
        "peer_id": peer,
        "date": date,
        "message": f"message {message_id}",
    }


def empty_page(count: int = 0) -> dict[str, Any]:
    return make_page(
        dialogs=[],
        messages=[],
        count=count,
    )


class PaginatedFakeClient:
    def __init__(
        self,
        pages: dict[int, dict[str, Any]],
    ) -> None:
        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    async def invoke(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert method == "messages.getDialogs"

        params = dict(params or {})
        self.calls.append(params)

        offset_id = params.get("offset_id", 0)

        return self.pages.get(
            offset_id,
            empty_page(),
        )


@pytest.mark.asyncio
async def test_channels_continue_fetching_until_requested_channel_limit() -> None:
    page_one = make_page(
        count=4,
        dialogs=[
            user_dialog(1, 101),
            channel_dialog(10, 102),
        ],
        messages=[
            message(
                message_id=101,
                peer={"_": "peerUser", "user_id": 1},
                date=2001,
            ),
            message(
                message_id=102,
                peer={"_": "peerChannel", "channel_id": 10},
                date=2000,
            ),
        ],
        users=[
            user_entity(1),
        ],
        chats=[
            channel_entity(10),
        ],
    )

    page_two = make_page(
        count=4,
        dialogs=[
            user_dialog(2, 201),
            channel_dialog(20, 202),
        ],
        messages=[
            message(
                message_id=201,
                peer={"_": "peerUser", "user_id": 2},
                date=1001,
            ),
            message(
                message_id=202,
                peer={"_": "peerChannel", "channel_id": 20},
                date=1000,
            ),
        ],
        users=[
            user_entity(2),
        ],
        chats=[
            channel_entity(20),
        ],
    )

    client = PaginatedFakeClient(
        {
            0: page_one,
            102: page_two,
        }
    )

    result = await DialogsService(client).channels(2)  # type: ignore[arg-type]

    assert len(result["dialogs"]) == 2

    assert [
        chat["id"]
        for chat in result["chats"]
    ] == [10, 20]

    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_pagination_stops_when_server_returns_empty_page() -> None:
    page_one = make_page(
        count=10,
        dialogs=[
            channel_dialog(10, 102),
        ],
        messages=[
            message(
                message_id=102,
                peer={"_": "peerChannel", "channel_id": 10},
                date=2000,
            ),
        ],
        chats=[
            channel_entity(10),
        ],
    )

    client = PaginatedFakeClient(
        {
            0: page_one,
            102: empty_page(count=10),
        }
    )

    result = await DialogsService(client).channels(5)  # type: ignore[arg-type]

    assert len(result["dialogs"]) == 1
    assert result["chats"][0]["id"] == 10

    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_duplicate_dialogs_are_not_returned_twice() -> None:
    page_one = make_page(
        count=3,
        dialogs=[
            channel_dialog(10, 102),
        ],
        messages=[
            message(
                message_id=102,
                peer={"_": "peerChannel", "channel_id": 10},
                date=2000,
            ),
        ],
        chats=[
            channel_entity(10),
        ],
    )

    page_two = make_page(
        count=3,
        dialogs=[
            channel_dialog(10, 102),
            channel_dialog(20, 202),
        ],
        messages=[
            message(
                message_id=102,
                peer={"_": "peerChannel", "channel_id": 10},
                date=2000,
            ),
            message(
                message_id=202,
                peer={"_": "peerChannel", "channel_id": 20},
                date=1000,
            ),
        ],
        chats=[
            channel_entity(10),
            channel_entity(20),
        ],
    )

    client = PaginatedFakeClient(
        {
            0: page_one,
            102: page_two,
        }
    )

    result = await DialogsService(client).channels(2)  # type: ignore[arg-type]

    assert len(result["dialogs"]) == 2

    assert {
        chat["id"]
        for chat in result["chats"]
    } == {10, 20}


@pytest.mark.asyncio
async def test_requested_limit_is_applied_after_filtering() -> None:
    page_one = make_page(
        count=4,
        dialogs=[
            channel_dialog(10, 101),
            channel_dialog(20, 102),
            channel_dialog(30, 103),
        ],
        messages=[
            message(
                message_id=101,
                peer={"_": "peerChannel", "channel_id": 10},
                date=3000,
            ),
            message(
                message_id=102,
                peer={"_": "peerChannel", "channel_id": 20},
                date=2000,
            ),
            message(
                message_id=103,
                peer={"_": "peerChannel", "channel_id": 30},
                date=1000,
            ),
        ],
        chats=[
            channel_entity(10),
            channel_entity(20),
            channel_entity(30),
        ],
    )

    client = PaginatedFakeClient(
        {
            0: page_one,
        }
    )

    result = await DialogsService(client).channels(2)  # type: ignore[arg-type]

    assert len(result["dialogs"]) == 2

    assert [
        chat["id"]
        for chat in result["chats"]
    ] == [10, 20]

    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_repeated_cursor_does_not_loop_forever() -> None:
    repeated_page = make_page(
        count=100,
        dialogs=[
            channel_dialog(10, 102),
        ],
        messages=[
            message(
                message_id=102,
                peer={"_": "peerChannel", "channel_id": 10},
                date=2000,
            ),
        ],
        chats=[
            channel_entity(10),
        ],
    )

    client = PaginatedFakeClient(
        {
            0: repeated_page,
            102: repeated_page,
        }
    )

    result = await DialogsService(client).channels(5)  # type: ignore[arg-type]

    assert len(result["dialogs"]) == 1

    # First request + one repeated-cursor request.
    # The service must then stop instead of entering an infinite loop.
    assert len(client.calls) == 2