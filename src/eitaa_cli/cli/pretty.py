from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from eitaa_cli.sync_engine import SyncEvent

console = Console()


def age_text(timestamp: int) -> str:
    if not timestamp:
        return "-"
    seconds = max(0, int(time.time()) - int(timestamp))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def print_sync_status(rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[dim]No synchronized sources yet.[/dim]")
        return
    table = Table(title="Sync status", show_lines=False, pad_edge=False)
    table.add_column("Source", overflow="ellipsis", max_width=52)
    table.add_column("Last ID", justify="right", no_wrap=True)
    table.add_column("Updated", no_wrap=True)
    table.add_column("Age", justify="right", no_wrap=True)
    for row in rows:
        updated = int(row.get("updated_at", 0) or 0)
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(updated)) if updated else "-"
        table.add_row(
            str(row.get("source") or ""),
            str(row.get("last_id") or 0),
            when,
            age_text(updated),
        )
    console.print(table)


def print_sources(rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[dim]No saved sources. Add one with: eitaa sources add NAME PEER[/dim]")
        return
    table = Table(title="Saved Eitaa sources", show_lines=False, pad_edge=False)
    table.add_column("Alias", style="bold cyan", no_wrap=True)
    table.add_column("Label", overflow="ellipsis", max_width=28)
    table.add_column("Kind", no_wrap=True)
    table.add_column("Use in commands", overflow="fold", max_width=28)
    table.add_column("Stable peer", overflow="fold", max_width=48)
    for row in rows:
        alias = str(row.get("alias") or "")
        table.add_row(
            alias,
            str(row.get("label") or ""),
            str(row.get("kind") or ""),
            f"source:{alias}",
            str(row.get("peer") or ""),
        )
    console.print(table)


def print_watch_header(
    sources: list[tuple[str, str]],
    *,
    db: Path,
    poll: float,
    webhook: str | None,
    include_edits: bool,
    once: bool,
    dry_run: bool,
) -> None:
    lines = [
        f"[bold]Sources:[/bold] {len(sources)}",
        *[f"  [cyan]{raw}[/cyan] → {resolved}" for raw, resolved in sources],
        f"[bold]Poll:[/bold] {poll:g}s    [bold]Edits:[/bold] {'on' if include_edits else 'off'}",
        f"[bold]State:[/bold] {db}",
        f"[bold]Webhook:[/bold] {webhook or '-'}",
        f"[bold]Mode:[/bold] {'once' if once else 'continuous'}{' / dry-run' if dry_run else ''}",
    ]
    console.print(Panel("\n".join(lines), title="Eitaa Next sync", border_style="cyan"))


def print_event(event: SyncEvent) -> None:
    kind = "NEW" if event.event_type == "new_message" else "EDIT"
    style = "bold green" if kind == "NEW" else "bold yellow"
    stamp = time.strftime("%H:%M:%S", time.localtime(event.date)) if event.date else "--:--:--"
    preview = " ".join(event.text.split())
    if len(preview) > 110:
        preview = preview[:107] + "..."
    media = f" [{event.media_type}]" if event.media_type else ""
    line = Text()
    line.append(f"{kind:<4}", style=style)
    line.append(f" {stamp} ", style="dim")
    line.append(f"#{event.message_id:<8}", style="cyan")
    line.append(f" {event.source} ", style="bold")
    line.append(preview or "<no text>")
    line.append(media, style="magenta")
    console.print(line)


def print_delivery_failures(rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[green]No failed deliveries.[/green]")
        return
    table = Table(title="Failed automation deliveries", show_lines=False, pad_edge=False)
    table.add_column("Rule", no_wrap=True)
    table.add_column("Action", justify="right")
    table.add_column("Attempts", justify="right")
    table.add_column("Error", overflow="ellipsis", max_width=70)
    table.add_column("Age", justify="right")
    for row in rows:
        table.add_row(
            str(row.get("rule_name") or ""),
            str(row.get("action_index") or 0),
            str(row.get("attempts") or 0),
            str(row.get("last_error") or ""),
            age_text(int(row.get("updated_at", 0) or 0)),
        )
    console.print(table)
