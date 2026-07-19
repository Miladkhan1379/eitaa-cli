from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eitaa_cli.client import EitaaClient


class MessagesService:
    def __init__(self, client: EitaaClient) -> None:
        self.client = client

    async def history(
        self,
        peer_reference: str | dict[str, Any],
        *,
        limit: int = 50,
        offset_id: int = 0,
        offset_date: int = 0,
        add_offset: int = 0,
        max_id: int = 0,
        min_id: int = 0,
    ) -> dict[str, Any]:
        peer = await self.client.peers.resolve(peer_reference)
        return await self.client.invoke(
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
        )

    async def search(
        self,
        peer_reference: str | dict[str, Any],
        query: str,
        *,
        limit: int = 50,
        offset_id: int = 0,
    ) -> dict[str, Any]:
        peer = await self.client.peers.resolve(peer_reference)
        return await self.client.invoke(
            "messages.search",
            {
                "peer": peer,
                "q": query,
                "filter": {"_": "inputMessagesFilterEmpty"},
                "min_date": 0,
                "max_date": 0,
                "offset_id": offset_id,
                "add_offset": 0,
                "limit": limit,
                "max_id": 0,
                "min_id": 0,
                "hash": 0,
            },
        )

    async def send_text(
        self,
        peer_reference: str | dict[str, Any],
        text: str,
        *,
        reply_to: int | None = None,
        silent: bool = False,
        no_webpage: bool = False,
    ) -> dict[str, Any]:
        peer = await self.client.peers.resolve(peer_reference)
        params: dict[str, Any] = {
            "peer": peer,
            "message": text,
            "random_id": random_long(),
            "silent": silent,
            "no_webpage": no_webpage,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await self.client.invoke("messages.sendMessage", params)

    async def edit(
        self,
        peer_reference: str | dict[str, Any],
        message_id: int,
        text: str,
        *,
        no_webpage: bool = False,
    ) -> dict[str, Any]:
        peer = await self.client.peers.resolve(peer_reference)
        return await self.client.invoke(
            "messages.editMessage",
            {"peer": peer, "id": message_id, "message": text, "no_webpage": no_webpage},
        )

    async def delete(
        self,
        message_ids: list[int],
        *,
        peer_reference: str | dict[str, Any] | None = None,
        revoke: bool = True,
    ) -> dict[str, Any]:
        if peer_reference is not None:
            peer = await self.client.peers.resolve(peer_reference)
            if peer.get("_") == "inputPeerChannel":
                channel = {
                    "_": "inputChannel",
                    "channel_id": peer["channel_id"],
                    "access_hash": peer["access_hash"],
                }
                return await self.client.invoke(
                    "channels.deleteMessages", {"channel": channel, "id": message_ids}
                )
        return await self.client.invoke(
            "messages.deleteMessages", {"id": message_ids, "revoke": revoke}
        )

    async def forward(
        self,
        source_reference: str | dict[str, Any],
        destination_reference: str | dict[str, Any],
        message_ids: list[int],
        *,
        silent: bool = False,
    ) -> dict[str, Any]:
        source = await self.client.peers.resolve(source_reference)
        destination = await self.client.peers.resolve(destination_reference)
        return await self.client.invoke(
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
        self, peer_reference: str | dict[str, Any], message_id: int
    ) -> dict[str, Any] | None:
        peer = await self.client.peers.resolve(peer_reference)
        if peer.get("_") == "inputPeerChannel":
            result = await self.client.invoke(
                "channels.getMessages",
                {
                    "channel": {
                        "_": "inputChannel",
                        "channel_id": peer["channel_id"],
                        "access_hash": peer["access_hash"],
                    },
                    "id": [{"_": "inputMessageID", "id": message_id}],
                },
            )
        else:
            result = await self.client.invoke(
                "messages.getMessages", {"id": [{"_": "inputMessageID", "id": message_id}]}
            )
        for message in result.get("messages", []):
            if int(message.get("id", -1)) == message_id:
                return message
        return None


def random_long() -> int:
    value = secrets.randbits(63)
    return value or 1
