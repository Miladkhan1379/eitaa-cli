from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.table import Table

from eitaa_cli.services.dialogs import dialog_entity_map, entity_kind
from eitaa_cli.services.peers import peer_key

console = Console()


def jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"$bytes_base64": base64.b64encode(value).decode("ascii"), "length": len(value)}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def print_json(value: Any) -> None:
    console.print(JSON.from_data(jsonable(value)))


def reusable_peer_reference(entity: dict[str, Any]) -> str:
    predicate = entity.get("_")
    identifier = int(entity.get("id", 0))
    if predicate in {"user", "userEmpty"}:
        if entity.get("self"):
            return "me"
        access_hash = entity.get("access_hash")
        return f"user:{identifier}:{access_hash}" if access_hash is not None else f"user:{identifier}"
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


def print_dialogs(result: dict[str, Any], *, title: str = "Eitaa chats") -> None:
    entities = dialog_entity_map(result)
    messages = {int(item.get("id", 0)): item for item in result.get("messages", [])}

    table = Table(title=title)
    table.add_column("Type", no_wrap=True)
    table.add_column("Title", overflow="fold")
    table.add_column("Username", overflow="fold")
    table.add_column("Unread", justify="right")
    table.add_column("Last message", overflow="fold")
    table.add_column("Peer reference", overflow="fold")
    for dialog in result.get("dialogs", []):
        key = peer_key(dialog.get("peer", {}))
        entity = entities.get(key, {})
        title_value = entity_title(entity) or f"{key[0]}:{key[1]}"
        message = messages.get(int(dialog.get("top_message", 0)), {})
        snippet = str(message.get("message") or message.get("action", {}).get("_") or "")
        table.add_row(
            entity_kind(entity),
            title_value,
            str(entity.get("username") or ""),
            str(dialog.get("unread_count", 0)),
            snippet[:120],
            reusable_peer_reference(entity),
        )
    console.print(table)
    console.print(f"[dim]{len(result.get('dialogs', []))} conversation(s)[/dim]")


def print_messages(result: dict[str, Any]) -> None:
    table = Table(title="Eitaa messages")
    table.add_column("ID", justify="right")
    table.add_column("Date")
    table.add_column("Direction")
    table.add_column("Text / media", overflow="fold")
    for message in result.get("messages", []):
        date_value = int(message.get("date", 0))
        date = datetime.fromtimestamp(date_value).isoformat(sep=" ", timespec="seconds") if date_value else ""
        text = str(message.get("message") or "")
        media = message.get("media", {}).get("_")
        if media:
            text = f"{text} [{media}]".strip()
        if message.get("_") == "messageService":
            text = f"[{message.get('action', {}).get('_', 'service')}]"
        table.add_row(
            str(message.get("id", "")),
            date,
            "out" if message.get("out") else "in",
            text[:500],
        )
    console.print(table)


def entity_title(entity: dict[str, Any]) -> str:
    if entity.get("title"):
        return str(entity["title"])
    full = " ".join(
        part
        for part in [str(entity.get("first_name") or ""), str(entity.get("last_name") or "")]
        if part
    ).strip()
    return full or str(entity.get("username") or entity.get("phone") or "")
