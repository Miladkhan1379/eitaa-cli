from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from eitaa_cli.api_types import (
    EntityObject,
    InputChannel,
    InputPeer,
    InputPeerChannel,
    InputPeerChat,
    InputPeerSelf,
    InputPeerUser,
    InputUser,
    InputUserSelf,
    Peer,
    PeerChannel,
    PeerChat,
    PeerKey,
    PeerReference,
    PeerUser,
    TLObject,
    as_object,
    int_field,
    object_field,
    object_list,
    str_field,
)
from eitaa_cli.errors import EitaaRPCError, PeerResolutionError
from eitaa_cli.rpc import AsyncInvoker, invoke_object


class PeerResolver:
    """Resolve IDs, usernames, links, titles, contacts, and TL objects."""

    def __init__(self, client: AsyncInvoker) -> None:
        self.client = client

    async def resolve(self, reference: PeerReference) -> InputPeer:
        if isinstance(reference, dict):
            return normalize_input_peer(reference)
        text = reference.strip()
        if text in {"me", "self"}:
            return InputPeerSelf(_="inputPeerSelf")
        if text.startswith("{"):
            try:
                decoded = json.loads(text)
                return normalize_input_peer(as_object(decoded, context="peer JSON"))
            except json.JSONDecodeError as exc:
                raise PeerResolutionError(f"invalid peer JSON: {exc}") from exc

        typed = _parse_typed_reference(text)
        if typed is not None:
            return typed

        query = _username_from_reference(text) or text.lstrip("@").strip()
        if not query:
            raise PeerResolutionError("empty peer reference")

        if text.startswith("@") or _username_from_reference(text):
            try:
                resolved = await invoke_object(
                    self.client, "contacts.resolveUsername", {"username": query}
                )
                return _resolved_peer_to_input_peer(resolved)
            except EitaaRPCError:
                pass

        found = await invoke_object(self.client, "contacts.search", {"q": query, "limit": 50})
        candidates = [
            cast(EntityObject, entity)
            for entity in (*object_list(found, "users"), *object_list(found, "chats"))
        ]
        if not candidates:
            raise PeerResolutionError(f"no Eitaa peer found for {reference!r}")
        lowered = query.casefold()
        exact = [entity for entity in candidates if _entity_matches(entity, lowered)]
        if len(exact) == 1:
            return entity_to_input_peer(exact[0])
        if len(exact) > 1:
            candidates = exact
        if len(candidates) == 1:
            return entity_to_input_peer(candidates[0])
        preview: list[str] = []
        for entity in candidates[:8]:
            title = str(entity.get("title") or "").strip()
            if not title:
                title = " ".join(
                    str(value)
                    for value in (entity.get("first_name"), entity.get("last_name"))
                    if value
                ).strip()
            username = str(entity.get("username") or "").strip()
            identifier = int(entity.get("id", 0))
            label = title or username or str(identifier)
            if username:
                label = f"{label} (@{username})"
            preview.append(label)
        raise PeerResolutionError(
            f"ambiguous Eitaa peer {reference!r}; use @username or a typed peer reference. "
            f"Matches: {', '.join(preview)}"
        )

    async def resolve_input_user(self, reference: PeerReference) -> InputUser | InputUserSelf:
        peer = await self.resolve(reference)
        predicate = peer["_"]
        if predicate == "inputPeerSelf":
            return InputUserSelf(_="inputUserSelf")
        if predicate == "inputPeerUser":
            user_peer = cast(InputPeerUser, peer)
            return InputUser(
                _="inputUser",
                user_id=user_peer["user_id"],
                access_hash=user_peer["access_hash"],
            )
        raise PeerResolutionError(f"{reference!r} does not resolve to a user")

    async def resolve_input_channel(self, reference: PeerReference) -> InputChannel:
        peer = await self.resolve(reference)
        if peer["_"] != "inputPeerChannel":
            raise PeerResolutionError(f"{reference!r} does not resolve to a channel/supergroup")
        channel_peer = peer
        return InputChannel(
            _="inputChannel",
            channel_id=channel_peer["channel_id"],
            access_hash=channel_peer["access_hash"],
        )


def normalize_input_peer(value: Mapping[str, object]) -> InputPeer:
    predicate = str_field(value, "_")
    if predicate == "inputPeerEmpty":
        return {"_": "inputPeerEmpty"}
    if predicate == "inputPeerSelf":
        return {"_": "inputPeerSelf"}
    if predicate == "inputPeerUser":
        return {
            "_": "inputPeerUser",
            "user_id": int_field(value, "user_id"),
            "access_hash": int_field(value, "access_hash"),
        }
    if predicate == "inputPeerChat":
        return {"_": "inputPeerChat", "chat_id": int_field(value, "chat_id")}
    if predicate == "inputPeerChannel":
        return {
            "_": "inputPeerChannel",
            "channel_id": int_field(value, "channel_id"),
            "access_hash": int_field(value, "access_hash"),
        }
    return entity_to_input_peer(cast(EntityObject, value))


