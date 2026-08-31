from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel
from rich.table import Table

from eitaa_cli.cli.pretty import console, print_delivery_failures, print_sources, print_sync_status
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.sync_engine import SyncStore

NEXT_VERSION = "0.8.0"

next_app = typer.Typer(
    no_args_is_help=True,
    help="Eitaa Next dashboard, health checks, and upgrade information.",
)


def _db_path(value: Path) -> Path:
    return value.expanduser().resolve()


@next_app.command("status")
def next_status(db: Path = typer.Option(Path(".eitaa-next.db"), "--db")) -> None:
    """Readable dashboard for sync state, source aliases, and automation deliveries."""
    path = _db_path(db)
    with SyncStore(path) as store:
        sources = store.list_registered_sources()
        checkpoints = store.status()
        stats = store.delivery_stats()
    console.print(
        Panel(
            f"[bold]eitaa-next[/bold] v{NEXT_VERSION}\n"
            f"State DB: {path}\n"
            f"Saved sources: {len(sources)}    Synced sources: {len(checkpoints)}\n"
            f"Deliveries: [green]{stats['done']} done[/green] / "
            f"[red]{stats['failed']} failed[/red]",
            title="Eitaa Next",
            border_style="cyan",
        )
    )
    print_sources(sources)
    print_sync_status(checkpoints)


@next_app.command("failures")
def next_failures(
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    limit: int = typer.Option(20, "--limit", min=1, max=200),
) -> None:
    with SyncStore(_db_path(db)) as store:
        rows = store.failed_deliveries(limit)
    print_delivery_failures(rows)


@next_app.command("doctor")
def next_doctor(
    ctx: typer.Context,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    probe_updates: bool = typer.Option(False, "--probe-updates"),
) -> None:
    """Check local state, authentication/API access, and optionally the raw update state."""
    rows: list[tuple[str, str, str]] = []
    rows.append(("Python", "OK", sys.version.split()[0]))
    rows.append(("Platform", "OK", platform.platform()))
    path = _db_path(db)
    try:
        with SyncStore(path) as store:
            store.status()
        rows.append(("SQLite state", "OK", str(path)))
    except Exception as exc:  # pragma: no cover - environment-specific
        rows.append(("SQLite state", "FAIL", str(exc)))

    async def action(client: EitaaClient) -> dict[str, Any]:
        dialogs = await client.dialogs.list(1)
        result: dict[str, Any] = {"dialogs": len(dialogs.get("dialogs", []))}
        if probe_updates:
            result["updates"] = await client.invoke("updates.getState", {})
        return result

    try:
        remote = _run(_with_client(_state(ctx).settings, action))
        rows.append(("Eitaa session/API", "OK", f"dialog probe={remote['dialogs']}"))
        if probe_updates:
            rows.append(("updates.getState", "OK", str(remote.get("updates"))))
    except Exception as exc:
        rows.append(("Eitaa session/API", "FAIL", str(exc)))

    table = Table(title="Eitaa Next doctor", pad_edge=False)
    table.add_column("Check", style="bold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Details", overflow="fold")
    for name, status, details in rows:
        style = "green" if status == "OK" else "red"
        table.add_row(name, f"[{style}]{status}[/{style}]", details)
    console.print(table)
