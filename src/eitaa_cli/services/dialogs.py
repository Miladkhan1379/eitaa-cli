from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from eitaa_cli.services.peers import peer_key

if TYPE_CHECKING:
    from eitaa_cli.client import EitaaClient


DIALOG_KINDS = frozenset({"private", "group", "supergroup", "channel"})


class DialogsService:
    """Read and filter the user's conversation list."""

    def __init__(self, client: EitaaClient) -> None:
        self.client = client

    async def list(
        self,
        limit: int = 50,
        *,
        folder_id: int | None = None,
        kinds: Iterable[str] | None = None,
        query: str | None = None,
        unread_only: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "offset_date": 0,
            "offset_id": 0,
            "offset_peer": {"_": "inputPeerEmpty"},
            "limit": limit,
            "hash": 0,
        }
        if folder_id is not None:
            params["folder_id"] = folder_id
        result = await self.client.invoke("messages.getDialogs", params)
        if kinds or query or unread_only:
            return filter_dialog_result(
                result,
                kinds=set(kinds or DIALOG_KINDS),
                query=query,
                unread_only=unread_only,
            )
        return result

    async def private(self, limit: int = 50, **kwargs: Any) -> dict[str, Any]:
        return await self.list(limit, kinds={"private"}, **kwargs)

    async def groups(self, limit: int = 50, **kwargs: Any) -> dict[str, Any]:
        return await self.list(limit, kinds={"group", "supergroup"}, **kwargs)

    async def channels(self, limit: int = 50, **kwargs: Any) -> dict[str, Any]:
        return await self.list(limit, kinds={"channel"}, **kwargs)

    async def info(self, reference: str | dict[str, Any]) -> dict[str, Any]:
        peer = await self.client.peers.resolve(reference)
        predicate = peer.get("_")
        if predicate in {"inputPeerSelf", "inputPeerUser"}:
            input_user = (
                {"_": "inputUserSelf"}
                if predicate == "inputPeerSelf"
                else {
                    "_": "inputUser",
                    "user_id": peer["user_id"],
                    "access_hash": peer["access_hash"],
                }
            )
            return await self.client.invoke("users.getFullUser", {"id": input_user})
        if predicate == "inputPeerChat":
            return await self.client.invoke("messages.getFullChat", {"chat_id": peer["chat_id"]})
        if predicate == "inputPeerChannel":
            return await self.client.invoke(
                "channels.getFullChannel",
                {
                    "channel": {
                        "_": "inputChannel",
                        "channel_id": peer["channel_id"],
                        "access_hash": peer["access_hash"],
                    }
                },
            )
        raise ValueError(f"unsupported peer type: {predicate!r}")


def entity_kind(entity: dict[str, Any]) -> str:
    """Classify an API entity as private, classic group, supergroup, or channel."""

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


def dialog_entity_map(result: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    entities: dict[tuple[str, int], dict[str, Any]] = {}
    for user in result.get("users", []):
        entities[("user", int(user.get("id", 0)))] = user
    for chat in result.get("chats", []):
        key_kind = "channel" if chat.get("_") in {"channel", "channelForbidden"} else "chat"
        entities[(key_kind, int(chat.get("id", 0)))] = chat
    return entities


def filter_dialog_result(
    result: dict[str, Any],
    *,
    kinds: set[str],
    query: str | None = None,
    unread_only: bool = False,
) -> dict[str, Any]:
    unknown = kinds - DIALOG_KINDS
    if unknown:
        raise ValueError(f"unknown dialog kind(s): {', '.join(sorted(unknown))}")

    entities = dialog_entity_map(result)
    normalized_query = (query or "").casefold().strip()
    selected_dialogs: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, int]] = set()
    selected_message_ids: set[int] = set()

    for dialog in result.get("dialogs", []):
        key = peer_key(dialog.get("peer", {}))
        entity = entities.get(key, {})
        if entity_kind(entity) not in kinds:
            continue
        if unread_only and int(dialog.get("unread_count", 0)) <= 0:
            continue
        if normalized_query and not _entity_contains(entity, normalized_query):
            continue
        selected_dialogs.append(dialog)
        selected_keys.add(key)
        selected_message_ids.add(int(dialog.get("top_message", 0)))

    filtered = dict(result)
    filtered["dialogs"] = selected_dialogs
    filtered["users"] = [
        user for user in result.get("users", []) if ("user", int(user.get("id", 0))) in selected_keys
    ]
    filtered["chats"] = [
        chat
        for chat in result.get("chats", [])
        if (
            "channel" if chat.get("_") in {"channel", "channelForbidden"} else "chat",
            int(chat.get("id", 0)),
        )
        in selected_keys
    ]
    filtered["messages"] = [
        message
        for message in result.get("messages", [])
        if int(message.get("id", 0)) in selected_message_ids
    ]
    if "count" in filtered:
        filtered["count"] = len(selected_dialogs)
    return filtered


def _entity_contains(entity: dict[str, Any], query: str) -> bool:
    values = (
        entity.get("title"),
        entity.get("username"),
        entity.get("phone"),
        entity.get("first_name"),
        entity.get("last_name"),
        " ".join(
            value
            for value in [str(entity.get("first_name") or ""), str(entity.get("last_name") or "")]
            if value
        ),
    )
    return any(query in str(value).casefold() for value in values if value)
