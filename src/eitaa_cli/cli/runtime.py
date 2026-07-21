from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import TypeVar

import typer
from rich.console import Console

from eitaa_cli.cli.error_reporting import render_error
from eitaa_cli.client import EitaaClient
from eitaa_cli.config import EitaaSettings
from eitaa_cli.errors import EitaaError

console = Console()
ResultT = TypeVar("ResultT")


@dataclass(slots=True)
class CLIState:
    settings: EitaaSettings


def state(ctx: typer.Context) -> CLIState:
    value = ctx.find_root().obj
    if not isinstance(value, CLIState):
        raise RuntimeError("CLI state has not been initialized")
    return value


def run(coroutine: Coroutine[object, object, ResultT]) -> ResultT:
    try:
        return asyncio.run(coroutine)
    except (EitaaError, ValueError, TypeError, KeyError, FileNotFoundError) as exc:
        render_error(console, exc)
        raise typer.Exit(1) from exc


async def with_client(
    settings: EitaaSettings,
    callback: Callable[[EitaaClient], Awaitable[ResultT]],
    *,
    auth: bool = True,
) -> ResultT:
    client = await EitaaClient.create(settings, require_auth=auth)
    async with client:
        return await callback(client)
