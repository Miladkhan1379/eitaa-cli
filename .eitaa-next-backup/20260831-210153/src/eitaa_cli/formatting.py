from __future__ import annotations

import base64
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from rich.console import Console
from rich.json import JSON
from rich.table import Table

from eitaa_cli.api_types import (
    ContactsSearchResponse,
    DialogsResponse,
    EntityObject,
    JSONValue,
    MessagesResponse,
    ParticipantsResponse,
    PeerKey,
    TLObject,
    TLValue,
    TopPeersResponse,
    float_field,
    int_field,
    object_field,
    object_list,
    str_field,
)
from eitaa_cli.services.dialogs import dialog_entity_map, entity_kind
from eitaa_cli.services.peers import peer_key

console = Console()
_UNKNOWN_ENTITY: EntityObject = {"_": "unknown"}


def jsonable(value: object) -> JSONValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"$bytes_base64": base64.b64encode(value).decode("ascii"), "length": len(value)}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return str(value)


def print_json(value: object) -> None:
    console.print(JSON.from_data(jsonable(value)))


def reusable_peer_reference(entity: EntityObject | None) -> str:
    if entity is None:
        return ""
    predicate = entity.get("_")
    identifier = entity.get("id", 0)
    if predicate in {"user", "userEmpty"}:
        if entity.get("self"):
            return "me"
        access_hash = entity.get("access_hash")
        return (
            f"user:{identifier}:{access_hash}" if access_hash is not None else f"user:{identifier}"
        )
    if predicate in {"chat", "chatEmpty", "chatForbidden"}:
        return f"chat:{identifier}"
    if predicate in {"channel", "channelForbidden"}:
        access_hash = entity.get("access_hash")
        return (
            f"channel:{identifier}:{access_hash}"
            if access_hash is not None
            else f"channel:{identifier}"
        )
    return ""


def print_dialogs(result: DialogsResponse, *, title: str = "Eitaa chats") -> None:
    """Compact default list: readable name + the easiest reusable peer."""
    entities = dialog_entity_map(result)
    table = Table(title=title, show_lines=False, pad_edge=False)
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Name", overflow="ellipsis", max_width=42)
    table.add_column("Type", no_wrap=True)
    table.add_column("Use", overflow="fold", max_width=46)
    table.add_column("Unread", justify="right", no_wrap=True)
    for index, dialog in enumerate(result.get("dialogs", []), start=1):
        dialog_object = cast(TLObject, dialog)
        key = peer_key(object_field(dialog_object, "peer"))
        entity = entities.get(key)
        title_value = entity_title(entity) or f"{key[0]}:{key[1]}"
        username = str(entity.get("username") or "") if entity else ""
        peer_reference = f"@{username}" if username else reusable_peer_reference(entity)
        unread = int(dialog.get("unread_count", 0))
        unread_text = f"[bold yellow]{unread}[/bold yellow]" if unread else ""
        table.add_row(
            str(index),
            title_value,
            entity_kind(entity or _UNKNOWN_ENTITY),
            peer_reference,
            unread_text,
        )
    console.print(table)
    console.print(
        f"[dim]{len(result.get('dialogs', []))} conversation(s) · "
        "Use `eitaa peers resolve PEER` for the stable typed reference.[/dim]"
    )

def print_messages(result: MessagesResponse) -> None:
    """Readable compact history table for interactive use."""
    table = Table(title="Eitaa messages", show_lines=False, pad_edge=False)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Time", no_wrap=True)
    table.add_column("Dir", justify="center", no_wrap=True)
    table.add_column("Message", overflow="fold", max_width=100)
    for message in result.get("messages", []):
        message_object = cast(TLObject, message)
        date = _format_timestamp(message.get("date", 0))
        if date:
            date = date.replace("+00:00", "")[:19]
        direction = "[green]→[/green]" if bool(message_object.get("out")) else "[blue]←[/blue]"
        text = _message_summary(message_object)
        compact = " ".join(text.split())
        if len(compact) > 500:
            compact = compact[:497] + "..."
        table.add_row(
            str(message.get("id", "")),
            date,
            direction,
            compact,
        )
    console.print(table)
    console.print(f"[dim]{len(result.get('messages', []))} message(s)[/dim]")

def entity_title(entity: EntityObject | None) -> str:
    if entity is None:
        return ""
    title = entity.get("title")
    if title:
        return title
    full = " ".join(
        part for part in [entity.get("first_name", ""), entity.get("last_name", "")] if part
    ).strip()
    return full or entity.get("username", "") or entity.get("phone", "")


