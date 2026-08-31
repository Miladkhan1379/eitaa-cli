from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import typer
from rich.table import Table

from eitaa_cli import __version__
from eitaa_cli.api_types import (
    ContactsSearchResponse,
    DialogsResponse,
    EntityObject,
    MessagesResponse,
    ParticipantsResponse,
    TLObject,
    TLValue,
    TransportKind,
    object_list,
    tl_from_json,
)
from eitaa_cli.cli.auth import auth_app
from eitaa_cli.cli.automation import automation_app
from eitaa_cli.cli.enhancements import register_enhancements
from eitaa_cli.cli.sync import sync_app
from eitaa_cli.cli.sources import sources_app
from eitaa_cli.cli.peers import peers_app
from eitaa_cli.cli.next import next_app
from eitaa_cli.cli.explore import explore_app
from eitaa_cli.cli.runtime import (
    CLIState,
    console,
)
from eitaa_cli.cli.runtime import (
    run as _run,
)
from eitaa_cli.cli.runtime import (
    state as _state,
)
from eitaa_cli.cli.runtime import (
    with_client as _with_client,
)
from eitaa_cli.client import EitaaClient
from eitaa_cli.config import EitaaSettings
from eitaa_cli.formatting import (
    entity_title,
    print_dialogs,
    print_entities,
    print_json,
    print_messages,
    print_participants,
)
from eitaa_cli.models.search import ChatSearchFilter, ParticipantFilter
from eitaa_cli.services.auth import normalize_phone
from eitaa_cli.services.messages import random_long
from eitaa_cli.services.peers import entity_to_input_peer
from eitaa_cli.tl import TLSchema
from eitaa_cli.tl.export import export_schema_files

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="Command-line client for Eitaa.",
)
chats_app = typer.Typer(
    no_args_is_help=True, help="Browse private chats, groups, supergroups, and channels."
)
dialogs_app = typer.Typer(no_args_is_help=True, help="Backward-compatible mixed dialog commands.")
messages_app = typer.Typer(
    no_args_is_help=True, help="Read, search, send, edit, forward, and delete messages."
)
media_app = typer.Typer(no_args_is_help=True, help="Upload, send, and download media files.")
contacts_app = typer.Typer(no_args_is_help=True, help="Search and manage contacts.")
groups_app = typer.Typer(
    no_args_is_help=True, help="Browse and manage classic groups and supergroups."
)
channels_app = typer.Typer(
    no_args_is_help=True, help="Browse and manage broadcast channels and supergroups."
)
links_app = typer.Typer(
    no_args_is_help=True, help="Resolve, inspect, join, and export Eitaa links."
)
raw_app = typer.Typer(no_args_is_help=True, help="Invoke any bundled TL method directly.")
schema_app = typer.Typer(no_args_is_help=True, help="Inspect the bundled layer-135 schema.")

app.add_typer(auth_app, name="auth")
app.add_typer(explore_app, name="explore")
app.add_typer(chats_app, name="chats")
app.add_typer(dialogs_app, name="dialogs")
app.add_typer(messages_app, name="messages")
app.add_typer(media_app, name="media")
app.add_typer(contacts_app, name="contacts")
app.add_typer(groups_app, name="groups")
app.add_typer(channels_app, name="channels")
app.add_typer(links_app, name="links")
app.add_typer(raw_app, name="raw")
app.add_typer(schema_app, name="schema")
app.add_typer(automation_app, name="automation")
app.add_typer(sync_app, name="sync")
app.add_typer(sources_app, name="sources")
app.add_typer(peers_app, name="peers")
app.add_typer(next_app, name="next")
register_enhancements(messages_app, media_app, chats_app, groups_app, channels_app)


