from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from eitaa_cli.api_types import (
    ContactsSearchResponse,
    EntityObject,
    MessagesResponse,
    ParticipantsResponse,
    PeerReference,
    ResolvedPeerResponse,
    TLObject,
    TopPeersResponse,
    int_field,
    object_field,
    object_list,
    str_field,
)
from eitaa_cli.models.search import (
    ChatSearchFilter,
    GlobalSearchFilter,
    GlobalSearchScope,
    ParticipantFilter,
    SearchCursor,
    TopPeerCategory,
)
from eitaa_cli.rpc import ServiceClient, invoke_object
from eitaa_cli.services.peers import entity_to_input_peer

_GLOBAL_SCOPE_FLAGS: dict[GlobalSearchScope, int] = {
    GlobalSearchScope.PRIVATE: 1 << 16,
    GlobalSearchScope.PUBLIC: 1 << 17,
    GlobalSearchScope.GLOBAL: 1 << 18,
}

_GLOBAL_FILTER_FLAGS: dict[GlobalSearchFilter, int] = {
    GlobalSearchFilter.ALL: 0,
    GlobalSearchFilter.TEXT: 1,
    GlobalSearchFilter.IMAGE: 2,
    GlobalSearchFilter.FILE: 8,
    GlobalSearchFilter.VIDEO: 16,
    GlobalSearchFilter.MUSIC: 32,
}

_CHAT_FILTERS: dict[ChatSearchFilter, TLObject] = {
    ChatSearchFilter.ALL: {"_": "inputMessagesFilterEmpty"},
    ChatSearchFilter.PHOTOS: {"_": "inputMessagesFilterPhotos"},
    ChatSearchFilter.VIDEO: {"_": "inputMessagesFilterVideo"},
    ChatSearchFilter.PHOTO_VIDEO: {"_": "inputMessagesFilterPhotoVideo"},
    ChatSearchFilter.DOCUMENT: {"_": "inputMessagesFilterDocument"},
    ChatSearchFilter.URL: {"_": "inputMessagesFilterUrl"},
    ChatSearchFilter.GIF: {"_": "inputMessagesFilterGif"},
    ChatSearchFilter.VOICE: {"_": "inputMessagesFilterVoice"},
    ChatSearchFilter.MUSIC: {"_": "inputMessagesFilterMusic"},
    ChatSearchFilter.CHAT_PHOTOS: {"_": "inputMessagesFilterChatPhotos"},
    ChatSearchFilter.CALLS: {"_": "inputMessagesFilterPhoneCalls"},
    ChatSearchFilter.MISSED_CALLS: {"_": "inputMessagesFilterPhoneCalls", "missed": True},
    ChatSearchFilter.ROUND_VIDEO: {"_": "inputMessagesFilterRoundVideo"},
    ChatSearchFilter.MENTIONS: {"_": "inputMessagesFilterMyMentions"},
    ChatSearchFilter.GEO: {"_": "inputMessagesFilterGeo"},
    ChatSearchFilter.CONTACTS: {"_": "inputMessagesFilterContacts"},
    ChatSearchFilter.PINNED: {"_": "inputMessagesFilterPinned"},
}

_TOP_PEER_FLAGS: dict[TopPeerCategory, str] = {
    TopPeerCategory.CORRESPONDENTS: "correspondents",
    TopPeerCategory.BOTS: "bots_pm",
    TopPeerCategory.INLINE_BOTS: "bots_inline",
    TopPeerCategory.CALLS: "phone_calls",
    TopPeerCategory.FORWARD_USERS: "forward_users",
    TopPeerCategory.FORWARD_CHATS: "forward_chats",
    TopPeerCategory.GROUPS: "groups",
    TopPeerCategory.CHANNELS: "channels",
}


