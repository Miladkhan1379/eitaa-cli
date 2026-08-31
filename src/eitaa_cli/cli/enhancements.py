from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import typer

from eitaa_cli.api_types import DialogsResponse, MessagesResponse, TLObject, TLValue
from eitaa_cli.cli.runtime import run as _run
from eitaa_cli.cli.runtime import state as _state
from eitaa_cli.cli.runtime import with_client as _with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.formatting import print_dialogs, print_json, print_messages
from eitaa_cli.services.extras import ExtrasService


def _timestamp(value: str) -> int:
    text = value.strip()
    if text.isdigit():
        timestamp = int(text)
    else:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        timestamp = int(parsed.timestamp())
    if timestamp <= int(datetime.now().timestamp()):
        raise typer.BadParameter("scheduled time must be in the future")
    return timestamp


def register_enhancements(
    messages_app: typer.Typer,
    media_app: typer.Typer,
    chats_app: typer.Typer,
    groups_app: typer.Typer,
    channels_app: typer.Typer,
) -> None:
    @messages_app.command("schedule")
    def schedule_message(
        ctx: typer.Context,
        peer: str,
        text: str,
        at: str = typer.Option(..., "--at", help="Unix time or ISO local time, e.g. 2026-09-01 09:30"),
        reply_to: int | None = typer.Option(None),
        silent: bool = typer.Option(False),
        no_webpage: bool = typer.Option(False),
        noforwards: bool = typer.Option(False),
        yes: bool = typer.Option(False, "--yes", "-y"),
        json_output: bool = typer.Option(False, "--json"),
    ) -> None:
        """Schedule a text message on Eitaa's server."""
        schedule_date = _timestamp(at)
        if not yes and not typer.confirm(f"Schedule message to {peer!r} for {at}?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).schedule_text(
                peer,
                text,
                schedule_date=schedule_date,
                reply_to=reply_to,
                silent=silent,
                no_webpage=no_webpage,
                noforwards=noforwards,
            )

        result = _run(_with_client(_state(ctx).settings, action))
        print_json(result) if json_output else typer.echo("Message scheduled.")

    @messages_app.command("forward-at")
    def forward_at(
        ctx: typer.Context,
        source: str,
        destination: str,
        message_ids: list[int],
        at: str = typer.Option(..., "--at"),
        silent: bool = typer.Option(False),
        drop_author: bool = typer.Option(False, "--drop-author"),
        drop_media_captions: bool = typer.Option(False, "--drop-media-captions"),
        yes: bool = typer.Option(False, "--yes", "-y"),
    ) -> None:
        """Schedule one or more forwarded messages."""
        schedule_date = _timestamp(at)
        if not yes and not typer.confirm(
            f"Schedule forward of {message_ids} to {destination!r} for {at}?"
        ):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).schedule_forward(
                source,
                destination,
                message_ids,
                schedule_date=schedule_date,
                silent=silent,
                drop_author=drop_author,
                drop_media_captions=drop_media_captions,
            )

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Forward scheduled.")

    @messages_app.command("scheduled")
    def scheduled(ctx: typer.Context, peer: str, json_output: bool = typer.Option(False, "--json")) -> None:
        """List server-side scheduled messages for a conversation."""
        async def action(client: EitaaClient) -> MessagesResponse:
            return await ExtrasService(client).scheduled_history(peer)

        result = _run(_with_client(_state(ctx).settings, action))
        print_json(result) if json_output else print_messages(result)

    @messages_app.command("scheduled-send")
    def scheduled_send(
        ctx: typer.Context,
        peer: str,
        message_ids: list[int],
        yes: bool = typer.Option(False, "--yes", "-y"),
    ) -> None:
        """Send scheduled messages immediately."""
        if not yes and not typer.confirm(f"Send scheduled message(s) {message_ids} now?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).send_scheduled(peer, message_ids)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Scheduled message(s) sent.")

    @messages_app.command("scheduled-delete")
    def scheduled_delete(
        ctx: typer.Context,
        peer: str,
        message_ids: list[int],
        yes: bool = typer.Option(False, "--yes", "-y"),
    ) -> None:
        """Delete server-side scheduled messages."""
        if not yes and not typer.confirm(f"Delete scheduled message(s) {message_ids}?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).delete_scheduled(peer, message_ids)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Scheduled message(s) deleted.")

    @messages_app.command("pin")
    def pin_message(
        ctx: typer.Context,
        peer: str,
        message_id: int,
        silent: bool = typer.Option(False),
        yes: bool = typer.Option(False, "--yes", "-y"),
    ) -> None:
        if not yes and not typer.confirm(f"Pin message {message_id} in {peer!r}?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).pin(peer, message_id, silent=silent)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Message pinned.")

    @messages_app.command("unpin")
    def unpin_message(
        ctx: typer.Context,
        peer: str,
        message_id: int,
        yes: bool = typer.Option(False, "--yes", "-y"),
    ) -> None:
        if not yes and not typer.confirm(f"Unpin message {message_id} in {peer!r}?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).unpin(peer, message_id)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Message unpinned.")

    @messages_app.command("unpin-all")
    def unpin_all(
        ctx: typer.Context,
        peer: str,
        yes: bool = typer.Option(False, "--yes", "-y"),
    ) -> None:
        if not yes and not typer.confirm(f"Unpin all messages in {peer!r}?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).unpin_all(peer)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("All messages unpinned.")

    @messages_app.command("read")
    def mark_read(
        ctx: typer.Context,
        peer: str,
        max_id: int = typer.Option(0, help="Mark through this ID; 0 lets the server use current maximum."),
    ) -> None:
        """Mark a conversation as read."""
        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).mark_read(peer, max_id=max_id)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Marked as read.")

    @messages_app.command("draft-set")
    def draft_set(ctx: typer.Context, peer: str, text: str, reply_to: int | None = typer.Option(None)) -> None:
        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).save_draft(peer, text, reply_to=reply_to)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Draft saved.")

    @messages_app.command("drafts")
    def drafts(ctx: typer.Context) -> None:
        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).get_drafts()

        print_json(_run(_with_client(_state(ctx).settings, action)))

    @messages_app.command("draft-clear")
    def draft_clear(ctx: typer.Context, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
        if not yes and not typer.confirm("Clear all drafts?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).clear_drafts()

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Drafts cleared.")

    @messages_app.command("history-all")
    def history_all(
        ctx: typer.Context,
        peer: str,
        limit: int = typer.Option(1000, min=1),
        json_output: bool = typer.Option(False, "--json"),
    ) -> None:
        """Paginate message history beyond one API page."""
        async def action(client: EitaaClient) -> MessagesResponse:
            return await ExtrasService(client).history_all(peer, limit=limit)

        result = _run(_with_client(_state(ctx).settings, action))
        print_json(result) if json_output else print_messages(result)

    @messages_app.command("export")
    def export_history(
        ctx: typer.Context,
        peer: str,
        output: Path,
        limit: int = typer.Option(5000, "--limit", min=1),
        format: str = typer.Option("jsonl", "--format", help="jsonl or json"),
    ) -> None:
        """Export paginated message history for local analysis/backup."""
        normalized = format.casefold().strip()
        if normalized not in {"jsonl", "json"}:
            raise typer.BadParameter("format must be jsonl or json")

        async def action(client: EitaaClient) -> MessagesResponse:
            return await ExtrasService(client).history_all(peer, limit=limit)

        result = _run(_with_client(_state(ctx).settings, action))
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        messages = result.get("messages", [])
        if normalized == "json":
            output.write_text(
                json.dumps(messages, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        else:
            with output.open("w", encoding="utf-8") as handle:
                for message in messages:
                    handle.write(
                        json.dumps(message, ensure_ascii=False, separators=(",", ":"), default=str)
                        + "\n"
                    )
        typer.echo(f"Exported {len(messages)} message(s) to {output}")

    @media_app.command("schedule")
    def schedule_media(
        ctx: typer.Context,
        peer: str,
        file: Path,
        at: str = typer.Option(..., "--at", help="Unix time or ISO local time."),
        caption: str = typer.Option(""),
        reply_to: int | None = typer.Option(None),
        as_document: bool = typer.Option(False),
        voice: bool = typer.Option(False),
        duration: int = typer.Option(0),
        width: int = typer.Option(0),
        height: int = typer.Option(0),
        silent: bool = typer.Option(False),
        noforwards: bool = typer.Option(False),
        yes: bool = typer.Option(False, "--yes", "-y"),
        json_output: bool = typer.Option(False, "--json"),
    ) -> None:
        """Upload and schedule a photo/document/audio/video on Eitaa's server."""
        schedule_date = _timestamp(at)
        if not yes and not typer.confirm(f"Schedule {file} to {peer!r} for {at}?"):
            raise typer.Abort()

        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).schedule_file(
                peer,
                file,
                schedule_date=schedule_date,
                caption=caption,
                reply_to=reply_to,
                as_document=as_document,
                voice=voice,
                duration=duration,
                width=width,
                height=height,
                silent=silent,
                noforwards=noforwards,
            )

        result = _run(_with_client(_state(ctx).settings, action))
        print_json(result) if json_output else typer.echo("Media scheduled.")

    @media_app.command("profile-photo")
    def profile_photo(
        ctx: typer.Context,
        peer: str,
        output: Path = typer.Option(Path("downloads/profile"), "--output", "-o"),
    ) -> None:
        """Download the current profile/chat/channel photo."""
        async def action(client: EitaaClient) -> Path:
            return await ExtrasService(client).download_profile_photo(peer, output)

        path = _run(_with_client(_state(ctx).settings, action))
        typer.echo(str(path))

    @media_app.command("download-all")
    def download_all(
        ctx: typer.Context,
        peer: str,
        output: Path = typer.Option(Path("downloads"), "--output", "-o"),
        limit: int = typer.Option(500, min=1),
        json_output: bool = typer.Option(False, "--json"),
    ) -> None:
        """Download photo/document media from paginated chat history."""
        async def action(client: EitaaClient) -> list[Path]:
            return await ExtrasService(client).download_history_media(
                peer, output, limit=limit
            )

        paths = _run(_with_client(_state(ctx).settings, action))
        if json_output:
            print_json([str(path) for path in paths])
        else:
            for path in paths:
                typer.echo(str(path))
            typer.echo(f"Downloaded {len(paths)} file(s).")

    @chats_app.command("folders")
    def folders(ctx: typer.Context) -> None:
        """List Eitaa dialog filters/folders."""
        async def action(client: EitaaClient) -> TLValue:
            return await ExtrasService(client).dialog_filters()

        print_json(_run(_with_client(_state(ctx).settings, action)))

    @chats_app.command("archive")
    def archive(ctx: typer.Context, peer: str) -> None:
        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).set_folder(peer, folder_id=1)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Conversation archived.")

    @chats_app.command("unarchive")
    def unarchive(ctx: typer.Context, peer: str) -> None:
        async def action(client: EitaaClient) -> TLObject:
            return await ExtrasService(client).set_folder(peer, folder_id=0)

        _run(_with_client(_state(ctx).settings, action))
        typer.echo("Conversation moved to the main folder.")

    @channels_app.command("archived")
    def channels_archived(
        ctx: typer.Context,
        limit: int = typer.Argument(300, min=1, max=5000),
        json_output: bool = typer.Option(False, "--json"),
    ) -> None:
        async def action(client: EitaaClient) -> DialogsResponse:
            return await client.dialogs.channels(limit, folder_id=1)

        result = _run(_with_client(_state(ctx).settings, action))
        print_json(result) if json_output else print_dialogs(result, title="Archived Eitaa channels")

    @groups_app.command("archived")
    def groups_archived(
        ctx: typer.Context,
        limit: int = typer.Argument(300, min=1, max=5000),
        json_output: bool = typer.Option(False, "--json"),
    ) -> None:
        async def action(client: EitaaClient) -> DialogsResponse:
            return await client.dialogs.groups(limit, folder_id=1)

        result = _run(_with_client(_state(ctx).settings, action))
        print_json(result) if json_output else print_dialogs(result, title="Archived Eitaa groups")
