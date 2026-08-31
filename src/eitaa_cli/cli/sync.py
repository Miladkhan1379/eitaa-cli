from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import time
from pathlib import Path
from typing import Any, cast

import httpx
import typer

from eitaa_cli.api_types import TLObject
from eitaa_cli.cli.pretty import print_event, print_sync_status, print_watch_header
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.formatting import print_json
from eitaa_cli.hybrid_sync import HybridUpdateSync
from eitaa_cli.sync_engine import IncrementalSync, SyncEvent, SyncStore


sync_app = typer.Typer(
    no_args_is_help=True,
    help="Durable incremental sync/events for n8n and long-running automations.",
)


def _db_path(value: Path) -> Path:
    return value.expanduser().resolve()


@sync_app.command("init")
def sync_init(db: Path = typer.Option(Path(".eitaa-next.db"), "--db")) -> None:
    """Create/upgrade the local SQLite state database."""
    path = _db_path(db)
    with SyncStore(path):
        pass
    typer.echo(str(path))


@sync_app.command("status")
def sync_status(
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show persisted source checkpoints."""
    with SyncStore(_db_path(db)) as store:
        rows = store.status()
    if json_output:
        print_json(rows)
    else:
        print_sync_status(rows)


@sync_app.command("reset")
def sync_reset(
    source: str,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Forget one source checkpoint; next watch bootstraps at the newest message."""
    path = _db_path(db)
    with SyncStore(path) as store:
        resolved = store.resolve_source(source)
    if not yes and not typer.confirm(f"Reset sync checkpoint for {source!r} ({resolved})?"):
        raise typer.Abort()
    with SyncStore(path) as store:
        store.reset_source(resolved)
    typer.echo("Reset complete.")


async def _post_event(
    url: str,
    event: SyncEvent,
    *,
    secret: str,
    timeout: float,
    retries: int = 3,
) -> None:
    payload = event.as_dict()
    payload["sent_at"] = int(time.time())
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    headers = {
        "Content-Type": "application/json",
        "X-Eitaa-Event-ID": event.event_id,
        "X-Eitaa-Event-Type": event.event_type,
    }
    if secret:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Eitaa-Signature"] = f"sha256={digest}"

    retries = max(0, min(int(retries), 10))
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout) as http:
        for attempt in range(retries + 1):
            try:
                response = await http.post(url, content=body, headers=headers)
                response.raise_for_status()
                return
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                await asyncio.sleep(min(20.0, 2**attempt) + random.random() * 0.25)
    assert last_error is not None
    raise last_error


