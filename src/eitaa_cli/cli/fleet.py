from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.panel import Panel

from eitaa_cli.cli.pretty import console, print_event
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.client import EitaaClient
from eitaa_cli.config import EitaaSettings
from eitaa_cli.session import SessionStore
from eitaa_cli.sync_engine import IncrementalSync, SyncEvent, SyncStore


fleet_app = typer.Typer(
    no_args_is_help=True,
    help="Run sync across multiple saved account profiles in one process.",
)


def _profile_db(base: Path, profile: str) -> Path:
    path = base.expanduser().resolve()
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in profile)
    return path.with_name(f"{path.stem}.{safe}{path.suffix or '.db'}")


async def _post_payload(url: str, payload: dict[str, Any], *, secret: str, retries: int) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Eitaa-Profile": str(payload.get("profile") or "")}
    event_id = str(payload.get("event_id") or "")
    if event_id:
        headers["X-Eitaa-Event-ID"] = event_id
    if secret:
        headers["X-Eitaa-Signature"] = "sha256=" + hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
    async with httpx.AsyncClient(timeout=15) as http:
        last: Exception | None = None
        for attempt in range(max(0, retries) + 1):
            try:
                response = await http.post(url, content=body, headers=headers)
                response.raise_for_status()
                return
            except (httpx.HTTPError, OSError) as exc:
                last = exc
                if attempt >= retries:
                    break
                await asyncio.sleep(min(15.0, 2**attempt) + random.random() * 0.25)
        if last:
            raise last


@fleet_app.command("watch")
def fleet_watch(
    ctx: typer.Context,
    sources: list[str] = typer.Argument(..., help="One or more source aliases/usernames/typed peers."),
    profile: list[str] = typer.Option([], "--profile", "-p", help="Repeat for each account; default=all authenticated profiles."),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    poll: float = typer.Option(5.0, "--poll", min=2.0),
    webhook: str | None = typer.Option(None, "--webhook"),
    secret: str = typer.Option("", "--secret"),
    once: bool = typer.Option(False, "--once"),
) -> None:
    """Watch the same sources across multiple logged-in Eitaa profiles."""
    base_settings = _state(ctx).settings
    sessions = SessionStore(base_settings.session_file)
    _active, saved = sessions.list_profiles()
    available = {item.name: item for item in saved if item.authenticated}
    profiles = profile or sorted(available)
    unknown = [name for name in profiles if name not in available]
    if unknown:
        raise typer.BadParameter(f"unknown or unauthenticated profile(s): {', '.join(unknown)}")
    base_db = db.expanduser().resolve()
    with SyncStore(base_db) as registry:
        resolved_sources: list[str] = []
        for source in sources:
            if source.casefold().startswith("source:"):
                alias = source.split(":", 1)[1].strip().casefold()
                row = registry.get_registered_source(alias)
                if row is None:
                    raise typer.BadParameter(f"unknown source alias: {alias}")
                # Prefer the original public username/link so each account obtains
                # its own valid access hash. Private peers may still require a
                # per-account typed peer if Eitaa treats access hashes per account.
                resolved_sources.append(str(row.get("original") or row.get("peer") or ""))
            else:
                resolved_sources.append(registry.resolve_source(source))

    async def run_profile(name: str) -> None:
        settings = replace(base_settings, profile=name)
        client = await EitaaClient.create(settings, require_auth=True)
        state_db = _profile_db(base_db, name)
        store = SyncStore(state_db)
        engine = IncrementalSync(client, store)
        try:
            async with client:
                while True:
                    for source in resolved_sources:
                        events, newest = await engine.poll_source(source)
                        for event in events:
                            console.print(f"[bold cyan][{name}][/bold cyan]", end=" ")
                            print_event(event)
                            if webhook:
                                payload = event.as_dict()
                                payload["profile"] = name
                                payload["sent_at"] = int(time.time())
                                await _post_payload(webhook, payload, secret=secret, retries=3)
                        engine.acknowledge(source, events, newest)
                    if once:
                        return
                    await asyncio.sleep(poll)
        finally:
            store.close()

    async def action() -> None:
        console.print(
            Panel(
                f"Profiles: {', '.join(profiles)}\nSources: {', '.join(sources)}\nPoll: {poll:g}s\n"
                f"Per-account state: {base_db.stem}.PROFILE{base_db.suffix or '.db'}",
                title="Eitaa Next multi-account fleet",
                border_style="cyan",
            )
        )
        tasks = [asyncio.create_task(run_profile(name), name=f"eitaa-{name}") for name in profiles]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    _run(action())
