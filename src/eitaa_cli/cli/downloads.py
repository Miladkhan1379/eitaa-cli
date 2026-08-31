from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import typer
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from eitaa_cli.api_types import MessageObject
from eitaa_cli.cli.pretty import console
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.download_manager import DownloadStore, accepted_media, parse_kinds
from eitaa_cli.sync_engine import SyncStore


downloads_app = typer.Typer(
    no_args_is_help=True,
    help="Resumable bulk media jobs with filters, deduplication, progress, and failure tracking.",
)


def _unix(value: str | None) -> int:
    if not value:
        return 0
    text = value.strip()
    if text.isdigit():
        return int(text)
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(text, fmt).timestamp())
        except ValueError:
            pass
    raise typer.BadParameter("date must be Unix timestamp or YYYY-MM-DD[ HH:MM[:SS]]")


def _bytes_from_mb(value: float) -> int:
    return 0 if value <= 0 else int(value * 1024 * 1024)


@downloads_app.command("run")
def downloads_run(
    ctx: typer.Context,
    source: str,
    output: Path = typer.Option(Path("downloads"), "--output", "-o"),
    limit: int = typer.Option(5000, "--limit", min=1, max=100000),
    media_type: list[str] = typer.Option(["all"], "--type", help="all/photo/video/document/audio/voice/gif; repeatable"),
    after: str | None = typer.Option(None, "--after", help="YYYY-MM-DD or Unix timestamp"),
    before: str | None = typer.Option(None, "--before", help="YYYY-MM-DD or Unix timestamp"),
    max_size_mb: float = typer.Option(0.0, "--max-size-mb", min=0),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    fresh: bool = typer.Option(False, "--fresh", help="Ignore the existing job ledger and create a new job key."),
) -> None:
    """Download matching media while skipping items already completed by this job."""
    kinds = parse_kinds(media_type)
    min_date = _unix(after)
    max_date = _unix(before)
    if min_date and max_date and min_date > max_date:
        raise typer.BadParameter("--after cannot be later than --before")
    state_db = db.expanduser().resolve()
    output_dir = output.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with SyncStore(state_db) as sync_store:
        resolved = sync_store.resolve_source(source)
    filters = json.dumps(
        {
            "kinds": sorted(kinds),
            "after": min_date,
            "before": max_date,
            "max_bytes": _bytes_from_mb(max_size_mb),
        },
        sort_keys=True,
    )
    base_key = DownloadStore.make_job_key(resolved, output_dir, filters)
    job_key = f"{base_key}-{int(time.time())}" if fresh else base_key

    async def action(client: EitaaClient) -> dict[str, int]:
        with DownloadStore(state_db) as store:
            store.ensure_job(
                job_key,
                source=resolved,
                output_dir=output_dir,
                filters_json=filters,
            )
            scanned = matched = downloaded = skipped = failed = 0
            offset_id = 0
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            )
            task = progress.add_task("Scanning media", total=limit)
            with progress:
                while scanned < limit:
                    page_limit = min(100, limit - scanned)
                    result = await client.messages.history(
                        resolved, limit=page_limit, offset_id=offset_id
                    )
                    messages = [
                        cast(MessageObject, item)
                        for item in result.get("messages", [])
                        if int(item.get("id", 0) or 0) > 0
                    ]
                    if not messages:
                        break
                    ids = [int(item.get("id", 0)) for item in messages]
                    for message in messages:
                        scanned += 1
                        progress.update(task, completed=min(scanned, limit))
                        ok, kind = accepted_media(
                            message,
                            kinds=kinds,
                            min_date=min_date,
                            max_date=max_date,
                            max_bytes=_bytes_from_mb(max_size_mb),
                        )
                        if not ok:
                            continue
                        matched += 1
                        message_id = int(message.get("id", 0))
                        if store.is_done(job_key, message_id):
                            skipped += 1
                            continue
                        store.mark(
                            job_key,
                            message_id,
                            media_kind=kind,
                            status="running",
                        )
                        try:
                            path = await client.media.download_message(
                                resolved, message_id, output_dir
                            )
                        except Exception as exc:
                            failed += 1
                            store.mark(
                                job_key,
                                message_id,
                                media_kind=kind,
                                status="failed",
                                error=str(exc),
                            )
                        else:
                            downloaded += 1
                            store.mark(
                                job_key,
                                message_id,
                                media_kind=kind,
                                status="done",
                                path=str(path),
                            )
                    next_offset = min(ids)
                    if len(messages) < page_limit or next_offset == offset_id:
                        break
                    offset_id = next_offset
            return {
                "scanned": scanned,
                "matched": matched,
                "downloaded": downloaded,
                "skipped": skipped,
                "failed": failed,
            }

    result = _run(_with_client(_state(ctx).settings, action))
    console.print(
        f"[green]Done[/green] job={job_key} · scanned={result['scanned']} · "
        f"matched={result['matched']} · downloaded={result['downloaded']} · "
        f"skipped={result['skipped']} · [red]failed={result['failed']}[/red]"
    )


@downloads_app.command("status")
def downloads_status(db: Path = typer.Option(Path(".eitaa-next.db"), "--db")) -> None:
    with DownloadStore(db.expanduser().resolve()) as store:
        rows = store.job_rows()
    if not rows:
        console.print("[dim]No bulk download jobs yet.[/dim]")
        return
    table = Table(title="Bulk download jobs", pad_edge=False)
    table.add_column("Job", style="cyan", no_wrap=True)
    table.add_column("Source", overflow="ellipsis", max_width=38)
    table.add_column("Done", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Output", overflow="fold", max_width=45)
    for row in rows:
        table.add_row(
            str(row.get("job_key") or ""),
            str(row.get("source") or ""),
            str(row.get("done") or 0),
            str(row.get("failed") or 0),
            str(row.get("total") or 0),
            str(row.get("output_dir") or ""),
        )
    console.print(table)


@downloads_app.command("failures")
def downloads_failures(
    job: str,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
) -> None:
    with DownloadStore(db.expanduser().resolve()) as store:
        rows = store.failed_rows(job, limit)
    if not rows:
        console.print("[green]No failed media items for this job.[/green]")
        return
    table = Table(title=f"Download failures · {job}", pad_edge=False)
    table.add_column("Message", justify="right")
    table.add_column("Type")
    table.add_column("Attempts", justify="right")
    table.add_column("Error", overflow="fold", max_width=80)
    for row in rows:
        table.add_row(
            str(row.get("message_id") or 0),
            str(row.get("media_kind") or ""),
            str(row.get("attempts") or 0),
            str(row.get("last_error") or ""),
        )
    console.print(table)


@downloads_app.command("retry")
def downloads_retry(
    job: str,
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
) -> None:
    with DownloadStore(db.expanduser().resolve()) as store:
        count = store.reset_failed(job)
    console.print(f"[green]{count}[/green] failed item(s) marked for retry. Re-run the same download job.")
