from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from eitaa_cli.api_types import (
    DialogObject,
    DialogsResponse,
    EntityObject,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
    MessageObject,
    PeerKey,
    PeerReference,
    TLObject,
    int_field,
    object_field,
    object_list,
)
from eitaa_cli.rpc import ServiceClient, invoke_object
from eitaa_cli.errors import PeerResolutionError
from eitaa_cli.services.peers import entity_to_input_peer, peer_key

DIALOG_KINDS = frozenset({"private", "group", "supergroup", "channel"})


class DialogsService:
    """Read and filter the user's conversation list."""

    def __init__(self, client: ServiceClient) -> None:
        self.client = client

    async def list(
        self,
        limit: int = 50,
        *,
        folder_id: int | None = None,
        kinds: Iterable[str] | None = None,
        query: str | None = None,
        unread_only: bool = False,
    ) -> DialogsResponse:
        if limit < 1:
            raise ValueError("limit must be positive")

        selected_kinds = set(kinds or DIALOG_KINDS)
        unknown = selected_kinds - DIALOG_KINDS
        if unknown:
            raise ValueError(
                f"unknown dialog kind(s): {', '.join(sorted(unknown))}"
            )

        page_size = min(max(limit, 1), 100)

        offset_date = 0
        offset_id = 0
        offset_peer: TLObject = {"_": "inputPeerEmpty"}

        combined: DialogsResponse = {
            "_": "messages.dialogs",
            "dialogs": [],
            "messages": [],
            "users": [],
            "chats": [],
        }

        seen_cursors: set[tuple[int, int, str]] = set()
        seen_dialogs: set[PeerKey] = set()
        seen_users: set[int] = set()
        seen_chats: set[tuple[str, int]] = set()
        seen_messages: set[tuple[PeerKey, int]] = set()

        total_count: int | None = None

        while True:
            params: TLObject = {
                "offset_date": offset_date,
                "offset_id": offset_id,
                "offset_peer": offset_peer,
                "limit": page_size,
                "hash": 0,
            }

            if folder_id is not None:
                params["folder_id"] = folder_id

            page = cast(
                DialogsResponse,
                await invoke_object(
                    self.client,
                    "messages.getDialogs",
                    params,
                ),
            )

            if total_count is None and "count" in page:
                total_count = page.get("count", 0)

            page_dialogs = page.get("dialogs", [])
            if not page_dialogs:
                return filter_dialog_result(
                    combined,
                    kinds=selected_kinds,
                    query=query,
                    unread_only=unread_only,
                )

            _merge_dialog_page(
                combined,
                page,
                seen_dialogs=seen_dialogs,
                seen_users=seen_users,
                seen_chats=seen_chats,
                seen_messages=seen_messages,
            )

            if total_count is not None:
                combined["count"] = total_count

            filtered = filter_dialog_result(
                combined,
                kinds=selected_kinds,
                query=query,
                unread_only=unread_only,
            )

            if len(filtered.get("dialogs", [])) >= limit:
                return _slice_dialog_result(filtered, limit)

            if total_count is not None and len(seen_dialogs) >= total_count:
                return filtered

            cursor = _next_dialog_cursor(page)
            if cursor is None:
                return filtered

            next_offset_date, next_offset_id, next_offset_peer = cursor

            cursor_key = (
                next_offset_date,
                next_offset_id,
                repr(next_offset_peer),
            )

            if cursor_key in seen_cursors:
                return filtered

            seen_cursors.add(cursor_key)

            offset_date = next_offset_date
            offset_id = next_offset_id
            offset_peer = next_offset_peer

    async def private(
        self,
        limit: int = 50,
        *,
        folder_id: int | None = None,
        query: str | None = None,
        unread_only: bool = False,
    ) -> DialogsResponse:
        return await self.list(
            limit,
            folder_id=folder_id,
            kinds={"private"},
            query=query,
            unread_only=unread_only,
        )

    async def groups(
        self,
        limit: int = 50,
        *,
        folder_id: int | None = None,
        query: str | None = None,
        unread_only: bool = False,
    ) -> DialogsResponse:
        return await self.list(
            limit,
            folder_id=folder_id,
            kinds={"group", "supergroup"},
            query=query,
            unread_only=unread_only,
        )

    async def channels(
        self,
        limit: int = 50,
        *,
        folder_id: int | None = None,
        query: str | None = None,
        unread_only: bool = False,
    ) -> DialogsResponse:
        return await self.list(
            limit,
            folder_id=folder_id,
            kinds={"channel"},
            query=query,
            unread_only=unread_only,
        )

    async def info(self, reference: PeerReference) -> TLObject:
        peer = await self.client.peers.resolve(reference)
        predicate = peer["_"]
        if predicate == "inputPeerSelf":
            return await invoke_object(
                self.client, "users.getFullUser", {"id": {"_": "inputUserSelf"}}
            )
        if predicate == "inputPeerUser":
            user = cast(InputPeerUser, peer)
            return await invoke_object(
                self.client,
                "users.getFullUser",
                {
                    "id": {
                        "_": "inputUser",
                        "user_id": user["user_id"],
                        "access_hash": user["access_hash"],
                    }
                },
            )
        if predicate == "inputPeerChat":
            chat = cast(InputPeerChat, peer)
            return await invoke_object(
                self.client, "messages.getFullChat", {"chat_id": chat["chat_id"]}
            )
        if predicate == "inputPeerChannel":
            channel = cast(InputPeerChannel, peer)
            return await invoke_object(
                self.client,
                "channels.getFullChannel",
                {
                    "channel": {
                        "_": "inputChannel",
                        "channel_id": channel["channel_id"],
                        "access_hash": channel["access_hash"],
                    }
                },
            )
        raise ValueError(f"unsupported peer type: {predicate!r}")

