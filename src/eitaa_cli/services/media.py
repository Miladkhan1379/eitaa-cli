from __future__ import annotations

import asyncio
import math
import mimetypes
import secrets
from pathlib import Path

from eitaa_cli.api_types import (
    InputPeer,
    PeerReference,
    TLObject,
    bytes_field,
    int_field,
    object_field,
    object_list,
    str_field,
)
from eitaa_cli.errors import EitaaError
from eitaa_cli.rpc import ServiceClient, invoke_object
from eitaa_cli.services.messages import MessagesService, random_long
from eitaa_cli.services.peers import input_peer_to_peer

_MAX_UPLOAD_PARTS = 4000
_BIG_FILE_THRESHOLD = 10 * 1024 * 1024


class MediaService:
    """Asynchronous media upload, send, album, and download workflows."""

    def __init__(self, client: ServiceClient) -> None:
        self.client = client

    async def upload(self, path: Path, *, peer: InputPeer | None = None) -> TLObject:
        path = path.expanduser().resolve()
        if not await asyncio.to_thread(path.is_file):
            raise FileNotFoundError(path)
        size = (await asyncio.to_thread(path.stat)).st_size
        is_big = size >= _BIG_FILE_THRESHOLD
        part_size = _upload_part_size(size)
        parts = max(1, math.ceil(size / part_size))
        if parts > _MAX_UPLOAD_PARTS:
            raise EitaaError(
                f"file requires {parts} parts; the Eitaa Web limit is {_MAX_UPLOAD_PARTS}"
            )

        file_id = secrets.randbits(63) or 1
        plain_peer = input_peer_to_peer(peer) if peer else None
        handle = await asyncio.to_thread(path.open, "rb")
        try:
            for index in range(parts):
                chunk = await asyncio.to_thread(handle.read, part_size)
                params: TLObject = {
                    "file_id": file_id,
                    "file_part": index,
                    "bytes": chunk,
                    "totalFileSize": size,
                }
                if plain_peer is not None:
                    params["peer"] = plain_peer
                if is_big:
                    params["file_total_parts"] = parts
                    await self.client.invoke("upload.saveBigFilePart", params, kind="upload")
                else:
                    await self.client.invoke("upload.saveFilePart", params, kind="upload")
        finally:
            await asyncio.to_thread(handle.close)

        if is_big:
            return {"_": "inputFileBig", "id": file_id, "parts": parts, "name": path.name}
        return {
            "_": "inputFile",
            "id": file_id,
            "parts": parts,
            "name": path.name,
            "md5_checksum": "",
        }

    async def send_file(
        self,
        peer_reference: PeerReference,
        path: Path,
        *,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        as_document: bool = False,
        voice: bool = False,
        duration: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> TLObject:
        path = path.expanduser().resolve()
        peer = await self.client.peers.resolve(peer_reference)
        uploaded = await self.upload(path, peer=peer)
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
            "silent": silent,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await invoke_object(self.client, "messages.sendMedia", params)

    async def send_album(
        self,
        peer_reference: PeerReference,
        paths: list[Path],
        *,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
    ) -> TLObject:
        if not paths:
            raise ValueError("album requires at least one file")
        if len(paths) > 10:
            raise ValueError("Eitaa albums support at most 10 files")

        peer = await self.client.peers.resolve(peer_reference)
        items: list[TLObject] = []
        for index, original_path in enumerate(paths):
            path = original_path.expanduser().resolve()
            uploaded = await self.upload(path, peer=peer)
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            pending_media = _uploaded_media(
                path=path,
                uploaded=uploaded,
                mime_type=mime_type,
                as_document=False,
                voice=False,
                duration=0,
                width=0,
                height=0,
            )
            uploaded_media = await invoke_object(
                self.client, "messages.uploadMedia", {"peer": peer, "media": pending_media}
            )
            items.append(
                {
                    "_": "inputSingleMedia",
                    "media": _message_media_to_input(uploaded_media),
                    "random_id": random_long(),
                    "message": caption if index == 0 else "",
                }
            )

        params: TLObject = {"peer": peer, "multi_media": items, "silent": silent}
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await invoke_object(self.client, "messages.sendMultiMedia", params)

    async def download_message(
        self,
        peer_reference: PeerReference,
        message_id: int,
        output: Path,
    ) -> Path:
        message = await MessagesService(self.client).get_by_id(peer_reference, message_id)
        if message is None:
            raise EitaaError(f"message {message_id} was not found")
        media = object_field(message, "media")
        location, size, suggested = _location_from_media(media)
        output = output.expanduser()
        if await asyncio.to_thread(output.is_dir):
            output = output / suggested
        elif output.suffix == "" and not await asyncio.to_thread(output.exists):
            await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
            output = output / suggested
        await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
        await self.download(location, size=size, output=output)
        return output

    async def download(
        self,
        location: TLObject,
        *,
        size: int,
        output: Path,
        chunk_size: int = 512 * 1024,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        offset = 0
        handle = await asyncio.to_thread(output.open, "wb")
        try:
            while offset < size:
                response = await invoke_object(
                    self.client,
                    "upload.getFile",
                    {
                        "location": location,
                        "offset": offset,
                        "limit": min(chunk_size, size - offset),
                        "cdn_supported": False,
                    },
                    kind="download",
                )
                if str_field(response, "_") != "upload.file":
                    raise EitaaError(f"unsupported download response: {str_field(response, '_')}")
                chunk = bytes_field(response, "bytes")
                if not chunk:
                    break
                await asyncio.to_thread(handle.write, chunk)
                offset += len(chunk)
        finally:
            await asyncio.to_thread(handle.close)

        actual_size = (await asyncio.to_thread(output.stat)).st_size
        if size and actual_size < size:
            raise EitaaError(f"download stopped at {actual_size} of {size} bytes: {output}")


def _upload_part_size(size: int) -> int:
    if size > 64 * 1024 * 1024:
        return 512 * 1024
    if size < 100 * 1024:
        return 32 * 1024
    return 256 * 1024


def _uploaded_media(
    *,
    path: Path,
    uploaded: TLObject,
    mime_type: str,
    as_document: bool,
    voice: bool,
    duration: int,
    width: int,
    height: int,
) -> TLObject:
    is_photo = mime_type.startswith("image/") and mime_type not in {"image/gif", "image/webp"}
    if is_photo and not as_document:
        return {"_": "inputMediaUploadedPhoto", "file": uploaded}

    attributes: list[TLObject] = [{"_": "documentAttributeFilename", "file_name": path.name}]
    if voice or mime_type.startswith("audio/"):
        attributes.append(
            {
                "_": "documentAttributeAudio",
                "voice": voice,
                "duration": max(0, duration),
            }
        )
    elif mime_type.startswith("video/"):
        attributes.append(
            {
                "_": "documentAttributeVideo",
                "supports_streaming": True,
                "duration": max(0, duration),
                "w": max(0, width),
                "h": max(0, height),
            }
        )
    return {
        "_": "inputMediaUploadedDocument",
        "file": uploaded,
        "mime_type": mime_type,
        "attributes": attributes,
        "force_file": as_document,
    }


def _message_media_to_input(media: TLObject) -> TLObject:
    predicate = str_field(media, "_")
    if predicate == "messageMediaPhoto":
        photo = object_field(media, "photo")
        if photo:
            return {
                "_": "inputMediaPhoto",
                "id": {
                    "_": "inputPhoto",
                    "id": int_field(photo, "id"),
                    "access_hash": int_field(photo, "access_hash"),
                    "file_reference": bytes_field(photo, "file_reference"),
                },
            }
    if predicate == "messageMediaDocument":
        document = object_field(media, "document")
        if document:
            return {
                "_": "inputMediaDocument",
                "id": {
                    "_": "inputDocument",
                    "id": int_field(document, "id"),
                    "access_hash": int_field(document, "access_hash"),
                    "file_reference": bytes_field(document, "file_reference"),
                },
            }
    raise EitaaError(f"messages.uploadMedia returned unsupported media: {predicate}")


def _location_from_media(media: TLObject) -> tuple[TLObject, int, str]:
    if str_field(media, "_") == "messageMediaDocument":
        document = object_field(media, "document")
        if document:
            identifier = int_field(document, "id")
            name = _document_filename(document) or f"document-{identifier}"
            return (
                {
                    "_": "inputDocumentFileLocation",
                    "id": identifier,
                    "access_hash": int_field(document, "access_hash"),
                    "file_reference": bytes_field(document, "file_reference"),
                    "thumb_size": "",
                },
                int_field(document, "size"),
                name,
            )

    if str_field(media, "_") == "messageMediaPhoto":
        photo = object_field(media, "photo")
        sizes = [
            size for size in object_list(photo, "sizes") if str_field(size, "_") != "photoSizeEmpty"
        ]
        if not sizes:
            raise EitaaError("photo has no downloadable sizes")
        largest = max(sizes, key=lambda item: int_field(item, "size"))
        identifier = int_field(photo, "id")
        return (
            {
                "_": "inputPhotoFileLocation",
                "id": identifier,
                "access_hash": int_field(photo, "access_hash"),
                "file_reference": bytes_field(photo, "file_reference"),
                "thumb_size": str_field(largest, "type", "x"),
            },
            int_field(largest, "size"),
            f"photo-{identifier}.jpg",
        )
    raise EitaaError(f"message has no downloadable photo/document media: {str_field(media, '_')}")


def _document_filename(document: TLObject) -> str | None:
    for attribute in object_list(document, "attributes"):
        if str_field(attribute, "_") == "documentAttributeFilename":
            return str_field(attribute, "file_name") or None
    mime = str_field(document, "mime_type")
    extension = mimetypes.guess_extension(mime) or ""
    return f"document-{int_field(document, 'id')}{extension}"
