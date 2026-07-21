from __future__ import annotations

import secrets
from typing import cast

from eitaa_cli.api_types import (
    MessageObject,
    MessagesResponse,
    PeerReference,
    TLObject,
    int_field,
    object_list,
)
from eitaa_cli.models.search import ChatSearchFilter
from eitaa_cli.rpc import ServiceClient, invoke_object
from eitaa_cli.services.search import SearchService


class MessagesService:
    """Read and mutate messages through asynchronous TL RPC calls."""

    def __init__(self, client: ServiceClient) -> None:
        self.client = client

    async def history(
        self,
        peer_reference: PeerReference,
        *,
        limit: int = 50,
        offset_id: int = 0,
        offset_date: int = 0,
        add_offset: int = 0,
        max_id: int = 0,
        min_id: int = 0,
    ) -> MessagesResponse:
        peer = await self.client.peers.resolve(peer_reference)
        return cast(
            MessagesResponse,
            await invoke_object(
                self.client,
                "messages.getHistory",
                {
                    "peer": peer,
                    "offset_id": offset_id,
                    "offset_date": offset_date,
                    "add_offset": add_offset,
                    "limit": limit,
                    "max_id": max_id,
                    "min_id": min_id,
                    "hash": 0,
                },
            ),
        )

    async def search(
        self,
        peer_reference: PeerReference,
        query: str,
        *,
        content_filter: ChatSearchFilter = ChatSearchFilter.ALL,
        from_reference: PeerReference | None = None,
        top_message_id: int | None = None,
        min_date: int = 0,
        max_date: int = 0,
        limit: int = 50,
        offset_id: int = 0,
        add_offset: int = 0,
        max_id: int = 0,
        min_id: int = 0,
    ) -> MessagesResponse:
        return await SearchService(self.client).in_chat_messages(
            peer_reference,
            query,
            content_filter=content_filter,
            from_reference=from_reference,
            top_message_id=top_message_id,
            min_date=min_date,
            max_date=max_date,
            offset_id=offset_id,
            add_offset=add_offset,
            limit=limit,
            max_id=max_id,
            min_id=min_id,
        )

    async def send_text(
        self,
        peer_reference: PeerReference,
        text: str,
        *,
        reply_to: int | None = None,
        silent: bool = False,
        no_webpage: bool = False,
    ) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        params: TLObject = {
            "peer": peer,
            "message": text,
            "random_id": random_long(),
            "silent": silent,
            "no_webpage": no_webpage,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await invoke_object(self.client, "messages.sendMessage", params)

    async def edit(
        self,
        peer_reference: PeerReference,
        message_id: int,
        text: str,
        *,
        no_webpage: bool = False,
    ) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(
            self.client,
            "messages.editMessage",
            {"peer": peer, "id": message_id, "message": text, "no_webpage": no_webpage},
        )

    async def delete(
        self,
        message_ids: list[int],
        *,
        peer_reference: PeerReference | None = None,
        revoke: bool = True,
    ) -> TLObject:
        if not message_ids:
            raise ValueError("at least one message ID is required")
        if peer_reference is not None:
            peer = await self.client.peers.resolve(peer_reference)
            if peer["_"] == "inputPeerChannel":
                channel_peer = peer
                return await invoke_object(
                    self.client,
                    "channels.deleteMessages",
                    {
                        "channel": {
                            "_": "inputChannel",
                            "channel_id": channel_peer["channel_id"],
                            "access_hash": channel_peer["access_hash"],
                        },
                        "id": message_ids,
                    },
                )
        return await invoke_object(
            self.client, "messages.deleteMessages", {"id": message_ids, "revoke": revoke}
        )

    async def forward(
        self,
        source_reference: PeerReference,
        destination_reference: PeerReference,
        message_ids: list[int],
        *,
        silent: bool = False,
    ) -> TLObject:
        if not message_ids:
            raise ValueError("at least one message ID is required")
        source = await self.client.peers.resolve(source_reference)
        destination = await self.client.peers.resolve(destination_reference)
        return await invoke_object(
            self.client,
            "messages.forwardMessages",
            {
                "from_peer": source,
                "id": message_ids,
                "random_id": [random_long() for _ in message_ids],
                "to_peer": destination,
                "silent": silent,
            },
        )

    async def get_by_id(
        self,
        peer_reference: PeerReference,
        message_id: int,
    ) -> MessageObject | None:
        peer = await self.client.peers.resolve(peer_reference)
        if peer["_"] == "inputPeerChannel":
            channel_peer = peer
            result = await invoke_object(
                self.client,
                "channels.getMessages",
                {
                    "channel": {
                        "_": "inputChannel",
                        "channel_id": channel_peer["channel_id"],
                        "access_hash": channel_peer["access_hash"],
                    },
                    "id": [{"_": "inputMessageID", "id": message_id}],
                },
            )
        else:
            result = await invoke_object(
                self.client,
                "messages.getMessages",
                {"id": [{"_": "inputMessageID", "id": message_id}]},
            )
        for message in object_list(result, "messages"):
            if int_field(message, "id", default=-1) == message_id:
                return cast(MessageObject, message)
        return None


def random_long() -> int:
    value = secrets.randbits(63)
    return value or 1
