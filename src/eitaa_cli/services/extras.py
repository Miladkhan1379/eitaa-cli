from __future__ import annotations

from collections.abc import AsyncIterator
import mimetypes
from pathlib import Path
from typing import Any, cast

from eitaa_cli.api_types import (
    MessageObject,
    MessagesResponse,
    PeerReference,
    TLObject,
    TLValue,
    int_field,
    object_field,
    object_list,
    str_field,
)
from eitaa_cli.errors import EitaaError
from eitaa_cli.rpc import invoke_object
from eitaa_cli.services.media import _uploaded_media
from eitaa_cli.services.messages import random_long


class ExtrasService:
    """High-level convenience features inspired by Telethon's client helpers.

    Everything in this service maps to methods already present in Eitaa's bundled
    layer-135 schema or composes existing eitaa-cli services. It does not emulate
    server-side features that Eitaa does not expose.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    async def schedule_text(
        self,
        peer_reference: PeerReference,
        text: str,
        *,
        schedule_date: int,
        reply_to: int | None = None,
        silent: bool = False,
        no_webpage: bool = False,
        noforwards: bool = False,
    ) -> TLObject:
        if schedule_date <= 0:
            raise ValueError("schedule_date must be a positive Unix timestamp")
        peer = await self.client.peers.resolve(peer_reference)
        params: TLObject = {
            "peer": peer,
            "message": text,
            "random_id": random_long(),
            "schedule_date": schedule_date,
            "silent": silent,
            "no_webpage": no_webpage,
            "noforwards": noforwards,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await invoke_object(self.client, "messages.sendMessage", params)

    async def schedule_file(
        self,
        peer_reference: PeerReference,
        path: Path,
        *,
        schedule_date: int,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        as_document: bool = False,
        voice: bool = False,
        duration: int = 0,
        width: int = 0,
        height: int = 0,
        noforwards: bool = False,
    ) -> TLObject:
        """Upload a file and schedule it with Eitaa's server-side schedule_date."""
        if schedule_date <= 0:
            raise ValueError("schedule_date must be a positive Unix timestamp")
        path = path.expanduser().resolve()
        peer = await self.client.peers.resolve(peer_reference)
        uploaded = await self.client.media.upload(path, peer=peer)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        media = _uploaded_media(
            path=path,
            uploaded=uploaded,
            mime_type=mime_type,
            as_document=as_document,
            voice=voice,
            duration=duration,
            width=width,
            height=height,
        )
        params: TLObject = {
            "peer": peer,
            "media": media,
            "message": caption,
            "random_id": random_long(),
            "schedule_date": schedule_date,
            "silent": silent,
            "noforwards": noforwards,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await invoke_object(self.client, "messages.sendMedia", params)

    async def schedule_forward(
        self,
        source_reference: PeerReference,
        destination_reference: PeerReference,
        message_ids: list[int],
        *,
        schedule_date: int,
        silent: bool = False,
        drop_author: bool = False,
        drop_media_captions: bool = False,
        noforwards: bool = False,
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
                "schedule_date": schedule_date,
                "silent": silent,
                "drop_author": drop_author,
                "drop_media_captions": drop_media_captions,
                "noforwards": noforwards,
            },
        )

    async def scheduled_history(self, peer_reference: PeerReference) -> MessagesResponse:
        peer = await self.client.peers.resolve(peer_reference)
        return cast(
            MessagesResponse,
            await invoke_object(
                self.client,
                "messages.getScheduledHistory",
                {"peer": peer, "hash": 0},
            ),
        )

    async def send_scheduled(
        self, peer_reference: PeerReference, message_ids: list[int]
    ) -> TLObject:
        if not message_ids:
            raise ValueError("at least one scheduled message ID is required")
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(
            self.client,
            "messages.sendScheduledMessages",
            {"peer": peer, "id": message_ids},
        )

    async def delete_scheduled(
        self, peer_reference: PeerReference, message_ids: list[int]
    ) -> TLObject:
        if not message_ids:
            raise ValueError("at least one scheduled message ID is required")
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(
            self.client,
            "messages.deleteScheduledMessages",
            {"peer": peer, "id": message_ids},
        )

    async def pin(
        self,
        peer_reference: PeerReference,
        message_id: int,
        *,
        silent: bool = False,
        one_side: bool = False,
    ) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(
            self.client,
            "messages.updatePinnedMessage",
            {
                "peer": peer,
                "id": message_id,
                "silent": silent,
                "pm_oneside": one_side,
            },
        )

    async def unpin(
        self,
        peer_reference: PeerReference,
        message_id: int,
        *,
        silent: bool = False,
        one_side: bool = False,
    ) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(
            self.client,
            "messages.updatePinnedMessage",
            {
                "peer": peer,
                "id": message_id,
                "silent": silent,
                "pm_oneside": one_side,
                "unpin": True,
            },
        )

    async def unpin_all(self, peer_reference: PeerReference) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(self.client, "messages.unpinAllMessages", {"peer": peer})

    async def mark_read(self, peer_reference: PeerReference, *, max_id: int = 0) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        if peer.get("_") == "inputPeerChannel":
            return await invoke_object(
                self.client,
                "channels.readHistory",
                {
                    "channel": {
                        "_": "inputChannel",
                        "channel_id": peer["channel_id"],
                        "access_hash": peer["access_hash"],
                    },
                    "max_id": max_id,
                },
            )
        return await invoke_object(
            self.client, "messages.readHistory", {"peer": peer, "max_id": max_id}
        )

    async def save_draft(
        self,
        peer_reference: PeerReference,
        text: str,
        *,
        reply_to: int | None = None,
        no_webpage: bool = False,
    ) -> TLObject:
        peer = await self.client.peers.resolve(peer_reference)
        params: TLObject = {"peer": peer, "message": text, "no_webpage": no_webpage}
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await invoke_object(self.client, "messages.saveDraft", params)

    async def get_drafts(self) -> TLObject:
        return await invoke_object(self.client, "messages.getAllDrafts", {})

    async def clear_drafts(self) -> TLObject:
        return await invoke_object(self.client, "messages.clearAllDrafts", {})

    async def dialog_filters(self) -> TLValue:
        return await self.client.invoke("messages.getDialogFilters", {})

    async def set_folder(self, peer_reference: PeerReference, *, folder_id: int) -> TLObject:
        if folder_id < 0:
            raise ValueError("folder_id must be >= 0")
        peer = await self.client.peers.resolve(peer_reference)
        return await invoke_object(
            self.client,
            "folders.editPeerFolders",
            {
                "folder_peers": [
                    {"_": "inputFolderPeer", "peer": peer, "folder_id": folder_id}
                ]
            },
        )

    async def iter_history(
        self,
        peer_reference: PeerReference,
        *,
        limit: int | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[MessageObject]:
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive or None")
        if page_size < 1:
            raise ValueError("page_size must be positive")
        page_size = min(page_size, 100)
        remaining = limit
        offset_id = 0
        seen_ids: set[int] = set()

        while remaining is None or remaining > 0:
            batch = page_size if remaining is None else min(page_size, remaining)
            result = await self.client.messages.history(
                peer_reference,
                limit=batch,
                offset_id=offset_id,
            )
            messages = [cast(MessageObject, item) for item in result.get("messages", [])]
            fresh: list[MessageObject] = []
            for message in messages:
                message_id = int(message.get("id", 0))
                if message_id <= 0 or message_id in seen_ids:
                    continue
                seen_ids.add(message_id)
                fresh.append(message)

            if not fresh:
                break

            for message in fresh:
                yield message
                if remaining is not None:
                    remaining -= 1
                    if remaining <= 0:
                        return

            next_offset = min(int(message.get("id", 0)) for message in fresh)
            if next_offset <= 0 or next_offset == offset_id:
                break
            offset_id = next_offset

    async def history_all(
        self,
        peer_reference: PeerReference,
        *,
        limit: int | None = None,
    ) -> MessagesResponse:
        messages = [message async for message in self.iter_history(peer_reference, limit=limit)]
        return {
            "_": "messages.messages",
            "messages": messages,
            "chats": [],
            "users": [],
        }


    async def download_profile_photo(
        self,
        peer_reference: PeerReference,
        output: Path,
    ) -> Path:
        """Download the current full-size profile/chat/channel photo when available."""
        info = await self.client.dialogs.info(peer_reference)
        predicate = str_field(info, "_")
        if predicate == "userFull":
            photo = object_field(info, "profile_photo")
        elif predicate == "messages.chatFull":
            photo = object_field(object_field(info, "full_chat"), "chat_photo")
        else:
            photo = {}
        if str_field(photo, "_") != "photo":
            raise EitaaError(f"{peer_reference!r} has no downloadable profile photo")
        sizes = [
            size
            for size in object_list(photo, "sizes")
            if str_field(size, "_") != "photoSizeEmpty"
        ]
        if not sizes:
            raise EitaaError("profile photo has no downloadable sizes")
        largest = max(sizes, key=lambda item: int_field(item, "size"))
        photo_id = int_field(photo, "id")
        location: TLObject = {
            "_": "inputPhotoFileLocation",
            "id": photo_id,
            "access_hash": int_field(photo, "access_hash"),
            "file_reference": photo.get("file_reference", b""),
            "thumb_size": str_field(largest, "type", "x"),
        }
        output = output.expanduser()
        if output.suffix == "":
            output.mkdir(parents=True, exist_ok=True)
            output = output / f"profile-{photo_id}.jpg"
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
        await self.client.media.download(
            location,
            size=int_field(largest, "size"),
            output=output,
        )
        return output

    async def download_history_media(
        self,
        peer_reference: PeerReference,
        output: Path,
        *,
        limit: int | None = 500,
        skip_existing: bool = True,
    ) -> list[Path]:
        output = output.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        async for message in self.iter_history(peer_reference, limit=limit):
            media = object_field(cast(TLObject, message), "media")
            predicate = str_field(media, "_")
            if predicate not in {"messageMediaPhoto", "messageMediaDocument"}:
                continue
            message_id = int_field(cast(TLObject, message), "id")
            try:
                path = await self.client.media.download_message(
                    peer_reference, message_id, output
                )
            except EitaaError:
                continue
            if skip_existing and path.exists() and path.stat().st_size > 0:
                downloaded.append(path)
                continue
            downloaded.append(path)

        return downloaded
