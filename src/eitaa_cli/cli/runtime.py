from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import typer
from rich.console import Console

from eitaa_cli.client import EitaaClient
from eitaa_cli.config import EitaaSettings
from eitaa_cli.errors import EitaaError

console = Console()


@dataclass(slots=True)
class CLIState:
    settings: EitaaSettings


def state(ctx: typer.Context) -> CLIState:
    value = ctx.find_root().obj
    if not isinstance(value, CLIState):
        raise RuntimeError("CLI state has not been initialized")
    return value


def run(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except (EitaaError, ValueError, KeyError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


async def with_client(settings: EitaaSettings, callback: Any, *, auth: bool = True) -> Any:
    async with EitaaClient(settings, require_auth=auth) as client:
        return await callback(client)
