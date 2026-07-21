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
from eitaa_cli.services.peers import peer_key

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
        params: TLObject = {
            "offset_date": 0,
            "offset_id": 0,
            "offset_peer": {"_": "inputPeerEmpty"},
            "limit": limit,
            "hash": 0,
        }
        if folder_id is not None:
            params["folder_id"] = folder_id
        result = cast(
            DialogsResponse,
            await invoke_object(self.client, "messages.getDialogs", params),
        )
        if kinds or query or unread_only:
            return filter_dialog_result(
                result,
                kinds=set(kinds or DIALOG_KINDS),
                query=query,
                unread_only=unread_only,
            )
        return result

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