@app.callback()
def root(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", "-p", help="Saved session profile."),
    session_file: Path | None = typer.Option(None, help="Override the session JSON path."),
    endpoint: str | None = typer.Option(None, help="Use one explicit /eitaa/ endpoint."),
    version: bool = typer.Option(False, "--version", is_eager=True),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    settings = EitaaSettings()
    if profile:
        settings.profile = profile
    if session_file:
        settings.session_file = session_file.expanduser()
    if endpoint:
        settings.endpoint = endpoint
    ctx.obj = CLIState(settings)


def _parse_chat_kind(value: str) -> set[str]:
    normalized = value.casefold().strip()
    choices = {
        "all": {"private", "group", "supergroup", "channel"},
        "private": {"private"},
        "group": {"group"},
        "groups": {"group", "supergroup"},
        "supergroup": {"supergroup"},
        "channel": {"channel"},
        "channels": {"channel"},
    }
    try:
        return choices[normalized]
    except KeyError as exc:
        raise ValueError(
            "kind must be one of: all, private, group, groups, supergroup, channel"
        ) from exc


def _list_conversations(
    ctx: typer.Context,
    *,
    limit: int,
    folder_id: int | None,
    kinds: set[str],
    query: str | None,
    unread_only: bool,
    json_output: bool,
    title: str,
) -> None:
    async def action(client: EitaaClient) -> DialogsResponse:
        return await client.dialogs.list(
            limit,
            folder_id=folder_id,
            kinds=kinds,
            query=query,
            unread_only=unread_only,
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else print_dialogs(result, title=title)


@chats_app.command("list")
def chats_list(
    ctx: typer.Context,
    limit: int = typer.Argument(50, min=1, max=500),
    kind: str = typer.Option("all", help="all, private, group, groups, supergroup, or channel"),
    query: str | None = typer.Option(
        None, "--query", "-q", help="Filter locally by title, name, username, or phone."
    ),
    unread_only: bool = typer.Option(
        False, "--unread-only", help="Only show conversations with unread messages."
    ),
    folder_id: int | None = typer.Option(None, help="Eitaa dialog folder ID."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List conversations with reusable peer references."""
    _list_conversations(
        ctx,
        limit=limit,
        folder_id=folder_id,
        kinds=_parse_chat_kind(kind),
        query=query,
        unread_only=unread_only,
        json_output=json_output,
        title="Eitaa chats",
    )


@chats_app.command("private")
def chats_private(
    ctx: typer.Context,
    limit: int = typer.Argument(50, min=1, max=500),
    query: str | None = typer.Option(None, "--query", "-q"),
    unread_only: bool = typer.Option(False, "--unread-only"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List one-to-one conversations."""
    _list_conversations(
        ctx,
        limit=limit,
        folder_id=None,
        kinds={"private"},
        query=query,
        unread_only=unread_only,
        json_output=json_output,
        title="Eitaa private chats",
    )


@chats_app.command("info")
def chats_info(
    ctx: typer.Context,
    peer: str,
    json_output: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Show full information for a user, classic group, supergroup, or channel."""

    async def action(client: EitaaClient) -> TLObject:
        return await client.dialogs.info(peer)

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else console.print(result)


@dialogs_app.command("list")
def dialogs_list(
    ctx: typer.Context,
    limit: int = typer.Argument(50, min=1, max=500),
    kind: str = typer.Option("all", help="all, private, group, groups, supergroup, or channel"),
    query: str | None = typer.Option(None, "--query", "-q"),
    unread_only: bool = typer.Option(False, "--unread-only"),
    folder_id: int | None = typer.Option(None),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Compatibility alias for `eitaa chats list`."""
    _list_conversations(
        ctx,
        limit=limit,
        folder_id=folder_id,
        kinds=_parse_chat_kind(kind),
        query=query,
        unread_only=unread_only,
        json_output=json_output,
        title="Eitaa dialogs",
    )


@messages_app.command("history")
def messages_history(
    ctx: typer.Context,
    peer: str,
    limit: int = typer.Argument(50, min=1, max=500),
    offset_id: int = typer.Option(0),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    async def action(client: EitaaClient) -> MessagesResponse:
        return await client.messages.history(peer, limit=limit, offset_id=offset_id)

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else print_messages(result)


@messages_app.command("search")
def messages_search(
    ctx: typer.Context,
    peer: str,
    query: str,
    content_filter: ChatSearchFilter = typer.Option(
        ChatSearchFilter.ALL,
        "--filter",
        help="all, photos, video, photo-video, document, url, gif, voice, music, chat-photos, calls, missed-calls, round-video, mentions, geo, contacts, or pinned.",
    ),
    from_peer: str | None = typer.Option(None, "--from", help="Only messages sent by this peer."),
    top_message_id: int | None = typer.Option(None, "--top-message-id", min=1),
    min_date: int = typer.Option(0, min=0, help="Minimum Unix timestamp."),
    max_date: int = typer.Option(0, min=0, help="Maximum Unix timestamp."),
    offset_id: int = typer.Option(0, min=0),
    add_offset: int = typer.Option(0),
    limit: int = typer.Option(50, min=1, max=500),
    max_id: int = typer.Option(0, min=0),
    min_id: int = typer.Option(0, min=0),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search within one chat, group, supergroup, or channel."""

    async def action(client: EitaaClient) -> MessagesResponse:
        return await client.messages.search(
            peer,
            query,
            content_filter=content_filter,
            from_reference=from_peer,
            top_message_id=top_message_id,
            min_date=min_date,
            max_date=max_date,
            offset_id=offset_id,
            add_offset=add_offset,
            limit=limit,
            max_id=max_id,
            min_id=min_id,
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else print_messages(result)


@messages_app.command("send")
def messages_send(
    ctx: typer.Context,
    peer: str,
    text: str,
    reply_to: int | None = typer.Option(None),
    silent: bool = typer.Option(False),
    no_webpage: bool = typer.Option(False),
    yes: bool = typer.Option(False, "--yes", "-y"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if not yes and not typer.confirm(f"Send to {peer!r}?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.messages.send_text(
            peer, text, reply_to=reply_to, silent=silent, no_webpage=no_webpage
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Message sent.")


@messages_app.command("edit")
def messages_edit(
    ctx: typer.Context,
    peer: str,
    message_id: int,
    text: str,
    yes: bool = typer.Option(False, "--yes", "-y"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if not yes and not typer.confirm(f"Edit message {message_id} in {peer!r}?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.messages.edit(peer, message_id, text)

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Message edited.")


@messages_app.command("delete")
def messages_delete(
    ctx: typer.Context,
    message_ids: list[int],
    peer: str | None = typer.Option(None, help="Required for channel messages."),
    revoke: bool = typer.Option(True, "--revoke/--no-revoke"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if not yes and not typer.confirm(f"Delete message(s) {message_ids}?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.messages.delete(message_ids, peer_reference=peer, revoke=revoke)

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Message(s) deleted.")


@messages_app.command("forward")
def messages_forward(
    ctx: typer.Context,
    source: str,
    destination: str,
    message_ids: list[int],
    silent: bool = typer.Option(False),
    yes: bool = typer.Option(False, "--yes", "-y"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if not yes and not typer.confirm(f"Forward {message_ids} from {source!r} to {destination!r}?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.messages.forward(source, destination, message_ids, silent=silent)

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Message(s) forwarded.")


@media_app.command("send")
def media_send(
    ctx: typer.Context,
    peer: str,
    file: Path,
    caption: str = typer.Option(""),
    reply_to: int | None = typer.Option(None),
    as_document: bool = typer.Option(False),
    voice: bool = typer.Option(False),
    duration: int = typer.Option(0),
    width: int = typer.Option(0),
    height: int = typer.Option(0),
    silent: bool = typer.Option(False),
    yes: bool = typer.Option(False, "--yes", "-y"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if not yes and not typer.confirm(f"Upload and send {file} to {peer!r}?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.media.send_file(
            peer,
            file,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            as_document=as_document,
            voice=voice,
            duration=duration,
            width=width,
            height=height,
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Media sent.")


@media_app.command("album")
def media_album(
    ctx: typer.Context,
    peer: str,
    files: list[Path],
    caption: str = typer.Option(""),
    reply_to: int | None = typer.Option(None),
    silent: bool = typer.Option(False),
    yes: bool = typer.Option(False, "--yes", "-y"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if not yes and not typer.confirm(
        f"Upload and send {len(files)} files to {peer!r} as an album?"
    ):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.media.send_album(
            peer, files, caption=caption, reply_to=reply_to, silent=silent
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Album sent.")


@media_app.command("download")
def media_download(
    ctx: typer.Context, peer: str, message_id: int, output: Path = Path("downloads")
) -> None:
    async def action(client: EitaaClient) -> Path:
        return await client.media.download_message(peer, message_id, output)

    path = _run(_with_client(_state(ctx).settings, action))
    typer.echo(str(path))


@contacts_app.command("search")
def contacts_search(
    ctx: typer.Context,
    query: str,
    limit: int = typer.Option(50, min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search Eitaa users, groups, supergroups, and channels."""

    async def action(client: EitaaClient) -> ContactsSearchResponse:
        return await client.search.entities(query, limit=limit)

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else print_entities(result, title="Eitaa contact search")


@contacts_app.command("list")
def contacts_list(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object("contacts.getContacts", {"hash": 0})

    result = _run(_with_client(_state(ctx).settings, action))
    users = [cast(EntityObject, user) for user in object_list(result, "users")]
    print_json(result) if json_output else contacts_search_table(users)


def contacts_search_table(users: list[EntityObject]) -> None:
    table = Table(title="Eitaa contacts")
    table.add_column("Name")
    table.add_column("Username")
    table.add_column("Phone")
    table.add_column("Peer JSON", overflow="fold")
    for user in users:
        try:
            peer_json = json.dumps(entity_to_input_peer(user), ensure_ascii=False)
        except ValueError:
            peer_json = "unresolvable"
        table.add_row(
            entity_title(user),
            str(user.get("username") or ""),
            str(user.get("phone") or ""),
            peer_json,
        )
    console.print(table)


@contacts_app.command("import-phone")
def contacts_import_phone(
    ctx: typer.Context,
    phone_number: str,
    first_name: str,
    last_name: str = "",
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object(
            "contacts.importContacts",
            {
                "contacts": [
                    {
                        "_": "inputPhoneContact",
                        "client_id": random_long(),
                        "phone": normalize_phone(phone_number),
                        "first_name": first_name,
                        "last_name": last_name,
                    }
                ]
            },
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Contact import completed.")


@contacts_app.command("add")
def contacts_add(
    ctx: typer.Context,
    peer: str,
    first_name: str,
    last_name: str = "",
    phone: str = "",
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        user = await client.peers.resolve_input_user(peer)
        return await client.invoke_object(
            "contacts.addContact",
            {
                "id": user,
                "first_name": first_name,
                "last_name": last_name,
                "phone": normalize_phone(phone) if phone else "",
            },
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Contact added.")


@contacts_app.command("delete")
def contacts_delete(
    ctx: typer.Context, peers: list[str], yes: bool = typer.Option(False, "--yes", "-y")
) -> None:
    if not yes and not typer.confirm(f"Delete {len(peers)} contact(s)?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        users = [await client.peers.resolve_input_user(peer) for peer in peers]
        return await client.invoke_object("contacts.deleteContacts", {"id": users})

    _run(_with_client(_state(ctx).settings, action))
    typer.echo("Contact(s) deleted.")


@groups_app.command("list")
def groups_list(
    ctx: typer.Context,
    limit: int = typer.Argument(100, min=1, max=500),
    query: str | None = typer.Option(None, "--query", "-q"),
    unread_only: bool = typer.Option(False, "--unread-only"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List classic groups and supergroups visible in the dialog list."""
    _list_conversations(
        ctx,
        limit=limit,
        folder_id=None,
        kinds={"group", "supergroup"},
        query=query,
        unread_only=unread_only,
        json_output=json_output,
        title="Eitaa groups and supergroups",
    )


@groups_app.command("create")
def groups_create(
    ctx: typer.Context,
    title: str,
    members: list[str],
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        users = [await client.peers.resolve_input_user(member) for member in members]
        return await client.invoke_object("messages.createChat", {"users": users, "title": title})

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Group created.")


@groups_app.command("info")
def groups_info(
    ctx: typer.Context, chat_id: int, json_output: bool = typer.Option(False, "--json")
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object("messages.getFullChat", {"chat_id": chat_id})

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result)


@groups_app.command("add-member")
def groups_add_member(ctx: typer.Context, chat_id: int, user: str, forward_limit: int = 50) -> None:
    async def action(client: EitaaClient) -> TLObject:
        input_user = await client.peers.resolve_input_user(user)
        return await client.invoke_object(
            "messages.addChatUser",
            {"chat_id": chat_id, "user_id": input_user, "fwd_limit": forward_limit},
        )

    _run(_with_client(_state(ctx).settings, action))
    typer.echo("Member added.")


@groups_app.command("remove-member")
def groups_remove_member(
    ctx: typer.Context, chat_id: int, user: str, revoke_history: bool = False
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        input_user = await client.peers.resolve_input_user(user)
        return await client.invoke_object(
            "messages.deleteChatUser",
            {"chat_id": chat_id, "user_id": input_user, "revoke_history": revoke_history},
        )

    _run(_with_client(_state(ctx).settings, action))
    typer.echo("Member removed.")


@channels_app.command("list")
def channels_list(
    ctx: typer.Context,
    limit: int = typer.Argument(100, min=1, max=500),
    query: str | None = typer.Option(None, "--query", "-q"),
    unread_only: bool = typer.Option(False, "--unread-only"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List broadcast channels visible in the dialog list."""
    _list_conversations(
        ctx,
        limit=limit,
        folder_id=None,
        kinds={"channel"},
        query=query,
        unread_only=unread_only,
        json_output=json_output,
        title="Eitaa channels",
    )


@channels_app.command("create")
def channels_create(
    ctx: typer.Context,
    title: str,
    about: str = "",
    supergroup: bool = typer.Option(False, "--supergroup"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object(
            "channels.createChannel",
            {"broadcast": not supergroup, "megagroup": supergroup, "title": title, "about": about},
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Channel/supergroup created.")


@channels_app.command("info")
def channels_info(
    ctx: typer.Context, channel: str, json_output: bool = typer.Option(False, "--json")
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        value = await client.peers.resolve_input_channel(channel)
        return await client.invoke_object("channels.getFullChannel", {"channel": value})

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result)


@channels_app.command("join")
def channels_join(
    ctx: typer.Context, channel: str, json_output: bool = typer.Option(False, "--json")
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        value = await client.peers.resolve_input_channel(channel)
        return await client.invoke_object("channels.joinChannel", {"channel": value})

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else typer.echo("Joined channel/supergroup.")


@channels_app.command("leave")
def channels_leave(
    ctx: typer.Context, channel: str, yes: bool = typer.Option(False, "--yes", "-y")
) -> None:
    if not yes and not typer.confirm(f"Leave {channel!r}?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        value = await client.peers.resolve_input_channel(channel)
        return await client.invoke_object("channels.leaveChannel", {"channel": value})

    _run(_with_client(_state(ctx).settings, action))
    typer.echo("Left channel/supergroup.")


@channels_app.command("members")
def channels_members(
    ctx: typer.Context,
    channel: str,
    participant_filter: ParticipantFilter = typer.Option(
        ParticipantFilter.RECENT,
        "--filter",
        help="recent, search, contacts, admins, bots, banned, kicked, or mentions.",
    ),
    query: str = typer.Option("", "--query", "-q"),
    top_message_id: int | None = typer.Option(None, min=1),
    limit: int = typer.Option(100, min=1, max=200),
    offset: int = typer.Option(0, min=0),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List or search members of a supergroup/channel."""

    async def action(client: EitaaClient) -> ParticipantsResponse:
        return await client.search.participants(
            channel,
            participant_filter=participant_filter,
            query=query,
            top_message_id=top_message_id,
            offset=offset,
            limit=limit,
        )

    result = _run(_with_client(_state(ctx).settings, action))
    print_json(result) if json_output else print_participants(result)


@channels_app.command("invite")
def channels_invite(ctx: typer.Context, channel: str, users: list[str]) -> None:
    async def action(client: EitaaClient) -> TLObject:
        value = await client.peers.resolve_input_channel(channel)
        input_users = [await client.peers.resolve_input_user(user) for user in users]
        return await client.invoke_object(
            "channels.inviteToChannel", {"channel": value, "users": input_users}
        )

    _run(_with_client(_state(ctx).settings, action))
    typer.echo("User(s) invited.")


def _invite_hash(value: str) -> str:
    text = value.strip().split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text.lstrip("+")


@links_app.command("resolve")
def links_resolve(ctx: typer.Context, username: str) -> None:
    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object(
            "contacts.resolveUsername", {"username": username.lstrip("@")}
        )

    print_json(_run(_with_client(_state(ctx).settings, action)))


@links_app.command("check")
def links_check(ctx: typer.Context, invite: str) -> None:
    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object(
            "messages.checkChatInvite", {"hash": _invite_hash(invite)}
        )

    print_json(_run(_with_client(_state(ctx).settings, action)))


@links_app.command("join")
def links_join(
    ctx: typer.Context,
    invite: str,
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    if not yes and not typer.confirm("Join the chat/channel represented by this invite?"):
        raise typer.Abort()

    async def action(client: EitaaClient) -> TLObject:
        return await client.invoke_object(
            "messages.importChatInvite", {"hash": _invite_hash(invite)}
        )

    print_json(_run(_with_client(_state(ctx).settings, action)))


@links_app.command("export")
def links_export(
    ctx: typer.Context,
    peer: str,
    expire_date: int | None = typer.Option(None, help="Unix timestamp."),
    usage_limit: int | None = typer.Option(None, min=1),
) -> None:
    async def action(client: EitaaClient) -> TLObject:
        input_peer = await client.peers.resolve(peer)
        params: TLObject = {"peer": input_peer}
        if expire_date is not None:
            params["expire_date"] = expire_date
        if usage_limit is not None:
            params["usage_limit"] = usage_limit
        return await client.invoke_object("messages.exportChatInvite", params)

    print_json(_run(_with_client(_state(ctx).settings, action)))


def _parse_transport_kind(value: str) -> TransportKind:
    if value in {"client", "upload", "download"}:
        return cast(TransportKind, value)
    raise ValueError("kind must be one of: client, upload, download")


@raw_app.command("invoke")
def raw_invoke(
    ctx: typer.Context,
    method: str,
    params: str = typer.Argument("{}", help="JSON object or @path/to/file.json"),
    kind: str = typer.Option("client", help="client, upload, or download endpoint pool."),
    unauthenticated: bool = typer.Option(
        False, "--unauthenticated", help="Send with an empty token."
    ),
) -> None:
    payload = _load_json_argument(params)

    async def action(client: EitaaClient) -> TLValue:
        return await client.invoke(
            method,
            payload,
            kind=_parse_transport_kind(kind),
            token="" if unauthenticated else None,
        )

    result = _run(_with_client(_state(ctx).settings, action, auth=not unauthenticated))
    print_json(result)


@schema_app.command("method")
def schema_method(name: str) -> None:
    schema = TLSchema.bundled()
    definition = schema.method(name)
    print_json(
        {
            "id": definition.id,
            "method": definition.name,
            "params": [{"name": p.name, "type": p.type} for p in definition.params],
            "type": definition.result_type,
        }
    )


@schema_app.command("constructor")
def schema_constructor(name: str) -> None:
    schema = TLSchema.bundled()
    definition = schema.constructor(name)
    print_json(
        {
            "id": definition.id,
            "predicate": definition.name,
            "params": [{"name": p.name, "type": p.type} for p in definition.params],
            "type": definition.result_type,
        }
    )


@schema_app.command("methods")
def schema_methods(prefix: str = "") -> None:
    """List bundled method names, optionally restricted by a prefix."""
    schema = TLSchema.bundled()
    for name in sorted(schema.methods_by_name):
        if name.startswith(prefix):
            typer.echo(name)


@schema_app.command("constructors")
def schema_constructors(prefix: str = "") -> None:
    """List bundled constructor names, optionally restricted by a prefix."""
    schema = TLSchema.bundled()
    for name in sorted(schema.constructors_by_name):
        if name.startswith(prefix):
            typer.echo(name)


@schema_app.command("stats")
def schema_stats() -> None:
    """Show schema layer and definition counts."""
    schema = TLSchema.bundled()
    print_json(
        {
            "layer": schema.layer,
            "api": {
                "constructors": len(schema.raw["API"]["constructors"]),
                "methods": len(schema.raw["API"]["methods"]),
            },
            "mtproto": {
                "constructors": len(schema.raw["MTProto"]["constructors"]),
                "methods": len(schema.raw["MTProto"]["methods"]),
            },
            "wire_format": "TL (Type Language), not Protocol Buffers",
        }
    )


@schema_app.command("export")
def schema_export(output: Path = typer.Argument(Path("schemas-export"))) -> None:
    """Export the authoritative JSON and readable .tl schema files."""
    schema = TLSchema.bundled()
    paths = export_schema_files(schema.raw, output.expanduser())
    for path in paths:
        typer.echo(str(path))


def _load_json_argument(value: str) -> TLObject:
    text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    parsed = tl_from_json(json.loads(text), context="raw params")
    if not isinstance(parsed, dict):
        raise ValueError("raw params must be a JSON object")
    return parsed


if __name__ == "__main__":
    app()