class SearchService:
    """High-level search and discovery workflows for Eitaa."""

    def __init__(self, client: ServiceClient) -> None:
        self.client = client

    async def global_messages(
        self,
        query: str,
        *,
        scope: GlobalSearchScope = GlobalSearchScope.GLOBAL,
        content_filter: GlobalSearchFilter = GlobalSearchFilter.ALL,
        limit: int = 50,
        cursor: SearchCursor | None = None,
    ) -> MessagesResponse:
        if not query.strip():
            raise ValueError("global search query cannot be empty")
        _validate_limit(limit, maximum=500)
        active_cursor = cursor or SearchCursor()
        params: TLObject = {
            "flags": _GLOBAL_SCOPE_FLAGS[scope] + _GLOBAL_FILTER_FLAGS[content_filter],
            "q": query,
            "limit": limit,
            **active_cursor.to_params(),
        }
        return cast(
            MessagesResponse,
            await invoke_object(self.client, "messages.searchGlobalExt", params),
        )

    async def in_chat_messages(
        self,
        peer_reference: PeerReference,
        query: str,
        *,
        content_filter: ChatSearchFilter = ChatSearchFilter.ALL,
        from_reference: PeerReference | None = None,
        top_message_id: int | None = None,
        min_date: int = 0,
        max_date: int = 0,
        offset_id: int = 0,
        add_offset: int = 0,
        limit: int = 50,
        max_id: int = 0,
        min_id: int = 0,
    ) -> MessagesResponse:
        _validate_limit(limit, maximum=500)
        peer = await self.client.peers.resolve(peer_reference)
        params: TLObject = {
            "peer": peer,
            "q": query,
            "filter": chat_filter_to_tl(content_filter),
            "min_date": min_date,
            "max_date": max_date,
            "offset_id": offset_id,
            "add_offset": add_offset,
            "limit": limit,
            "max_id": max_id,
            "min_id": min_id,
            "hash": 0,
        }
        if from_reference is not None:
            params["from_id"] = await self.client.peers.resolve(from_reference)
        if top_message_id is not None:
            params["top_msg_id"] = top_message_id
        return cast(
            MessagesResponse,
            await invoke_object(self.client, "messages.search", params),
        )

    async def entities(self, query: str, *, limit: int = 50) -> ContactsSearchResponse:
        if not query.strip():
            raise ValueError("entity search query cannot be empty")
        _validate_limit(limit, maximum=100)
        return cast(
            ContactsSearchResponse,
            await invoke_object(self.client, "contacts.search", {"q": query, "limit": limit}),
        )

    async def resolve_username(self, username: str) -> ResolvedPeerResponse:
        value = username.strip().lstrip("@")
        if not value:
            raise ValueError("username cannot be empty")
        return cast(
            ResolvedPeerResponse,
            await invoke_object(self.client, "contacts.resolveUsername", {"username": value}),
        )

    async def top_peers(
        self,
        categories: Iterable[TopPeerCategory] = (TopPeerCategory.CORRESPONDENTS,),
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> TopPeersResponse:
        _validate_limit(limit, maximum=100)
        selected = tuple(dict.fromkeys(categories))
        if not selected:
            raise ValueError("at least one top-peer category is required")
        params: TLObject = {"offset": offset, "limit": limit, "hash": 0}
        for category in selected:
            params[_TOP_PEER_FLAGS[category]] = True
        return cast(
            TopPeersResponse,
            await invoke_object(self.client, "contacts.getTopPeers", params),
        )

    async def participants(
        self,
        channel_reference: PeerReference,
        *,
        participant_filter: ParticipantFilter = ParticipantFilter.RECENT,
        query: str = "",
        top_message_id: int | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> ParticipantsResponse:
        _validate_limit(limit, maximum=200)
        channel = await self.client.peers.resolve_input_channel(channel_reference)
        filter_object = participant_filter_to_tl(
            participant_filter,
            query=query,
            top_message_id=top_message_id,
        )
        return cast(
            ParticipantsResponse,
            await invoke_object(
                self.client,
                "channels.getParticipants",
                {
                    "channel": channel,
                    "filter": filter_object,
                    "offset": offset,
                    "limit": limit,
                    "hash": 0,
                },
            ),
        )


def chat_filter_to_tl(content_filter: ChatSearchFilter) -> TLObject:
    return dict(_CHAT_FILTERS[content_filter])


def participant_filter_to_tl(
    participant_filter: ParticipantFilter,
    *,
    query: str = "",
    top_message_id: int | None = None,
) -> TLObject:
    if participant_filter is ParticipantFilter.RECENT:
        return {"_": "channelParticipantsRecent"}
    if participant_filter is ParticipantFilter.ADMINS:
        return {"_": "channelParticipantsAdmins"}
    if participant_filter is ParticipantFilter.BOTS:
        return {"_": "channelParticipantsBots"}
    if participant_filter is ParticipantFilter.SEARCH:
        return {"_": "channelParticipantsSearch", "q": query}
    if participant_filter is ParticipantFilter.CONTACTS:
        return {"_": "channelParticipantsContacts", "q": query}
    if participant_filter is ParticipantFilter.BANNED:
        return {"_": "channelParticipantsBanned", "q": query}
    if participant_filter is ParticipantFilter.KICKED:
        return {"_": "channelParticipantsKicked", "q": query}
    if participant_filter is ParticipantFilter.MENTIONS:
        value: TLObject = {"_": "channelParticipantsMentions"}
        if query:
            value["q"] = query
        if top_message_id is not None:
            value["top_msg_id"] = top_message_id
        return value
    raise ValueError(f"unsupported participant filter: {participant_filter}")


def _validate_limit(limit: int, *, maximum: int) -> None:
    if limit < 1 or limit > maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")


def next_search_cursor(result: MessagesResponse) -> SearchCursor | None:
    messages = result.get("messages", [])
    if not messages:
        return None
    message = messages[-1]
    peer = object_field(cast(TLObject, message), "peer_id")
    peer_kind = str_field(peer, "_")
    identifier = (
        int_field(peer, "user_id") or int_field(peer, "chat_id") or int_field(peer, "channel_id")
    )
    entities = [
        cast(EntityObject, entity)
        for entity in (
            *object_list(cast(TLObject, result), "users"),
            *object_list(cast(TLObject, result), "chats"),
        )
    ]
    for entity in entities:
        predicate = entity.get("_", "")
        matches = (
            (peer_kind == "peerUser" and predicate in {"user", "userEmpty"})
            or (peer_kind == "peerChat" and predicate in {"chat", "chatEmpty", "chatForbidden"})
            or (peer_kind == "peerChannel" and predicate in {"channel", "channelForbidden"})
        )
        if matches and entity.get("id", 0) == identifier:
            return SearchCursor(
                offset_date=int_field(cast(TLObject, message), "date"),
                offset_peer=entity_to_input_peer(entity),
                offset_id=int_field(cast(TLObject, message), "id"),
            )
    return SearchCursor(
        offset_date=int_field(cast(TLObject, message), "date"),
        offset_peer={"_": "inputPeerEmpty"},
        offset_id=int_field(cast(TLObject, message), "id"),
    )
