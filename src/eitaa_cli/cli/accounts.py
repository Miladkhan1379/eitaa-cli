from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from eitaa_cli.cli.pretty import console
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.config import EitaaSettings
from eitaa_cli.session import SessionStore


accounts_app = typer.Typer(
    no_args_is_help=True,
    help="Manage and verify multiple saved Eitaa account profiles.",
)


@accounts_app.command("list")
def accounts_list(ctx: typer.Context) -> None:
    settings = _state(ctx).settings
    store = SessionStore(settings.session_file)
    active, profiles = store.list_profiles()
    table = Table(title="Eitaa accounts", pad_edge=False)
    table.add_column("Active", justify="center", no_wrap=True)
    table.add_column("Profile", style="cyan", no_wrap=True)
    table.add_column("Phone", no_wrap=True)
    table.add_column("Authenticated", no_wrap=True)
    table.add_column("User ID", justify="right", no_wrap=True)
    for profile in profiles:
        user_id = ""
        if profile.user:
            user_id = str(profile.user.get("id", ""))
        table.add_row(
            "●" if profile.name == active else "",
            profile.name,
            profile.phone_number,
            "yes" if profile.authenticated else "no",
            user_id,
        )
    console.print(table)


@accounts_app.command("use")
def accounts_use(ctx: typer.Context, profile: str) -> None:
    settings = _state(ctx).settings
    store = SessionStore(settings.session_file)
    selected = store.set_active(profile)
    console.print(f"[green]Active account:[/green] {selected.name}")


@accounts_app.command("check")
def accounts_check(ctx: typer.Context, profiles: list[str] = typer.Argument([])) -> None:
    """Open a lightweight API session for one or more profiles and report health."""
    root_settings = _state(ctx).settings
    store = SessionStore(root_settings.session_file)
    _active, saved = store.list_profiles()
    names = profiles or [item.name for item in saved]
    saved_names = {item.name for item in saved}
    unknown = [name for name in names if name not in saved_names]
    if unknown:
        raise typer.BadParameter(f"unknown profile(s): {', '.join(unknown)}")

    rows: list[tuple[str, str, str]] = []
    for name in names:
        settings = EitaaSettings()
        settings.profile = name
        settings.session_file = root_settings.session_file
        settings.endpoint = root_settings.endpoint

        async def action(client: EitaaClient) -> dict[str, Any]:
            result = await client.dialogs.list(1)
            return {"dialogs": len(result.get("dialogs", []))}

        try:
            result = _run(_with_client(settings, action))
        except typer.Exit:
            rows.append((name, "FAIL", "authentication/API error"))
        else:
            rows.append((name, "OK", f"dialog probe={result['dialogs']}"))

    table = Table(title="Account health", pad_edge=False)
    table.add_column("Profile", style="cyan")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")
    for name, status, details in rows:
        style = "green" if status == "OK" else "red"
        table.add_row(name, f"[{style}]{status}[/{style}]", details)
    console.print(table)