@sync_app.command("watch")
def sync_watch(
    ctx: typer.Context,
    sources: list[str] = typer.Argument(
        ...,
        help="username/@username, typed peer, or source:alias. On PowerShell prefer username without @.",
    ),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    poll: float = typer.Option(5.0, "--poll", min=2.0),
    webhook: str | None = typer.Option(None, "--webhook", help="Optional n8n/webhook URL."),
    secret: str = typer.Option("", "--secret", help="Optional HMAC webhook secret."),
    webhook_retries: int = typer.Option(3, "--webhook-retries", min=0, max=10),
    include_edits: bool = typer.Option(True, "--include-edits/--no-edits"),
    revisit: int = typer.Option(25, "--revisit", min=0, max=500),
    max_scan: int = typer.Option(5000, "--max-scan", min=100),
    once: bool = typer.Option(False, "--once"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Watch new messages with durable checkpoints; first run performs no backfill."""

    async def action(client: EitaaClient) -> None:
        path = _db_path(db)
        store = SyncStore(path)
        resolved_sources = [(source, store.resolve_source(source)) for source in sources]
        engine = IncrementalSync(
            client,
            store,
            max_scan_messages=max_scan,
            revisit_messages=revisit if include_edits else 0,
        )
        if not json_output:
            print_watch_header(
                resolved_sources,
                db=path,
                poll=poll,
                webhook=webhook,
                include_edits=include_edits,
                once=once,
                dry_run=dry_run,
            )
        try:
            while True:
                for _raw_source, resolved in resolved_sources:
                    events, newest = await engine.poll_source(resolved)
                    for event in events:
                        if not include_edits and event.event_type == "edited_message":
                            continue
                        if json_output:
                            print_json(event.as_dict())
                        else:
                            print_event(event)
                        if webhook and not dry_run:
                            await _post_event(
                                webhook,
                                event,
                                secret=secret,
                                timeout=15.0,
                                retries=webhook_retries,
                            )
                    if not dry_run:
                        engine.acknowledge(resolved, events, newest)
                if once:
                    return
                await asyncio.sleep(poll)
        finally:
            store.close()

    _run(_with_client(_state(ctx).settings, action))


@sync_app.command("probe-updates")
def probe_updates(
    ctx: typer.Context,
    difference: bool = typer.Option(
        False,
        "--difference",
        help="Also call updates.getDifference from the returned state (experimental).",
    ),
) -> None:
    """Probe Eitaa's raw updates state/difference support without enabling it for automation."""

    async def action(client: EitaaClient) -> dict[str, Any]:
        state_value = await client.invoke("updates.getState", {})
        result: dict[str, Any] = {"state": state_value}
        if difference and isinstance(state_value, dict):
            state = cast(TLObject, state_value)
            params: TLObject = {
                "pts": int(state.get("pts", 0) or 0),
                "date": int(state.get("date", 0) or 0),
                "qts": int(state.get("qts", 0) or 0),
            }
            result["difference"] = await client.invoke("updates.getDifference", params)
        return result

    print_json(_run(_with_client(_state(ctx).settings, action)))


@sync_app.command("hybrid")
def sync_hybrid(
    ctx: typer.Context,
    sources: list[str] = typer.Argument(..., help="Watched username/source alias/typed peers."),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    poll: float = typer.Option(5.0, "--poll", min=2.0),
    webhook: str | None = typer.Option(None, "--webhook"),
    secret: str = typer.Option("", "--secret"),
    once: bool = typer.Option(False, "--once"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Hybrid low-latency updates.getDifference + durable polling fallback."""

    async def action(client: EitaaClient) -> None:
        path = _db_path(db)
        store = SyncStore(path)
        resolved = [store.resolve_source(source) for source in sources]
        profile = _state(ctx).settings.profile or "default"
        engine = HybridUpdateSync(client, store, profile=profile)
        try:
            if not json_output:
                print_watch_header(
                    list(zip(sources, resolved)),
                    db=path,
                    poll=poll,
                    webhook=webhook,
                    include_edits=True,
                    once=once,
                    dry_run=False,
                )
                console.print(
                    "[cyan]Mode:[/cyan] hybrid updates.getDifference with automatic polling fallback"
                )
            while True:
                events, mode = await engine.poll(resolved)
                if not json_output and events:
                    console.print(f"[dim]update mode: {mode}[/dim]")
                for event in events:
                    if json_output:
                        payload = event.as_dict()
                        payload["sync_mode"] = mode
                        print_json(payload)
                    else:
                        print_event(event)
                    if webhook:
                        await _post_event(webhook, event, secret=secret, timeout=15.0, retries=3)
                if once:
                    return
                await asyncio.sleep(poll)
        finally:
            engine.close()
            store.close()

    _run(_with_client(_state(ctx).settings, action))


@sync_app.command("capabilities")
def sync_capabilities(ctx: typer.Context) -> None:
    """Probe raw update methods and report whether hybrid mode can be attempted."""
    async def action(client: EitaaClient) -> dict[str, Any]:
        result: dict[str, Any] = {"getState": False, "getDifference": False, "state": None, "error": ""}
        try:
            state = await client.invoke("updates.getState", {})
            result["getState"] = isinstance(state, dict)
            result["state"] = state
            if isinstance(state, dict):
                params: TLObject = {
                    "pts": int(state.get("pts", 0) or 0),
                    "date": int(state.get("date", 0) or 0),
                    "qts": int(state.get("qts", 0) or 0),
                }
                diff = await client.invoke("updates.getDifference", params)
                result["getDifference"] = isinstance(diff, dict)
                result["difference_type"] = diff.get("_") if isinstance(diff, dict) else type(diff).__name__
        except Exception as exc:
            result["error"] = str(exc)
        return result

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result)