def print_entities(
    result: ContactsSearchResponse,
    *,
    title: str = "Eitaa entity search",
) -> None:
    table = Table(title=title)
    table.add_column("Type", no_wrap=True)
    table.add_column("Name", overflow="fold")
    table.add_column("Username")
    table.add_column("Phone")
    table.add_column("Peer reference", overflow="fold")
    entities = [*result.get("users", []), *result.get("chats", [])]
    for entity in entities:
        table.add_row(
            entity_kind(entity),
            entity_title(entity),
            entity.get("username", ""),
            entity.get("phone", ""),
            reusable_peer_reference(entity),
        )
    console.print(table)
    console.print(f"[dim]{len(entities)} entity(s)[/dim]")


def print_search_messages(
    result: MessagesResponse,
    *,
    title: str = "Eitaa message search",
) -> None:
    entities = _message_entity_map(cast(Mapping[str, TLValue], result))
    table = Table(title=title)
    table.add_column("ID", justify="right")
    table.add_column("Date")
    table.add_column("Conversation", overflow="fold")
    table.add_column("Type", no_wrap=True)
    table.add_column("Text / media", overflow="fold")
    table.add_column("Peer reference", overflow="fold")
    for message in result.get("messages", []):
        message_object = cast(TLObject, message)
        key = peer_key(object_field(message_object, "peer_id"))
        entity = entities.get(key)
        table.add_row(
            str(message.get("id", "")),
            _format_timestamp(message.get("date", 0)),
            entity_title(entity) or f"{key[0]}:{key[1]}",
            entity_kind(entity or _UNKNOWN_ENTITY),
            _message_summary(message_object)[:500],
            reusable_peer_reference(entity),
        )
    console.print(table)
    console.print(f"[dim]{len(result.get('messages', []))} message(s)[/dim]")


def print_top_peers(result: TopPeersResponse) -> None:
    predicate = result.get("_")
    if predicate in {"contacts.topPeersNotModified", "contacts.topPeersDisabled"}:
        console.print(predicate)
        return
    entities = _message_entity_map(cast(Mapping[str, TLValue], result))
    table = Table(title="Eitaa top peers")
    table.add_column("Category")
    table.add_column("Rank", justify="right")
    table.add_column("Name", overflow="fold")
    table.add_column("Rating", justify="right")
    table.add_column("Peer reference", overflow="fold")
    for category in object_list(cast(TLObject, result), "categories"):
        category_name = str_field(object_field(category, "category"), "_")
        for rank, top_peer in enumerate(object_list(category, "peers"), start=1):
            entity = entities.get(peer_key(object_field(top_peer, "peer")))
            table.add_row(
                category_name,
                str(rank),
                entity_title(entity),
                f"{float_field(top_peer, 'rating'):.3f}",
                reusable_peer_reference(entity),
            )
    console.print(table)


def print_participants(result: ParticipantsResponse) -> None:
    users = {user.get("id", 0): user for user in result.get("users", [])}
    table = Table(title="Eitaa participants")
    table.add_column("Role", no_wrap=True)
    table.add_column("Name", overflow="fold")
    table.add_column("Username")
    table.add_column("Peer reference", overflow="fold")
    participants = object_list(cast(TLObject, result), "participants")
    for participant in participants:
        peer = object_field(participant, "peer")
        user_id = int_field(participant, "user_id") or int_field(peer, "user_id")
        user = users.get(user_id)
        table.add_row(
            str_field(participant, "_"),
            entity_title(user) or str(user_id),
            user.get("username", "") if user else "",
            reusable_peer_reference(user),
        )
    console.print(table)
    console.print(f"[dim]{len(participants)} participant(s)[/dim]")


def _message_entity_map(result: Mapping[str, TLValue]) -> dict[PeerKey, EntityObject]:
    entities: dict[PeerKey, EntityObject] = {}
    for user in object_list(result, "users"):
        entity = cast(EntityObject, user)
        entities[("user", entity.get("id", 0))] = entity
    for chat in object_list(result, "chats"):
        entity = cast(EntityObject, chat)
        kind = "channel" if entity.get("_") in {"channel", "channelForbidden"} else "chat"
        entities[(kind, entity.get("id", 0))] = entity
    return entities


def _message_summary(message: TLObject) -> str:
    text = str_field(message, "message")
    media_type = str_field(object_field(message, "media"), "_")
    if media_type:
        text = f"{text} [{media_type}]".strip()
    if str_field(message, "_") == "messageService":
        return f"[{str_field(object_field(message, 'action'), '_', 'service')}]"
    return text


def _format_timestamp(value: int) -> str:
    return (
        datetime.fromtimestamp(value, tz=UTC).isoformat(sep=" ", timespec="seconds")
        if value
        else ""
    )
