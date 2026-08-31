from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from eitaa_cli.cli.pretty import console
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


peers_app = typer.Typer(
    no_args_is_help=True,
    help="Resolve Eitaa peer references and show safe reusable forms.",
)


@peers_app.command("resolve")
def peer_resolve(ctx: typer.Context, peer: str) -> None:
    """Resolve a name/@username/typed peer and show the stable reference."""

    normalized_peer = normalize_peer_input(peer)

    async def action(client: EitaaClient) -> dict[str, Any]:
        resolved = await client.peers.resolve(normalized_peer)
        canonical = canonical_peer_reference(resolved)
        return {
            "input": peer,
            "kind": peer_kind(resolved),
            "best": best_reference(normalized_peer, canonical),
            "stable": canonical,
        }

    result = _run(_with_client(_state(ctx).settings, action))
    table = Table(title="Resolved Eitaa peer", show_header=False, pad_edge=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("Input", str(result["input"]))
    table.add_row("Kind", str(result["kind"]))
    table.add_row("Use", str(result["best"]))
    table.add_row("Stable", str(result["stable"]))
    console.print(table)
    console.print("[dim]For long-running automation, the Stable value is the safest choice.[/dim]")


@peers_app.command("formats")
def peer_formats() -> None:
    table = Table(title="Accepted peer formats", pad_edge=False)
    table.add_column("Format", style="cyan", no_wrap=True)
    table.add_column("Example")
    table.add_column("When to use")
    table.add_row("username", "news", "PowerShell-friendly public username")
    table.add_row("@username", "@news", "Also works when quoted in PowerShell")
    table.add_row("me", "me", "Your Saved Messages / self")
    table.add_row("user:id:hash", "user:123:456", "Stable private user reference")
    table.add_row("chat:id", "chat:123", "Classic group")
    table.add_row("channel:id:hash", "channel:123:456", "Stable channel/supergroup")
    table.add_row("source:alias", "source:news", "Saved v0.8 source alias")
    console.print(table)