def entity_to_input_peer(entity: EntityObject) -> InputPeer:
    predicate = entity.get("_")
    identifier = entity.get("id", 0)
    if predicate in {"user", "userEmpty"}:
        if entity.get("self"):
            return {"_": "inputPeerSelf"}
        access_hash = entity.get("access_hash")
        if access_hash is None:
            raise PeerResolutionError(f"user {identifier} has no access_hash")
        return {"_": "inputPeerUser", "user_id": identifier, "access_hash": access_hash}
    if predicate in {"chat", "chatEmpty", "chatForbidden"}:
        return {"_": "inputPeerChat", "chat_id": identifier}
    if predicate in {"channel", "channelForbidden"}:
        access_hash = entity.get("access_hash")
        if access_hash is None:
            raise PeerResolutionError(f"channel {identifier} has no access_hash")
        return {
            "_": "inputPeerChannel",
            "channel_id": identifier,
            "access_hash": access_hash,
        }
    if predicate == "peerUser":
        raise PeerResolutionError("a bare peerUser lacks the required access_hash")
    if predicate == "peerChat":
        return {"_": "inputPeerChat", "chat_id": int_field(entity, "chat_id")}
    if predicate == "peerChannel":
        raise PeerResolutionError("a bare peerChannel lacks the required access_hash")
    raise PeerResolutionError(f"unsupported peer object: {predicate!r}")


def input_peer_to_peer(peer: InputPeer) -> Peer | None:
    predicate = peer["_"]
    if predicate == "inputPeerUser":
        user = cast(InputPeerUser, peer)
        return PeerUser(_="peerUser", user_id=user["user_id"])
    if predicate == "inputPeerChat":
        chat = cast(InputPeerChat, peer)
        return PeerChat(_="peerChat", chat_id=chat["chat_id"])
    if predicate == "inputPeerChannel":
        channel = cast(InputPeerChannel, peer)
        return PeerChannel(_="peerChannel", channel_id=channel["channel_id"])
    return None


def peer_key(peer: TLObject) -> PeerKey:
    predicate = str_field(peer, "_")
    if predicate in {"peerUser", "inputPeerUser"}:
        return "user", int_field(peer, "user_id")
    if predicate in {"peerChat", "inputPeerChat"}:
        return "chat", int_field(peer, "chat_id")
    if predicate in {"peerChannel", "inputPeerChannel"}:
        return "channel", int_field(peer, "channel_id")
    return predicate or "unknown", 0


def _parse_typed_reference(text: str) -> InputPeer | None:
    parts = text.split(":")
    kind = parts[0].casefold()
    try:
        if kind == "chat" and len(parts) == 2:
            return InputPeerChat(_="inputPeerChat", chat_id=int(parts[1]))
        if kind in {"user", "channel"} and len(parts) == 3:
            identifier, access_hash = int(parts[1]), int(parts[2])
            if kind == "user":
                return InputPeerUser(_="inputPeerUser", user_id=identifier, access_hash=access_hash)
            return InputPeerChannel(
                _="inputPeerChannel", channel_id=identifier, access_hash=access_hash
            )
    except ValueError as exc:
        raise PeerResolutionError(f"invalid typed peer reference: {text!r}") from exc
    return None


def _entity_matches(entity: EntityObject, query: str) -> bool:
    values = [
        entity.get("username", ""),
        entity.get("title", ""),
        " ".join(
            value for value in [entity.get("first_name", ""), entity.get("last_name", "")] if value
        ),
        entity.get("phone", ""),
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


def _resolved_peer_to_input_peer(result: TLObject) -> InputPeer:
    peer = object_field(result, "peer")
    kind, identifier = peer_key(peer)
    entities = [
        cast(EntityObject, entity)
        for entity in (*object_list(result, "users"), *object_list(result, "chats"))
    ]
    for entity in entities:
        predicate = entity.get("_", "")
        entity_kind = (
            "user"
            if predicate in {"user", "userEmpty"}
            else "channel"
            if predicate in {"channel", "channelForbidden"}
            else "chat"
        )
        if entity_kind == kind and entity.get("id", 0) == identifier:
            return entity_to_input_peer(entity)
    raise PeerResolutionError("resolved username did not include a usable peer entity")
