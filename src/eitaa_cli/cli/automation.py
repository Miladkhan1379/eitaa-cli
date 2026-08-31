from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import typer
from rich.table import Table

from eitaa_cli.automation import AutomationRunner, load_config, write_example
from eitaa_cli.cli.pretty import console, print_delivery_failures, print_sync_status
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.sync_engine import SyncStore


automation_app = typer.Typer(
    no_args_is_help=True,
    help="Durable automations for forwarding, downloads, replies, scheduling, and n8n webhooks.",
)


def _state_db(config: Path, data: dict[str, object]) -> Path:
    raw = Path(str(data.get("state_db") or ".eitaa-next.db"))
    return raw if raw.is_absolute() else config.expanduser().resolve().parent / raw


@automation_app.command("init")
def automation_init(path: Path = Path("automations.json")) -> None:
    """Write a safe example automation configuration."""
    target = write_example(path)
    console.print(f"[green]Created[/green] {target}")


@automation_app.command("check")
def automation_check(config: Path) -> None:
    """Validate an automation JSON file without connecting to Eitaa."""
    data = load_config(config)
    console.print(f"[green]OK[/green] {len(data['rules'])} rule(s) in {config}")


@automation_app.command("list")
def automation_list(config: Path) -> None:
    """Show automation rules in a compact readable table."""
    data = load_config(config)
    table = Table(title=f"Automation rules — {config.name}", pad_edge=False)
    table.add_column("Rule", style="bold cyan", no_wrap=True)
    table.add_column("Source(s)", overflow="fold", max_width=32)
    table.add_column("Events", overflow="fold", max_width=22)
    table.add_column("Filters", overflow="fold", max_width=34)
    table.add_column("Actions", overflow="fold", max_width=38)
    for rule in cast(list[dict[str, Any]], data["rules"]):
        raw_sources: list[str] = []
        if str(rule.get("source") or "").strip():
            raw_sources.append(str(rule["source"]))
        raw_sources.extend(str(item) for item in cast(list[Any], rule.get("sources") or []))
        filters: list[str] = []
        if rule.get("contains"):
            filters.append(f"contains={rule['contains']}")
        if rule.get("regex"):
            filters.append(f"regex={rule['regex']}")
        if rule.get("media_only"):
            filters.append("media-only")
        if rule.get("incoming_only", True):
            filters.append("incoming")
        actions = [str(item.get("type") or "") for item in cast(list[dict[str, Any]], rule["actions"])]
        table.add_row(
            str(rule["name"]),
            ", ".join(raw_sources),
            ", ".join(str(item) for item in rule.get("events", ["new_message"])),
            ", ".join(filters) or "-",
            " → ".join(actions),
        )
    console.print(table)


@automation_app.command("status")
def automation_status(config: Path) -> None:
    """Show checkpoints and delivery health for an automation configuration."""
    data = load_config(config)
    with SyncStore(_state_db(config, data)) as store:
        rows = store.status()
        stats = store.delivery_stats()
    console.print(
        f"[bold]{config.name}[/bold]  "
        f"[green]{stats['done']} delivered[/green]  "
        f"[red]{stats['failed']} failed[/red]"
    )
    print_sync_status(rows)


@automation_app.command("failures")
def automation_failures(
    config: Path,
    limit: int = typer.Option(20, "--limit", min=1, max=200),
) -> None:
    data = load_config(config)
    with SyncStore(_state_db(config, data)) as store:
        rows = store.failed_deliveries(limit)
    print_delivery_failures(rows)


@automation_app.command("reset-source")
def automation_reset_source(
    config: Path,
    source: str,
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Reset one source; its next cycle bootstraps without backfill."""
    data = load_config(config)
    db = _state_db(config, data)
    with SyncStore(db) as store:
        resolved = store.resolve_source(source)
    if not yes and not typer.confirm(f"Reset automation checkpoint for {source!r} ({resolved})?"):
        raise typer.Abort()
    with SyncStore(db) as store:
        store.reset_source(resolved)
    console.print("[green]Reset complete.[/green]")


@automation_app.command("run")
def automation_run(
    ctx: typer.Context,
    config: Path,
    once: bool = typer.Option(False, "--once", help="Run one polling cycle and exit."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show matching actions without sending/downloading/posting. Checkpoints are not advanced for matched events.",
    ),
) -> None:
    """Run automation rules. First run establishes checkpoints and performs no backfill."""
    data = load_config(config)

    async def action(client: EitaaClient) -> None:
        runner = AutomationRunner(
            client,
            data,
            config_path=config,
            dry_run=dry_run,
            log=console.print,
        )
        await runner.run(once=once)

    _run(_with_client(_state(ctx).settings, action))