def _merge_dialog_page(
    target: DialogsResponse,
    page: DialogsResponse,
    *,
    seen_dialogs: set[PeerKey],
    seen_users: set[int],
    seen_chats: set[tuple[str, int]],
    seen_messages: set[tuple[PeerKey, int]],
) -> None:
    for dialog in page.get("dialogs", []):
        key = peer_key(object_field(cast(TLObject, dialog), "peer"))

        if key in seen_dialogs:
            continue

        seen_dialogs.add(key)
        target["dialogs"].append(dialog)

    for user in page.get("users", []):
        identifier = user.get("id", 0)

        if identifier in seen_users:
            continue

        seen_users.add(identifier)
        target["users"].append(user)

    for chat in page.get("chats", []):
        kind = (
            "channel"
            if chat.get("_") in {"channel", "channelForbidden"}
            else "chat"
        )
        key = (kind, chat.get("id", 0))

        if key in seen_chats:
            continue

        seen_chats.add(key)
        target["chats"].append(chat)

    for message in page.get("messages", []):
        message_object = cast(TLObject, message)

        try:
            message_peer = object_field(message_object, "peer_id")
            key = peer_key(message_peer)
        except (KeyError, TypeError, ValueError):
            key = ("unknown", 0)

        message_key = (
            key,
            int_field(message_object, "id"),
        )

        if message_key in seen_messages:
            continue

        seen_messages.add(message_key)
        target["messages"].append(message)


def _next_dialog_cursor(
    page: DialogsResponse,
) -> tuple[int, int, TLObject] | None:
    dialogs = page.get("dialogs", [])

    if not dialogs:
        return None

    last_dialog = dialogs[-1]
    last_dialog_object = cast(TLObject, last_dialog)

    peer = object_field(last_dialog_object, "peer")
    key = peer_key(peer)

    top_message_id = int_field(
        last_dialog_object,
        "top_message",
    )

    offset_date = 0

    for message in object_list(
        cast(TLObject, page),
        "messages",
    ):
        if int_field(message, "id") != top_message_id:
            continue

        try:
            message_peer = object_field(message, "peer_id")
        except (KeyError, TypeError, ValueError):
            continue

        if peer_key(message_peer) != key:
            continue

        offset_date = int_field(message, "date")
        break

    entities = dialog_entity_map(page)
    entity = entities.get(key)

    offset_peer: TLObject = {"_": "inputPeerEmpty"}

    if entity is not None:
        try:
            offset_peer = cast(
                TLObject,
                entity_to_input_peer(entity),
            )
        except PeerResolutionError:
            # Some incomplete/forbidden entities may not expose
            # the access hash required for an input peer.
            offset_peer = {"_": "inputPeerEmpty"}

    return offset_date, top_message_id, offset_peer


