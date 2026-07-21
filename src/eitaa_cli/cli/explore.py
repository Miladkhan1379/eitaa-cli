from __future__ import annotations

import asyncio
import json

import typer

from eitaa_cli.api_types import (
    CombinedExploreResult,
    ContactsSearchResponse,
    MessagesResponse,
    ParticipantsResponse,
    ResolvedPeerResponse,
    TopPeersResponse,
)
from eitaa_cli.cli.runtime import console, run, state, with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.formatting import (
    print_entities,
    print_json,
    print_participants,
    print_search_messages,
    print_top_peers,
)
from eitaa_cli.models.search import (
    GlobalSearchFilter,
    GlobalSearchScope,
    ParticipantFilter,
    SearchCursor,
    TopPeerCategory,
)
from eitaa_cli.services.search import next_search_cursor

explore_app = typer.Typer(
    no_args_is_help=True,
    help="Discover public/private content, entities, frequent peers, and members.",
)


async def _global_search(
    client: EitaaClient,
    *,
    query: str,
    scope: GlobalSearchScope,
    content_filter: GlobalSearchFilter,
    limit: int,
    offset_date: int,
    offset_peer: str | None,
    offset_id: int,
) -> MessagesResponse:
    peer = (
        await client.peers.resolve(offset_peer)
        if offset_peer is not None
        else {"_": "inputPeerEmpty"}
    )
    return await client.search.global_messages(
        query,
        scope=scope,
        content_filter=content_filter,
        limit=limit,
        cursor=SearchCursor(
            offset_date=offset_date,
            offset_peer=peer,
            offset_id=offset_id,
        ),
    )


def _print_next_cursor(result: MessagesResponse) -> None:
    cursor = next_search_cursor(result)
    if cursor is None:
        return
    console.print(
        "[dim]next cursor: "
        f"--offset-date {cursor.offset_date} "
        f"--offset-id {cursor.offset_id} "
        f"--offset-peer '{json.dumps(cursor.offset_peer, ensure_ascii=False)}'[/dim]"
    )


@explore_app.command("search")
def explore_search(
    ctx: typer.Context,
    query: str,
    scope: GlobalSearchScope = typer.Option(
        GlobalSearchScope.GLOBAL,
        "--scope",
        help="private, public, or global Eitaa discovery scope.",
    ),
    content_filter: GlobalSearchFilter = typer.Option(
        GlobalSearchFilter.ALL,
        "--filter",
        help="all, text, image, file, video, or music.",
    ),
    limit: int = typer.Option(50, min=1, max=500),
    offset_date: int = typer.Option(0, min=0),
    offset_peer: str | None = typer.Option(
        None,
        help="Peer reference from the previous page; JSON input peers are accepted.",
    ),
    offset_id: int = typer.Option(0, min=0),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search messages across private chats, public content, or both."""

    async def action(client: EitaaClient) -> MessagesResponse:
        return await _global_search(
            client,
            query=query,
            scope=scope,
            content_filter=content_filter,
            limit=limit,
            offset_date=offset_date,
            offset_peer=offset_peer,
            offset_id=offset_id,
        )

    result = run(with_client(state(ctx).settings, action))
    if json_output:
        cursor = next_search_cursor(result)
        payload: dict[str, object] = dict(result)
        payload["_next_cursor"] = cursor.to_params() if cursor else None
        print_json(payload)
    else:
        print_search_messages(result, title=f"Eitaa {scope.value} search: {query}")
        _print_next_cursor(result)


@explore_app.command("entities")
def explore_entities(
    ctx: typer.Context,
    query: str,
    limit: int = typer.Option(50, min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search users, groups, supergroups, and channels."""

    async def action(client: EitaaClient) -> ContactsSearchResponse:
        return await client.search.entities(query, limit=limit)

    result = run(with_client(state(ctx).settings, action))
    print_json(result) if json_output else print_entities(result)


@explore_app.command("all")
def explore_all(
    ctx: typer.Context,
    query: str,
    scope: GlobalSearchScope = typer.Option(GlobalSearchScope.GLOBAL, "--scope"),
    content_filter: GlobalSearchFilter = typer.Option(GlobalSearchFilter.ALL, "--filter"),
    limit: int = typer.Option(25, min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run entity discovery and message discovery together."""

    async def action(client: EitaaClient) -> CombinedExploreResult:
        entities, messages = await asyncio.gather(
            client.search.entities(query, limit=limit),
            client.search.global_messages(
                query,
                scope=scope,
                content_filter=content_filter,
                limit=limit,
            ),
        )
        return {"entities": entities, "messages": messages}

    result = run(with_client(state(ctx).settings, action))
    if json_output:
        print_json(result)
    else:
        print_entities(result["entities"], title=f"Entities matching: {query}")
        print_search_messages(result["messages"], title=f"Messages matching: {query}")
        _print_next_cursor(result["messages"])


@explore_app.command("username")
def explore_username(
    ctx: typer.Context,
    username: str,
    json_output: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Resolve one exact public username."""

    async def action(client: EitaaClient) -> ResolvedPeerResponse:
        return await client.search.resolve_username(username)

    result = run(with_client(state(ctx).settings, action))
    print_json(result) if json_output else console.print(result)


@explore_app.command("top")
def explore_top(
    ctx: typer.Context,
    categories: list[TopPeerCategory] = typer.Option(
        [TopPeerCategory.CORRESPONDENTS],
        "--category",
        help="Repeat for multiple categories.",
    ),
    offset: int = typer.Option(0, min=0),
    limit: int = typer.Option(25, min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show frequently contacted peers, groups, channels, bots, or calls."""

    async def action(client: EitaaClient) -> TopPeersResponse:
        return await client.search.top_peers(categories, offset=offset, limit=limit)

    result = run(with_client(state(ctx).settings, action))
    print_json(result) if json_output else print_top_peers(result)


@explore_app.command("members")
def explore_members(
    ctx: typer.Context,
    channel: str,
    participant_filter: ParticipantFilter = typer.Option(
        ParticipantFilter.RECENT,
        "--filter",
        help="recent, search, contacts, admins, bots, banned, kicked, or mentions.",
    ),
    query: str = typer.Option("", "--query", "-q"),
    top_message_id: int | None = typer.Option(None, min=1),
    offset: int = typer.Option(0, min=0),
    limit: int = typer.Option(100, min=1, max=200),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Explore members of a supergroup or channel."""

    async def action(client: EitaaClient) -> ParticipantsResponse:
        return await client.search.participants(
            channel,
            participant_filter=participant_filter,
            query=query,
            top_message_id=top_message_id,
            offset=offset,
            limit=limit,
        )

    result = run(with_client(state(ctx).settings, action))
    print_json(result) if json_output else print_participants(result)
