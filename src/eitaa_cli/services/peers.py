from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from eitaa_cli.errors import EitaaRPCError, PeerResolutionError

if TYPE_CHECKING:
    from eitaa_cli.client import EitaaClient


class PeerResolver:
    """Resolves JSON, typed IDs, usernames, titles, and contact names to InputPeer."""

    def __init__(self, client: EitaaClient) -> None:
        self.client = client

    async def resolve(self, reference: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(reference, dict):
            return normalize_input_peer(reference)
        text = reference.strip()
        if text in {"me", "self"}:
            return {"_": "inputPeerSelf"}
        if text.startswith("{"):
            try:
                return normalize_input_peer(json.loads(text))
            except json.JSONDecodeError as exc:
                raise PeerResolutionError(f"invalid peer JSON: {exc}") from exc
        typed = _parse_typed_reference(text)
        if typed:
            return typed
        query = _username_from_reference(text) or text.lstrip("@").strip()
        if not query:
            raise PeerResolutionError("empty peer reference")
        if text.startswith("@") or _username_from_reference(text):
            try:
                resolved = await self.client.invoke(
                    "contacts.resolveUsername", {"username": query}
                )
                return _resolved_peer_to_input_peer(resolved)
            except EitaaRPCError:
                pass
        found = await self.client.invoke("contacts.search", {"q": query, "limit": 50})
        candidates = list(found.get("users", [])) + list(found.get("chats", []))
        if not candidates:
            raise PeerResolutionError(f"no Eitaa peer found for {reference!r}")
        lowered = query.casefold()
        exact = [entity for entity in candidates if _entity_matches(entity, lowered)]
        entity = exact[0] if exact else candidates[0]
        return entity_to_input_peer(entity)

    async def resolve_input_user(self, reference: str | dict[str, Any]) -> dict[str, Any]:
        peer = await self.resolve(reference)
        predicate = peer.get("_")
        if predicate == "inputPeerSelf":
            return {"_": "inputUserSelf"}
        if predicate == "inputPeerUser":
            return {
                "_": "inputUser",
                "user_id": peer["user_id"],
                "access_hash": peer["access_hash"],
            }
        raise PeerResolutionError(f"{reference!r} does not resolve to a user")

    async def resolve_input_channel(self, reference: str | dict[str, Any]) -> dict[str, Any]:
        peer = await self.resolve(reference)
        if peer.get("_") != "inputPeerChannel":
            raise PeerResolutionError(f"{reference!r} does not resolve to a channel/supergroup")
        return {
            "_": "inputChannel",
            "channel_id": peer["channel_id"],
            "access_hash": peer["access_hash"],
        }


def normalize_input_peer(value: dict[str, Any]) -> dict[str, Any]:
    predicate = value.get("_")
    if predicate in {"inputPeerEmpty", "inputPeerSelf", "inputPeerUser", "inputPeerChat", "inputPeerChannel"}:
        return value
    return entity_to_input_peer(value)


def entity_to_input_peer(entity: dict[str, Any]) -> dict[str, Any]:
    predicate = entity.get("_")
    if predicate in {"user", "userEmpty"}:
        if entity.get("self"):
            return {"_": "inputPeerSelf"}
        access_hash = entity.get("access_hash")
        if access_hash is None:
            raise PeerResolutionError(f"user {entity.get('id')} has no access_hash")
        return {"_": "inputPeerUser", "user_id": entity["id"], "access_hash": access_hash}
    if predicate in {"chat", "chatEmpty", "chatForbidden"}:
        return {"_": "inputPeerChat", "chat_id": entity["id"]}
    if predicate in {"channel", "channelForbidden"}:
        access_hash = entity.get("access_hash")
        if access_hash is None:
            raise PeerResolutionError(f"channel {entity.get('id')} has no access_hash")
        return {
            "_": "inputPeerChannel",
            "channel_id": entity["id"],
            "access_hash": access_hash,
        }
    if predicate == "peerUser":
        raise PeerResolutionError("a bare peerUser lacks the required access_hash")
    if predicate == "peerChat":
        return {"_": "inputPeerChat", "chat_id": entity["chat_id"]}
    if predicate == "peerChannel":
        raise PeerResolutionError("a bare peerChannel lacks the required access_hash")
    raise PeerResolutionError(f"unsupported peer object: {predicate!r}")


def input_peer_to_peer(peer: dict[str, Any]) -> dict[str, Any] | None:
    predicate = peer.get("_")
    if predicate == "inputPeerUser":
        return {"_": "peerUser", "user_id": peer["user_id"]}
    if predicate == "inputPeerChat":
        return {"_": "peerChat", "chat_id": peer["chat_id"]}
    if predicate == "inputPeerChannel":
        return {"_": "peerChannel", "channel_id": peer["channel_id"]}
    return None


def peer_key(peer: dict[str, Any]) -> tuple[str, int]:
    predicate = peer.get("_")
    if predicate in {"peerUser", "inputPeerUser"}:
        return "user", int(peer.get("user_id", 0))
    if predicate in {"peerChat", "inputPeerChat"}:
        return "chat", int(peer.get("chat_id", 0))
    if predicate in {"peerChannel", "inputPeerChannel"}:
        return "channel", int(peer.get("channel_id", 0))
    return predicate or "unknown", 0


def _parse_typed_reference(text: str) -> dict[str, Any] | None:
    parts = text.split(":")
    kind = parts[0].casefold()
    if kind == "chat" and len(parts) == 2:
        return {"_": "inputPeerChat", "chat_id": int(parts[1])}
    if kind in {"user", "channel"} and len(parts) == 3:
        id_value, access_hash = int(parts[1]), int(parts[2])
        if kind == "user":
            return {"_": "inputPeerUser", "user_id": id_value, "access_hash": access_hash}
        return {
            "_": "inputPeerChannel",
            "channel_id": id_value,
            "access_hash": access_hash,
        }
    return None


def _entity_matches(entity: dict[str, Any], query: str) -> bool:
    values = [
        str(entity.get("username") or ""),
        str(entity.get("title") or ""),
        " ".join(
            value for value in [str(entity.get("first_name") or ""), str(entity.get("last_name") or "")] if value
        ),
        str(entity.get("phone") or ""),
    ]
    return any(value.casefold() == query for value in values if value)


def _username_from_reference(text: str) -> str | None:
    lowered = text.casefold()
    for marker in ("eitaa.com/", "eitaa.ir/"):
        index = lowered.find(marker)
        if index >= 0:
            tail = text[index + len(marker) :].split("?", 1)[0].split("#", 1)[0].strip("/")
            if tail and "/" not in tail and not tail.startswith("+"):
                return tail
    return None


def _resolved_peer_to_input_peer(result: dict[str, Any]) -> dict[str, Any]:
    peer = result.get("peer") or {}
    kind, identifier = peer_key(peer)
    entities = list(result.get("users", [])) + list(result.get("chats", []))
    for entity in entities:
        entity_kind = (
            "user"
            if entity.get("_") in {"user", "userEmpty"}
            else "channel"
            if entity.get("_") in {"channel", "channelForbidden"}
            else "chat"
        )
        if entity_kind == kind and int(entity.get("id", 0)) == identifier:
            return entity_to_input_peer(entity)
    raise PeerResolutionError("resolved username did not include a usable peer entity")
