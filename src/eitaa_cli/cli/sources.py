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