def _slice_dialog_result(
    result: DialogsResponse,
    limit: int,
) -> DialogsResponse:
    dialogs = result.get("dialogs", [])[:limit]

    selected_keys: set[PeerKey] = set()
    selected_message_ids: set[int] = set()

    for dialog in dialogs:
        dialog_object = cast(TLObject, dialog)

        selected_keys.add(
            peer_key(
                object_field(
                    dialog_object,
                    "peer",
                )
            )
        )

        selected_message_ids.add(
            int_field(
                dialog_object,
                "top_message",
            )
        )

    sliced: DialogsResponse = {
        "_": result.get("_", "messages.dialogs"),
        "dialogs": dialogs,
        "users": [
            user
            for user in result.get("users", [])
            if ("user", user.get("id", 0))
            in selected_keys
        ],
        "chats": [
            chat
            for chat in result.get("chats", [])
            if (
                (
                    "channel"
                    if chat.get("_")
                    in {"channel", "channelForbidden"}
                    else "chat"
                ),
                chat.get("id", 0),
            )
            in selected_keys
        ],
        "messages": [
            cast(MessageObject, message)
            for message in object_list(
                cast(TLObject, result),
                "messages",
            )
            if int_field(message, "id")
            in selected_message_ids
        ],
    }

    sliced["count"] = len(dialogs)

    return sliced

def entity_kind(entity: EntityObject) -> str:
    predicate = entity.get("_")
    if predicate in {"user", "userEmpty"}:
        return "private"
    if predicate in {"chat", "chatEmpty", "chatForbidden"}:
        return "group"
    if predicate in {"channel", "channelForbidden"}:
        if entity.get("megagroup") or entity.get("gigagroup"):
            return "supergroup"
        return "channel"
    return "unknown"


def dialog_entity_map(result: DialogsResponse) -> dict[PeerKey, EntityObject]:
    entities: dict[PeerKey, EntityObject] = {}
    for user in result.get("users", []):
        entities[("user", user.get("id", 0))] = user
    for chat in result.get("chats", []):
        kind = "channel" if chat.get("_") in {"channel", "channelForbidden"} else "chat"
        entities[(kind, chat.get("id", 0))] = chat
    return entities


def filter_dialog_result(
    result: DialogsResponse,
    *,
    kinds: set[str],
    query: str | None = None,
    unread_only: bool = False,
) -> DialogsResponse:
    unknown = kinds - DIALOG_KINDS
    if unknown:
        raise ValueError(f"unknown dialog kind(s): {', '.join(sorted(unknown))}")

    entities = dialog_entity_map(result)
    normalized_query = (query or "").casefold().strip()
    selected_dialogs: list[DialogObject] = []
    selected_keys: set[PeerKey] = set()
    selected_message_ids: set[int] = set()

    for dialog in result.get("dialogs", []):
        key = peer_key(object_field(cast(TLObject, dialog), "peer"))
        entity = entities.get(key)
        if entity is None or entity_kind(entity) not in kinds:
            continue
        if unread_only and dialog.get("unread_count", 0) <= 0:
            continue
        if normalized_query and not _entity_contains(entity, normalized_query):
            continue
        selected_dialogs.append(dialog)
        selected_keys.add(key)
        selected_message_ids.add(dialog.get("top_message", 0))

    messages = [
        cast(MessageObject, message)
        for message in object_list(cast(TLObject, result), "messages")
        if int_field(message, "id") in selected_message_ids
    ]
    filtered: DialogsResponse = {
        "_": result.get("_", "messages.dialogs"),
        "dialogs": selected_dialogs,
        "users": [
            user for user in result.get("users", []) if ("user", user.get("id", 0)) in selected_keys
        ],
        "chats": [
            chat
            for chat in result.get("chats", [])
            if (
                "channel" if chat.get("_") in {"channel", "channelForbidden"} else "chat",
                chat.get("id", 0),
            )
            in selected_keys
        ],
        "messages": messages,
    }
    if "count" in result:
        filtered["count"] = len(selected_dialogs)
    return filtered


def _entity_contains(entity: EntityObject, query: str) -> bool:
    full_name = " ".join(
        value for value in [entity.get("first_name", ""), entity.get("last_name", "")] if value
    )
    values = (
        entity.get("title", ""),
        entity.get("username", ""),
        entity.get("phone", ""),
        entity.get("first_name", ""),
        entity.get("last_name", ""),
        full_name,
    )
    return any(query in value.casefold() for value in values if value)
