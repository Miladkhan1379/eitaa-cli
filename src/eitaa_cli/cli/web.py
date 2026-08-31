from __future__ import annotations

import secrets
from pathlib import Path

import typer

from eitaa_cli.cli.pretty import console
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.dashboard import serve_dashboard


web_app = typer.Typer(
    no_args_is_help=True,
    help="Local browser dashboard for accounts, sources, sync, downloads, failures and quick actions.",
)


@web_app.command("start")
def web_start(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port", min=1, max=65535),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    token: str = typer.Option("", "--token", help="Required when exposing beyond localhost."),
    automation: Path | None = typer.Option(Path("automations.json"), "--automation", help="Automation config shown in the dashboard."),
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and not token:
        token = secrets.token_urlsafe(24)
        console.print(f"[yellow]Generated access token:[/yellow] {token}")
    suffix = f"?token={token}" if token else ""
    console.print(f"[green]Eitaa Next dashboard:[/green] http://{host}:{port}/{suffix}")
    console.print("[dim]Ctrl+C to stop. Bind to localhost unless you know how the host is protected.[/dim]")
    serve_dashboard(settings=_state(ctx).settings, db=db, host=host, port=port, token=token, automation_config=automation)
