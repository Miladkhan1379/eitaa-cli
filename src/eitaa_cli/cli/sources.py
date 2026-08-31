from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from eitaa_cli.cli.pretty import console, print_sources
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.formatting import entity_title
from eitaa_cli.services.dialogs import dialog_entity_map, entity_kind
from eitaa_cli.services.peers import entity_to_input_peer, peer_key
from eitaa_cli.api_types import TLObject, object_field
from eitaa_cli.source_refs import (
    best_reference,
    canonical_peer_reference,
    normalize_peer_input,
    peer_kind,
)
from eitaa_cli.sync_engine import SyncStore


sources_app = typer.Typer(
    no_args_is_help=True,
    help="Save friendly aliases for stable Eitaa peer references used by sync/automation.",
)


def _db_path(value: Path) -> Path:
    return value.expanduser().resolve()


@sources_app.command("add")
def source_add(
    ctx: typer.Context,
    alias: str,
    peer: str,
    label: str = typer.Option("", "--label", "-l"),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
) -> None:
    """Resolve PEER once and save it as `source:ALIAS`. Bare usernames are accepted."""

    normalized_peer = normalize_peer_input(peer)

    async def action(client: EitaaClient) -> dict[str, Any]:
        resolved = await client.peers.resolve(normalized_peer)
        canonical = canonical_peer_reference(resolved)
        return {
            "canonical": canonical,
            "kind": peer_kind(resolved),
            "best": best_reference(normalized_peer, canonical),
        }

    result = _run(_with_client(_state(ctx).settings, action))
    with SyncStore(_db_path(db)) as store:
        store.register_source(
            alias,
            str(result["canonical"]),
            label=label or alias,
            kind=str(result["kind"]),
            original=normalized_peer,
        )
    console.print(
        f"[green]Saved[/green] [bold]source:{alias.casefold()}[/bold] → {result['canonical']}"
    )
    if str(result["best"]) != str(result["canonical"]):
        console.print(f"[dim]Public/friendly reference: {result['best']}[/dim]")


@sources_app.command("list")
def source_list(
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
) -> None:
    """List saved aliases and the stable peer behind each alias."""
    with SyncStore(_db_path(db)) as store:
        rows = store.list_registered_sources()
    print_sources(rows)


@sources_app.command("show")
def source_show(
    alias: str,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
) -> None:
    with SyncStore(_db_path(db)) as store:
        row = store.get_registered_source(alias)
    if row is None:
        raise typer.BadParameter(f"unknown source alias: {alias}")
    table = Table(title=f"source:{row['alias']}", show_header=False, pad_edge=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    for key in ("label", "kind", "original", "peer"):
        table.add_row(key, str(row.get(key) or ""))
    console.print(table)


@sources_app.command("remove")
def source_remove(
    alias: str,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    if not yes and not typer.confirm(f"Remove source alias {alias!r}?"):
        raise typer.Abort()
    with SyncStore(_db_path(db)) as store:
        removed = store.remove_source(alias)
    if removed:
        console.print(f"[green]Removed[/green] source:{alias.casefold()}")
    else:
        console.print(f"[yellow]No source alias named {alias!r}.[/yellow]")


@sources_app.command("test")
def source_test(
    ctx: typer.Context,
    source: str,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
) -> None:
    """Resolve an alias/reference and verify that its latest message can be read."""
    with SyncStore(_db_path(db)) as store:
        resolved = store.resolve_source(source)

    async def action(client: EitaaClient) -> dict[str, Any]:
        result = await client.messages.history(resolved, limit=1)
        messages = result.get("messages", [])
        return {
            "resolved": resolved,
            "message_id": int(messages[0].get("id", 0)) if messages else 0,
        }

    result = _run(_with_client(_state(ctx).settings, action))
    console.print(f"[green]OK[/green] {source} → {result['resolved']}")
    console.print(f"[dim]Latest message ID: {result['message_id'] or '-'}[/dim]")


@sources_app.command("pick")
def source_pick(
    ctx: typer.Context,
    alias: str,
    kind: str = typer.Option("all", "--kind", help="all/channel/groups/private"),
    query: str | None = typer.Option(None, "--query", "-q"),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
    label: str = typer.Option("", "--label", "-l"),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
) -> None:
    """Interactively choose a conversation and save it as source:ALIAS."""
    choices = {
        "all": {"private", "group", "supergroup", "channel"},
        "channel": {"channel"},
        "channels": {"channel"},
        "group": {"group", "supergroup"},
        "groups": {"group", "supergroup"},
        "private": {"private"},
    }
    key = kind.strip().casefold()
    if key not in choices:
        raise typer.BadParameter("--kind must be all/channel/groups/private")

    async def action(client: EitaaClient) -> list[dict[str, Any]]:
        result = await client.dialogs.list(limit, kinds=choices[key], query=query)
        entities = dialog_entity_map(result)
        rows: list[dict[str, Any]] = []
        for dialog in result.get("dialogs", []):
            dialog_obj = dialog if isinstance(dialog, dict) else {}
            pkey = peer_key(object_field(dialog_obj, "peer"))
            entity = entities.get(pkey)
            if entity is None:
                continue
            input_peer = entity_to_input_peer(entity)
            rows.append(
                {
                    "name": entity_title(entity) or f"{pkey[0]}:{pkey[1]}",
                    "kind": entity_kind(entity),
                    "username": str(entity.get("username") or ""),
                    "canonical": canonical_peer_reference(input_peer),
                }
            )
        return rows

    rows = _run(_with_client(_state(ctx).settings, action))
    if not rows:
        console.print("[yellow]No matching conversations found.[/yellow]")
        raise typer.Exit(1)
    table = Table(title="Choose an Eitaa source", pad_edge=False)
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Name", overflow="ellipsis", max_width=40)
    table.add_column("Kind", no_wrap=True)
    table.add_column("Username", overflow="ellipsis", max_width=28)
    for idx, row in enumerate(rows, 1):
        table.add_row(str(idx), row["name"], row["kind"], f"@{row['username']}" if row["username"] else "")
    console.print(table)
    selected = typer.prompt("Select number", type=int)
    if selected < 1 or selected > len(rows):
        raise typer.BadParameter("selection is outside the displayed range")
    row = rows[selected - 1]
    with SyncStore(_db_path(db)) as store:
        store.register_source(
            alias,
            row["canonical"],
            label=label or row["name"],
            kind=row["kind"],
            original=f"@{row['username']}" if row["username"] else row["canonical"],
        )
    console.print(
        f"[green]Saved[/green] [bold]source:{alias.casefold()}[/bold] → {row['name']}\n"
        f"[dim]{row['canonical']}[/dim]"
    )
